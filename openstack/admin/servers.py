from openstack.api import base


class Server(base.Resource):
    def __repr__(self):
        return "<Server> %s" % self.name


class ServerManager(base.ManagerWithFind):
    resource_class = Server

    def list(self):
        return self._list("/admin/servers", "servers")
