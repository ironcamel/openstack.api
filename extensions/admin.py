# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import base64
import json
import urlparse

from datetime import datetime
from operator import add
from webob import exc


from nova import compute
from nova import crypto
from nova import db
from nova import exception
from nova import flags
from nova import log as logging
from nova import utils
from nova import wsgi
from nova.auth import manager as auth_manager
from nova.db.sqlalchemy.session import get_session


import nova.api.openstack as openstack_api
from nova.api.openstack import extensions
from nova.api.openstack import faults
from nova.api.openstack import views

from nova.compute import instance_types

FLAGS = flags.FLAGS
flags.DECLARE('max_gigabytes', 'nova.scheduler.simple')
flags.DECLARE('max_cores', 'nova.scheduler.simple')

LOG = logging.getLogger('nova.api.openstack.admin')


def user_dict(user, base64_file=None):
    """Convert the user object to a result dict"""
    if user:
        return {
            'username': user.id,
            'accesskey': user.access,
            'secretkey': user.secret,
            'file': base64_file}
    else:
        return {}


def project_dict(project):
    """Convert the project object to a result dict"""
    if project:
        return {
            'id': project.id,
            'name': project.id,
            'projectname': project.id,
            'project_manager_id': project.project_manager_id,
            'description': project.description}
    else:
        return {}


def host_dict(host, compute_service, instances, volume_service, volumes, now):
    """Convert a host model object to a result dict"""
    rv = {'hostname': host, 'instance_count': len(instances),
          'volume_count': len(volumes)}
    if compute_service:
        latest = compute_service['updated_at'] or compute_service['created_at']
        delta = now - latest
        if delta.seconds <= FLAGS.service_down_time:
            rv['compute'] = 'up'
        else:
            rv['compute'] = 'down'
    if volume_service:
        latest = volume_service['updated_at'] or volume_service['created_at']
        delta = now - latest
        if delta.seconds <= FLAGS.service_down_time:
            rv['volume'] = 'up'
        else:
            rv['volume'] = 'down'
    return rv


def instance_dict(inst):
    return {'name': inst['name'],
            'memory_mb': inst['memory_mb'],
            'vcpus': inst['vcpus'],
            'disk_gb': inst['local_gb'],
            'image_id': inst['image_id'],
            'kernel_id': inst['kernel_id'],
            'ramdisk_id': inst['ramdisk_id'],
            'user': inst['user_id'],
            'scheduled_at': inst['scheduled_at'],
            'launched_at': inst['launched_at'],
            'terminated_at': inst['terminated_at'],
            'display_name': inst['display_name'],
            'display_description': inst['display_description'],
            'os_type': inst['os_type'],
            'hostname': inst['hostname'],
            'host': inst['host'],
            'id': inst['id'],
            }


def vpn_dict(project, vpn_instance):
    rv = {'project_id': project.id,
          'public_ip': project.vpn_ip,
          'public_port': project.vpn_port}
    if vpn_instance:
        rv['instance_id'] = ec2utils.id_to_ec2_id(vpn_instance['id'])
        rv['created_at'] = utils.isotime(vpn_instance['created_at'])
        address = vpn_instance.get('fixed_ip', None)
        if address:
            rv['internal_ip'] = address['address']
        if project.vpn_ip and project.vpn_port:
            if utils.vpn_ping(project.vpn_ip, project.vpn_port):
                rv['state'] = 'running'
            else:
                rv['state'] = 'down'
        else:
            rv['state'] = 'down - invalid project vpn config'
    else:
        rv['state'] = 'pending'
    return rv


