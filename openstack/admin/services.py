from openstack.api import base
from openstack.compute.api import API_OPTIONS


class Services(base.Resource):
    def __repr__(self):
        return "<Service>"

    def update(self, disabled):
        self.manager.update(self.id, disabled)


class ServiceManager(base.ManagerWithFind):
    resource_class = Services

    def list(self):
        return self._list("/admin/services", "services")

    def update(self, id, disabled):
        body = {"service": {'disabled': disabled}}
        self._update("/admin/services/%s" % id, body)
