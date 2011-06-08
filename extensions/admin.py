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
from nova import db
from nova import exception
from nova import flags
from nova import log as logging
from nova import utils
from nova import wsgi
from nova.auth import manager
from nova.db.sqlalchemy.session import get_session


import nova.api.openstack as openstack_api
from nova.api.openstack import extensions
from nova.api.openstack import faults
from nova.api.openstack import views

from nova.compute import instance_types

FLAGS = flags.FLAGS
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


class ServerController(wsgi.Controller):
    def _get_builder(self, req):
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
                attrs = {'name': inst['name'],
                        'memory_mb': inst['memory_mb'],
                        'vcpus': inst['vcpus'],
                        'disk_gb': inst['local_gb'],
                        'image_id': inst['image_id'],
                        'kernel_id': inst['kernel_id'],
                        'ramdisk_id': inst['ramdisk_id'],
                        'user_id': inst['user_id'],
                        'project_id': inst['project'].id,
                        'scheduled_at': inst['scheduled_at'],
                        'launched_at': inst['launched_at'],
                        'terminated_at': inst['terminated_at'],
                        'display_name': inst['display_name'],
                        'display_description': inst['display_description'],
                        'os_type': inst['os_type'],
                        'hostname': inst['hostname'],
                        'host': inst['host'],
                        'key_name': inst['key_name'],
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
        context = req.environ['nova.context'].elevated()
        instances = db.instance_get_all(context)
        builder = self._get_builder(req)
        server_list = db.instance_get_all(context)
        servers = [builder.build(inst, True)['server']
                for inst in instances]
        return dict(servers=servers)

    def show(self, req, id):
        context = req.environ['nova.context'].elevated()
        instance = db.instance_get(context, id)
        builder = self._get_builder(req)
        return builder.build(instance, True)


class ConsoleController(wsgi.Controller):
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


class FlavorController(openstack_api.flavors.ControllerV11):

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


class UsageController(wsgi.Controller):

    def _hours_for(self, instance, period_start, period_stop):
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

    def _usage_for_period(self, period_start, period_stop, tenant_id=None):
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

            flavor = instance_types.get_instance_type_by_flavor_id(o['instance_type_id'])

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

            if not o['tenant_id'] in rval:
                summary = {}
                summary['instances'] = []
                summary['total_disk_usage'] = 0
                summary['total_cpu_usage'] = 0
                summary['total_ram_usage'] = 0

                summary['total_active_ram_size'] = 0
                summary['total_active_disk_size'] = 0
                summary['total_active_vcpus'] = 0

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

            rval[o['tenant_id']]['total_hours'] += o['hours']
            rval[o['tenant_id']]['instances'].append(o)

        return rval.values()


    def _parse_datetime(self, dtstr):
        try:
            return datetime.strptime(dtstr, "%Y-%m-%dT%H:%M:%S")
        except:
            return datetime.strptime(dtstr, "%Y-%m-%dT%H:%M:%S.%f")

    def _get_datetime_range(self, req):
        qs = req.environ.get('QUERY_STRING', '')
        env = urlparse.parse_qs(qs)
        period_start = self._parse_datetime(env.get('start', [datetime.utcnow().isoformat()])[0])
        period_stop = self._parse_datetime(env.get('end', [datetime.utcnow().isoformat()])[0])
        return (period_start, period_stop)

    def index(self, req):
        (period_start, period_stop) = self._get_datetime_range(req)
        usage = self._usage_for_period(period_start, period_stop)
        return {'usage': {'values': usage}}
    
    def show(self, req, id):
        (period_start, period_stop) = self._get_datetime_range(req)
        usage = self._usage_for_period(period_start, period_stop, id)
        if len(usage):
            usage = usage[0]
        else:
            usage = {}
        return {'usage': usage}
    

class ServiceController(wsgi.Controller):

    def index(self, req):
        context = req.environ['nova.context'].elevated()
        now = datetime.utcnow()
        services = []
        for service in db.service_get_all(context, False):
            delta = now - (service['updated_at'] or service['created_at'])
            services.append({
                'id': service['id'],
                'host': service['host'],
                'disabled': service['disabled'],
                'type': service['binary'],
                'zone': service['availability_zone'],
                'last_update': service['updated_at'],
                'up': (delta.seconds <= FLAGS.service_down_time)
            })
        return {'services': services}

    def update(self, req, id):
        context = req.environ['nova.context'].elevated()
        env = self._deserialize(req.body, req.get_content_type())
        name = env['service'].get('disabled')
        db.service_update(context, id, env['service'])
        return exc.HTTPAccepted()


class ProjectController(wsgi.Controller):

    def show(self, req, id):
        return project_dict(manager.AuthManager().get_project(id))

    def index(self, req):
        user = req.environ.get('user')
        return {'projects':
            [project_dict(u) for u in
            manager.AuthManager().get_projects(user=user)]}

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
                     manager.AuthManager().create_project(
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
        manager.AuthManager().modify_project(name,
                                             manager_user=manager_user,
                                             description=description)
        return exc.HTTPAccepted()

    def delete(self, req, id):
        context = req.environ['nova.context']
        LOG.audit(_("Delete project: %s"), id, context=context)
        manager.AuthManager().delete_project(id)
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
                                                 ProjectController()))
        resources.append(extensions.ResourceExtension('admin/services',
                                                 ServiceController()))
        resources.append(extensions.ResourceExtension('admin/servers',
                                             ServerController()))
        resources.append(extensions.ResourceExtension('extras/consoles',
                                             ConsoleController()))
        resources.append(extensions.ResourceExtension('admin/flavors',
                                             FlavorController()))
        resources.append(extensions.ResourceExtension('extras/usage',
                                             UsageController()))
        return resources