class ExtrasServerController(openstack_api.servers.ControllerV11):
    def _get_view_builder(self, req):
        class ViewBuilder(views.servers.ViewBuilderV11):
            def __init__(self,
                         addresses_builder,
                         flavor_builder,
                         image_builder,
                         base_url):
                views.servers.ViewBuilderV11.__init__(self,
                                                      addresses_builder,
                                                      flavor_builder,
                                                      image_builder,
                                                      base_url)

            def _build_extra(self, response, inst):
                self._build_links(response, inst)
                self._build_extended_attributes(response, inst)

            def _build_extended_attributes(self, response, inst):
                attrs = {'name': inst['display_name'],
                        'memory_mb': inst['memory_mb'],
                        'vcpus': inst['vcpus'],
                        'disk_gb': inst['local_gb'],
                        'image_id': inst['image_id'],
                        'kernel_id': inst['kernel_id'],
                        'ramdisk_id': inst['ramdisk_id'],
                        'user_id': inst['user_id'],
                        #'project_id': inst['project'].id,
                        'scheduled_at': inst['scheduled_at'],
                        'launched_at': inst['launched_at'],
                        'terminated_at': inst['terminated_at'],
                        'description': inst['display_description'],
                        'os_type': inst['os_type'],
                        'hostname': inst['hostname'],
                        'host': inst['host'],
                        'key_name': inst['key_name'],
                        'user_data': inst['user_data'],
                        'mac_address': inst['mac_address'],
                        'os_type': inst['os_type'],
                        }
                response['server']['attrs'] = attrs

        base_url = req.application_url
        flavor_builder = views.flavors.ViewBuilderV11(base_url)
        image_builder = views.images.ViewBuilderV11(base_url)
        addresses_builder = views.addresses.ViewBuilderV11()

        return ViewBuilder(
            addresses_builder, flavor_builder, image_builder, base_url)

    def index(self, req):
        return self._items(req, is_detail=True)

    # @scheduler_api.redirect_handler
    def update(self, req, id):
        """ Updates the server name or password """
        if len(req.body) == 0:
            raise exc.HTTPUnprocessableEntity()

        inst_dict = self._deserialize(req.body, req.get_content_type())
        if not inst_dict:
            return faults.Fault(exc.HTTPUnprocessableEntity())

        ctxt = req.environ['nova.context']
        update_dict = {}

        if 'name' in inst_dict['server']:
            name = inst_dict['server']['name']
            self._validate_server_name(name)
            update_dict['display_name'] = name.strip()

        if 'description' in inst_dict['server']:
            description = inst_dict['server']['description']
            update_dict['display_description'] = description.strip()

        self._parse_update(ctxt, id, inst_dict, update_dict)

        try:
            self.compute_api.update(ctxt, id, **update_dict)
        except exception.NotFound:
            return faults.Fault(exc.HTTPNotFound())

        return exc.HTTPNoContent()


    def create(self, req):
        """ Creates a new server for a given user """
        env = self._deserialize_create(req)
        if not env:
            return faults.Fault(exc.HTTPUnprocessableEntity())

        context = req.environ['nova.context']

        password = self._get_server_admin_password(env['server'])

        key_name = env['server'].get('key_name')
        key_data = None

        if key_name:
            try:
                key_pair = db.key_pair_get(context, context.user_id, key_name)
                key_name = key_pair['name']
                key_data = key_pair['public_key']
            except:
                msg = _("Can not load the requested key %s" % key_name)
                return faults.Fault(exc.HTTPBadRequest(msg))
        else:
            # backwards compatibility
            key_pairs = auth_manager.AuthManager.get_key_pairs(context)
            if key_pairs:
                key_pair = key_pairs[0]
                key_name = key_pair['name']
                key_data = key_pair['public_key']

        image_id = self._image_id_from_req_data(env)

        kernel_id, ramdisk_id = self._get_kernel_ramdisk_from_image(
            req, image_id)

        personality = env['server'].get('personality')
        injected_files = []
        if personality:
            injected_files = self._get_injected_files(personality)

        flavor_id = self._flavor_id_from_req_data(env)

        if not 'name' in env['server']:
            msg = _("Server name is not defined")
            return exc.HTTPBadRequest(msg)
        print "4444"

        name = env['server']['name']
        self._validate_server_name(name)
        name = name.strip()

        try:
            inst_type = \
                instance_types.get_instance_type_by_flavor_id(flavor_id)
            (inst,) = self.compute_api.create(
                context,
                inst_type,
                image_id,
                kernel_id=kernel_id,
                ramdisk_id=ramdisk_id,
                display_name=name,
                display_description=name,
                key_name=key_name,
                key_data=key_data,
                user_data=env['server'].get('user_data'),
                metadata=env['server'].get('metadata', {}),
                injected_files=injected_files,
                admin_password=password)
        except quota.QuotaError as error:
            self._handle_quota_error(error)

        inst['instance_type'] = inst_type
        inst['image_id'] = image_id

        builder = self._get_view_builder(req)
        server = builder.build(inst, is_detail=True)
        server['server']['adminPass'] = password
        return server


