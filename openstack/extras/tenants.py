from openstack.api import base


class Tenant(base.Resource):
    def __repr__(self):
        return "<Tenant %s>" % self._info

    def delete(self):
        self.manager.delete(self)

    def update(self, description=None, enabled=None):
        description = description or self.description or '(none)'
        self.manager.update(self.id, description, enabled)


class TenantManager(base.ManagerWithFind):
    resource_class = Tenant

    def get(self, tenant_id):
        return self._get("/tenants/%s" % tenant_id, "tenant")

    def create(self, tenant_id, description, enabled=True):
        params = {"tenant": {"id": tenant_id,
                             "description": description,
                             "enabled": enabled}}

        return self._create('/tenants', params, "tenant")

    def list(self):
        """
        Get a list of tenants.
        :rtype: list of :class:`Tenant`
        """
        return self._list("/tenants", "tenants")

    def update(self, tenant_id, description=None, enabled=None):
        """
        update a tenant with a new name and description
        """
        body = {"tenant": {'id': tenant_id }}
        if enabled is not None:
            body['tenant']['enabled'] = enabled
        if description:
            body['tenant']['description'] = description

        self._update("/tenants/%s" % tenant_id, body)

    def delete(self, tenant_id):
        """
        Delete a tenant
        """
        self._delete("/tenants/%s" % tenant_id)
