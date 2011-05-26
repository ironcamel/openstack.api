from openstack.api import base
from openstack import compute


class Flavor(compute.Flavor):
    def __repr__(self):
        return "<Flavor: %s>" % self.name

    def delete(self, purge=False):
        self.manager.delete(self.id, purge)


class FlavorManager(compute.FlavorManager):
    resource_class = Flavor

    def create(self, name, memory_mb, vcpus, local_gb, flavorid,
               swap=0, rxtx_quota=0, rxtx_cap=0):

        body = {}
        body['flavor'] = {}
        body['flavor']['name'] = name
        body['flavor']['memory_mb'] = memory_mb
        body['flavor']['vcpus'] = vcpus
        body['flavor']['local_gb'] = local_gb
        body['flavor']['flavorid'] = flavorid
        body['flavor']['swap'] = swap
        body['flavor']['rxtx_quota'] = rxtx_quota
        body['flavor']['rxtx_cap'] = rxtx_cap
        
        return self._create('/admin/flavors', body, "flavor")

    def delete(self, id, purge=False):
        print "delete %s" % id
        self._delete("/admin/flavors/%s?purge=%s" % (id, purge))