class ExtrasConsoleController(object):
    def create(self, req):
        context = req.environ['nova.context'].elevated()
        env = self._deserialize(req.body, req.get_content_type())
        console_type = env['console'].get('type')
        server_id = env['console'].get('server_id')
        compute_api = compute.API()
        if console_type == 'text':
            output = compute_api.get_console_output(
                      context, instance_id=server_id)
        elif console_type == 'vnc':
            output = compute_api.get_vnc_console(
                      context, instance_id=server_id)['url']
        else:
            raise Exception("Not Implemented")
        return {'console':{'id': '', 'type': console_type, 'output': output}}


class ExtrasFlavorController(openstack_api.flavors.ControllerV11):
    def _get_view_builder(self, req):
        class ViewBuilder(views.flavors.ViewBuilderV11):
            def __init__(self, base_url):
                self.base_url = base_url

            def _build_simple(self, flavor_obj):
                simple = {
                    "id": flavor_obj["flavorid"],
                    "name": flavor_obj["name"],
                    #FIXME - why isn't this memory_mb?
                    "ram": flavor_obj["memory_mb"],
                    "disk": flavor_obj["local_gb"],
                    "vcpus": flavor_obj["vcpus"],
                }
                return simple


        base_url = req.application_url
        return ViewBuilder(base_url)


class AdminFlavorController(ExtrasFlavorController):

    def create(self, req):
        env = self._deserialize(req.body, req.get_content_type())

        name = env['flavor'].get('name')
        memory_mb = env['flavor'].get('memory_mb')
        vcpus = env['flavor'].get('vcpus')
        local_gb = env['flavor'].get('local_gb')
        flavorid = env['flavor'].get('flavorid')
        swap = env['flavor'].get('swap')
        rxtx_quota = env['flavor'].get('rxtx_quota')
        rxtx_cap = env['flavor'].get('rxtx_cap')

        context = req.environ['nova.context'].elevated()
        flavor = instance_types.create(name, memory_mb, vcpus,
                                       local_gb, flavorid,
                                       swap, rxtx_quota, rxtx_cap)
        builder = self._get_view_builder(req)
        values = builder.build(env['flavor'], is_detail=True)
        return dict(flavor=values)

    def delete(self, req, id):
        qs = req.environ.get('QUERY_STRING', '')
        env = urlparse.parse_qs(qs)

        purge = env.get('purge', False)

        flavor = instance_types.get_instance_type_by_flavor_id(id)
        if purge:
            instance_types.purge(flavor['name'])
        else:
            instance_types.destroy(flavor['name'])
    
        return exc.HTTPAccepted()


