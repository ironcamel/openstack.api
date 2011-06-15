from openstack.api import base


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

    def create(self, user_id, email, password, enabled=True):
        params = {"user": {"id": user_id,
                           "email": email,
                           "enabled": enabled,
                           "password": password}}

        return self._put_create('/users', params, "user")

    def list(self):
        """
        Get a list of users.
        :rtype: list of :class:`User`
        """
        return self._list("/users", "users")

