from openstack.api import base


class Usage(base.Resource):
    def __repr__(self):
        return "<ComputeUsage>"

class UsageManager(base.ManagerWithFind):
    resource_class = Usage

    def list(self):
        return self._list("/extras/usage", "usage")

    def get(self, tenant_id):
        return self._get("/extras/usage/%s" % tenant_id, "usage")
