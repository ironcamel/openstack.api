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

    def update(self, name=None, description=None):
        if name is None:
            name = self.name
        if description is None:
            description = self.description
        self.manager.update(self, name, description)


class TenantManager(base.ManagerWithFind):
    resource_class = Tenant

    def create(self, tenant_id, description=None, enabled=True):
        params = {"tenant": {"id": tenant_id,

                             "enabled": enabled}}

        return self._create('/tenants', params, "tenant")

    def list(self):
        """
        Get a list of tenants.
        :rtype: list of :class:`Tenant`
        """
        return self._list("/tenants", "tenants")

    def update(self, tenant, name, description):
        """
        update a tenant with a new name and description
        """
        body = {'name': name, 'description': description}
        self._update("/tenants/%s" % base.getid(tenant), body)

    def delete(self, tenant):
        """
        Delete a tenant
        """
        self._delete("/tenants/%s" % base.getid(tenant))
