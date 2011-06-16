from openstack.api import base


class Server(base.Resource):
    def __repr__(self):
        return "<Server>"

    def update(self, name=None, password=None, description=None):
        """
        Update the name or the password for this server.

        :param name: Update the server's name.
        :param password: Update the root password.
        :param description: Update the description
        """
        self.manager.update(self, name, password, description)


class ServerManager(base.ManagerWithFind):
    resource_class = Server

    def get(self, server_id):
        return self._get("/extras/servers/%s" % server_id, "server")

    def list(self):
        return self._list("/extras/servers", "servers")

    def update(self, server, name=None, password=None, description=None):
        """
        Update the name or the password for a server.

        :param server: The :class:`Server` (or its ID) to update.
        :param name: Update the server's name.
        :param password: Update the root password.
        """

        if name is None and password is None and description is None:
            return
        body = {"server": {}}
        if description:
            body["server"]["description"] = description
        if name:
            body["server"]["name"] = name
        if password:
            body["server"]["adminPass"] = password
        self._update("/extras/servers/%s" % base.getid(server), body)
