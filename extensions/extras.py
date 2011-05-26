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

from webob import exc

from nova import compute
from nova import db
from nova import exception
from nova import flags
from nova import log as logging
from nova import utils
from nova import wsgi
from nova.auth import manager

from nova.api.openstack import extensions
from nova.api.openstack import faults
from nova.api.openstack import views

FLAGS = flags.FLAGS
LOG = logging.getLogger('nova.api.openstack.extras')



class ConsoleController(wsgi.Controller):
    def create(self, req):
        context = req.environ['nova.context'].elevated()
        env = self._deserialize(req.body, req.get_content_type())
        print env
        console_type = env['console'].get('type')
        server_id = env['console'].get('server_id')
        compute_api = compute.API()
        if console_type == 'text':
            output = compute_api.get_console_output(
                      context, server_id)
        elif console_type == 'vnc':
            output = compute_api.get_vnc_console(
                      context, server_id)['url']
        else:
            raise Exception("Not Implemented")
        return {'console':{'id': '', 'type': console_type, 'output': output}}


class Extras(object):

    def __init__(self):
        pass

    def get_name(self):
        return "Extras Controller"

    def get_alias(self):
        return "EXTRAS"

    def get_description(self):
        return "The Extras API Extension"

    def get_namespace(self):
        return "http:TODO/"

    def get_updated(self):
        return "2011-05-25 16:12:21.656723"

    def get_resources(self):
        resources = []
        resources.append(extensions.ResourceExtension('extras/consoles',
                                             ConsoleController()))
        return resources

