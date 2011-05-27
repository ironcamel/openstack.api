from openstack.api import base


class Tenant(base.Resource):
    def __repr__(self):
        
        return "<Tenant %s>" % self._info

    @property
    def id(self):
        return self._info['id']

    @property
    def enabled(self):
        return self._info['enabled']

    @property
    def description(self):
        return self._info['description']

    def delete(self):
        self.manager.delete(self)


class TenantManager(base.ManagerWithFind):
    resource_class = Tenant

    def create(self, tenant_id, description, enabled=True):
        params = {"tenant": {"id": tenant_id,
                             "description": description,
                             "enabled": enabled}}

        return self._create('tenants', params, "tenant")