class UsageController(object):

    def _hours_for(self, instance, period_start, period_stop):
        print period_start
        print period_stop
        # nothing if it stopped before the usage report start
        #terminated_at = instance['terminated_at']
        #launched_at = instance['launched_at']

        launched_at = terminated_at = None
        if instance['terminated_at'] is not None:
            terminated_at = datetime.strptime(instance['terminated_at'], "%Y-%m-%d %H:%M:%S.%f")

        if instance['launched_at'] is not None:
            launched_at = datetime.strptime(instance['launched_at'], "%Y-%m-%d %H:%M:%S.%f")

        if terminated_at and terminated_at < period_start:
            return 0
        # nothing if it started after the usage report ended
        if launched_at and launched_at > period_stop:
            return 0
        if launched_at:
            # if instance launched after period_started, don't charge for first
            start = max(launched_at, period_start)
            if terminated_at:
                # if instance stopped before period_stop, don't charge after
                stop = min(period_stop, terminated_at)
            else:
                # instance is still running, so charge them up to current time
                stop = period_stop
            dt = stop - start
            seconds = dt.days * 3600 * 24 + dt.seconds\
                      + dt.microseconds / 100000.0

            return seconds/3600.0
        else:
            # instance hasn't launched, so no charge
            return 0

    def _usage_for_period(self, context, period_start, period_stop, tenant_id=None):
        fields = ['id',
                  'image_id',
                  'project_id',
                  'user_id',
                  'vcpus',
                  'hostname',
                  'display_name',
                  'host',
                  'state_description',
                  'instance_type_id',
                  'launched_at',
                  'terminated_at']

        tenant_clause = ''
        if tenant_id:
            tenant_clause = " and project_id='%s'" % tenant_id

        connection = get_session().connection()
        rows = connection.execute("select %s from instances where \
                                   (terminated_at is NULL or terminated_at > '%s') \
                                   and (launched_at < '%s') %s" %\
                                   (','.join(fields), period_start.isoformat(' '),\
                                   period_stop.isoformat(' '), tenant_clause
                                   )).fetchall()

        rval = {}

        for row in rows:
            o = {}
            for i in range(len(fields)):
                o[fields[i]] = row[i]
            o['hours'] = self._hours_for(o, period_start, period_stop)

            flavor = db.instance_type_get_by_id(context, o['instance_type_id'])

            o['name'] = o['display_name']
            del(o['display_name'])

            o['ram_size'] = flavor['memory_mb']
            o['disk_size'] = flavor['local_gb']

            o['tenant_id'] = o['project_id']
            del(o['project_id'])

            o['flavor'] = flavor['name']
            del(o['instance_type_id'])

            o['started_at'] = o['launched_at']
            del(o['launched_at'])

            o['ended_at'] = o['terminated_at']
            del(o['terminated_at'])

            if o['ended_at']:
                o['state'] = 'terminated'
            else:
                o['state'] = o['state_description']

            del(o['state_description'])

            now = datetime.utcnow()

            if o['state'] == 'terminated':
                delta = self._parse_datetime(o['ended_at'])\
                             - self._parse_datetime(o['started_at'])
            else:
                delta = now - self._parse_datetime(o['started_at'])

            o['uptime'] = delta.days + 24 * 60 + delta.seconds

            if not o['tenant_id'] in rval:
                summary = {}
                summary['tenant_id'] = o['tenant_id']
                summary['instances'] = []
                summary['total_disk_usage'] = 0
                summary['total_cpu_usage'] = 0
                summary['total_ram_usage'] = 0

                summary['total_active_ram_size'] = 0
                summary['total_active_disk_size'] = 0
                summary['total_active_vcpus'] = 0
                summary['total_active_instances'] = 0

                summary['total_hours'] = 0
                summary['begin'] = period_start
                summary['stop'] = period_stop
                rval[o['tenant_id']] = summary

            rval[o['tenant_id']]['total_disk_usage'] += o['disk_size'] * o['hours']
            rval[o['tenant_id']]['total_cpu_usage'] += o['vcpus'] * o['hours']
            rval[o['tenant_id']]['total_ram_usage'] += o['ram_size'] * o['hours']

            if o['state'] is not 'terminated':
                rval[o['tenant_id']]['total_active_ram_size'] += o['ram_size']
                rval[o['tenant_id']]['total_active_vcpus'] += o['vcpus']
                rval[o['tenant_id']]['total_active_disk_size'] += o['disk_size']
                rval[o['tenant_id']]['total_active_instances'] += 1

            rval[o['tenant_id']]['total_hours'] += o['hours']
            rval[o['tenant_id']]['instances'].append(o)

        return rval.values()

    def _parse_datetime(self, dtstr):
        try:
            return datetime.strptime(dtstr, "%Y-%m-%dT%H:%M:%S")
        except:
            try:
                return datetime.strptime(dtstr, "%Y-%m-%dT%H:%M:%S.%f")
            except:
                return datetime.strptime(dtstr, "%Y-%m-%d %H:%M:%S.%f")

    def _get_datetime_range(self, req):
        qs = req.environ.get('QUERY_STRING', '')
        env = urlparse.parse_qs(qs)
        period_start = self._parse_datetime(env.get('start', [datetime.utcnow().isoformat()])[0])
        period_stop = self._parse_datetime(env.get('end', [datetime.utcnow().isoformat()])[0])
        return (period_start, period_stop)

    def index(self, req):
        (period_start, period_stop) = self._get_datetime_range(req)
        context = req.environ['nova.context']
        usage = self._usage_for_period(context, period_start, period_stop)
        return {'usage': {'values': usage}}
    
    def show(self, req, id):
        (period_start, period_stop) = self._get_datetime_range(req)
        context = req.environ['nova.context']
        usage = self._usage_for_period(context, period_start, period_stop, id)
        if len(usage):
            usage = usage[0]
        else:
            usage = {}
        return {'usage': usage}
    

