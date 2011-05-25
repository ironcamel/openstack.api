from openstack.api import base
from openstack.compute.api import API_OPTIONS


class Services(base.Resource):
    def __repr__(self):
        return "<Service>"


class ServiceManager(base.ManagerWithFind):
    resource_class = Services

    def list(self):
        return self._list("/admin/services", "services")
