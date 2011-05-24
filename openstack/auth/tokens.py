from openstack.api import base


class Token(base.Resource):
    def __repr__(self):
        
        return "<Token %s>" % self._info

    @property
    def id(self):
        return self._info['token']['id']

    @property
    def username(self):
        return self._info['user']['username'] 

    @property
    def tenant_id(self):
        return self._info['user']['tenantId'] 

    def delete(self):
        self.manager.delete(self)


class TokenManager(base.ManagerWithFind):
    resource_class = Token

    def create(self, tenant, username, password):
        params = {"passwordCredentials": {"username": username,
                                          "password": password,
                                          "tenantId": tenant}}

        return self._create('token', params, "auth")