class AdminServiceController(object):

    def _set_attr(self, service):
        now = datetime.utcnow()
        delta = now - (service['updated_at'] or service['created_at'])
        stats = {}
        if service['binary'] == 'nova-compute':
            stats['max_vcpus'] = FLAGS.max_cores
            stats['max_gigabytes'] = FLAGS.max_gigabytes
        return {
            'id': service['id'],
            'host': service['host'],
            'disabled': service['disabled'],
            'type': service['binary'],
            'zone': service['availability_zone'],
            'last_update': service['updated_at'],
            'up': (delta.seconds <= FLAGS.service_down_time),
            'stats': stats
        }

    def index(self, req):
        context = req.environ['nova.context'].elevated()
        services = []
        for service in db.service_get_all(context):
            services.append(self._set_attr(service))
        return {'services': services}

    def show(self, req, id):
        context = req.environ['nova.context'].elevated()
        service = self._set_attr(db.service_get(context, id))
        return {'service': service}

    def update(self, req, id):
        context = req.environ['nova.context'].elevated()
        env = self._deserialize(req.body, req.get_content_type())
        name = env['service'].get('disabled')
        db.service_update(context, id, env['service'])
        return exc.HTTPAccepted()


class ExtrasKeypairController(object):
    def _gen_key(self, context, user_id, key_name):
        """Generate a key

        This is a module level method because it is slow and we need to defer
        it into a process pool."""
        # NOTE(vish): generating key pair is slow so check for legal
        #             creation before creating key_pair
        try:
            db.key_pair_get(context, user_id, key_name)
            raise exception.KeyPairExists(key_name=key_name)
        except exception.NotFound:
            pass
        private_key, public_key, fingerprint = crypto.generate_key_pair()
        key = {}
        key['user_id'] = user_id
        key['name'] = key_name
        key['public_key'] = public_key
        key['fingerprint'] = fingerprint
        db.key_pair_create(context, key)
        return {'private_key': private_key, 'fingerprint': fingerprint}

    def create(self, req):
        env = self._deserialize(req.body, req.get_content_type())
        context = req.environ['nova.context']
        key_name = env['keypair']['key_name']
        LOG.audit(_("Create key pair %s"), key_name, context=context)
        data = self._gen_key(context, context.user_id, key_name)

        rval = env
        rval['keypair']['fingerprint'] = data['fingerprint']
        rval['keypair']['private_key'] = data['private_key']
        return rval

    def delete(self, req, id):
        context = req.environ['nova.context']
        key_name = id
        LOG.audit(_("Delete key pair %s"), key_name, context=context)
        try:
            db.key_pair_destroy(context, context.user_id, key_name)
        except exception.NotFound:
            # aws returns true even if the key doesn't exist
            pass
        return exc.HTTPAccepted()

    def index(self, req):
        context = req.environ['nova.context']
        key_pairs = db.key_pair_get_all_by_user(context, context.user_id)
        result = []
        for key_pair in key_pairs:
            # filter out the vpn keys
            suffix = FLAGS.vpn_key_suffix
            if context.is_admin or \
               not key_pair['name'].endswith(suffix):
                result.append({
                    'name': key_pair['name'],
                    'key_name': key_pair['name'],
                    'fingerprint': key_pair['fingerprint'],
                })


        return {'keypairs': result}


