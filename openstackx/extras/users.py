from openstackx.api import base


class User(base.Resource):
    def __repr__(self):
        return "<User %s>" % self._info

    def delete(self):
        self.manager.delete(self)

    def update(self, description=None, enabled=None):
        description = description or self.description or '(none)'
        self.manager.update(self.id, description, enabled)


class UserManager(base.ManagerWithFind):
    resource_class = User

    def get(self, user_id):
        return self._get("/users/%s" % user_id, "user")

    def create(self, user_id, email, password, tenant_id, enabled=True):
        params = {"user": {"id": user_id,
                           "email": email,
                           "tenantId": tenant_id,
                           "enabled": enabled,
                           "password": password}}
        return self._create('/users', params, "user")

    def _create(self, url, body, response_key):
        resp, body = self.api.connection.put(url, body=body)
        return self.resource_class(self, body[response_key])

    def delete(self, user_id):
        self._delete("/users/%s" % user_id)

    def list(self):
        """
        Get a list of users.
        :rtype: list of :class:`User`
        """
        return self._list("/users", "users")
