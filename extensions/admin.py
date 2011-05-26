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
import datetime
import json
import urlparse


from webob import exc


from nova import compute
from nova import db
from nova import exception
from nova import flags
from nova import log as logging
from nova import utils
from nova import wsgi
from nova.auth import manager


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
        if console_type == 'text':
            compute_api = compute.API()
            output = compute_api.get_console_output(
                      context, instance_id=server_id)
        else:
            raise Exception("Not Implemented")
        return {'console':{'id': '', 'type': console_type, 'output': output}}


class FlavorController(openstack_api.flavors.ControllerV11):

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
        print id
        qs = req.environ.get('QUERY_STRING', '')
        env = urlparse.parse_qs(qs)

        purge = env.get('purge', False)

        flavor = instance_types.get_instance_type_by_flavor_id(id)
        if purge:
            instance_types.purge(flavor['name'])
        else:
            instance_types.destroy(flavor['name'])
    
        return exc.HTTPAccepted()


class ServiceController(wsgi.Controller):

    def index(self, req):
        rv = {'services': [{'zoneName': 'nova',
                                        'zoneState': 'available'}]}

        context = req.environ['nova.context']  # without an elevated context this will fail!
        services = db.service_get_all(context, False)
        now = datetime.datetime.utcnow()
        hosts = []
        for host in [service['host'] for service in services]:
            if not host in hosts:
                hosts.append(host)
        for host in hosts:
            rv['services'].append({'zoneName': '|- %s' % host,
                                               'zoneState': ''})
            hsvcs = [service for service in services \
                     if service['host'] == host]
            for svc in hsvcs:
                delta = now - (svc['updated_at'] or svc['created_at'])
                alive = (delta.seconds <= FLAGS.service_down_time)
                art = (alive and ":-)") or "XXX"
                active = 'enabled'
                if svc['disabled']:
                    active = 'disabled'
                rv['services'].append({
                        'zoneName': '| |- %s' % svc['binary'],
                        'zoneState': '%s %s %s' % (active, art,
                                                   svc['updated_at'])})
        return rv


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

    def update(self, req):
        context = req.environ['nova.context']
        env = self._deserialize(req.body, req.get_content_type())
        name = env['project'].get('name')
        manager_user = env['project'].get('manager_user')
        description = env['project'].get('description')
        msg = _("Modify project: %(name)s managed by"
                " %(manager_user)s") % locals()
        LOG.audit(msg, context=context)
        manager.AuthManager().modify_project(name,
                                             manager_user=manager_user,
                                             description=description)
        return True

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
        resources.append(extensions.ResourceExtension('admin/consoles',
                                             ConsoleController()))
        resources.append(extensions.ResourceExtension('admin/flavors',
                                             FlavorController()))
        return resources