class AdminProjectController(object):

    def show(self, req, id):
        return project_dict(auth_manager.AuthManager().get_project(id))

    def index(self, req):
        user = req.environ.get('user')
        return {'projects':
            [project_dict(u) for u in
            auth_manager.AuthManager().get_projects(user=user)]}

    def create(self, req):
        env = self._deserialize(req.body, req.get_content_type())
        name = env['project'].get('name')
        manager_user = env['project'].get('manager_user')
        description = env['project'].get('description')
        member_users = env['project'].get('member_users')

        context = req.environ['nova.context']
        msg = _("Create project %(name)s managed by"
                " %(manager_user)s") % locals()
        LOG.audit(msg, context=context)
        project = project_dict(
                     auth_manager.AuthManager().create_project(
                     name,
                     manager_user,
                     description=None,
                     member_users=None))
        return {'project': project}

    def update(self, req, id):
        context = req.environ['nova.context']
        env = self._deserialize(req.body, req.get_content_type())
        name = id
        manager_user = env['project'].get('manager_user')
        description = env['project'].get('description')
        msg = _("Modify project: %(name)s managed by"
                " %(manager_user)s") % locals()
        LOG.audit(msg, context=context)
        auth_manager.AuthManager().modify_project(name,
                                             manager_user=manager_user,
                                             description=description)
        return exc.HTTPAccepted()

    def delete(self, req, id):
        context = req.environ['nova.context']
        LOG.audit(_("Delete project: %s"), id, context=context)
        auth_manager.AuthManager().delete_project(id)
        return exc.HTTPAccepted()


class Admin(object):

    def __init__(self):
        pass

    def get_name(self):
        return "Admin Controller"

    def get_alias(self):
        return "ADMIN"

    def get_description(self):
        return "The Admin API Extension"

    def get_namespace(self):
        return "http:TODO/"

    def get_updated(self):
        return "2011-05-25 16:12:21.656723"

    def get_resources(self):
        resources = []
        resources.append(extensions.ResourceExtension('admin/projects',
                                                 AdminProjectController()))
        resources.append(extensions.ResourceExtension('admin/services',
                                                 AdminServiceController()))
        resources.append(extensions.ResourceExtension('extras/consoles',
                                             ExtrasConsoleController()))
        resources.append(extensions.ResourceExtension('admin/flavors',
                                             AdminFlavorController()))
        resources.append(extensions.ResourceExtension('extras/usage',
                                             UsageController()))
        resources.append(extensions.ResourceExtension('extras/flavors',
                                             ExtrasFlavorController()))
        resources.append(extensions.ResourceExtension('extras/servers',
                                             ExtrasServerController()))
        resources.append(extensions.ResourceExtension('extras/keypairs',
                                             ExtrasKeypairController()))
        return resources
