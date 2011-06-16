from openstack.api import base
from openstack import compute


class Flavor(compute.Flavor):
    def __repr__(self):
        return "<Flavor: %s>" % self.name


class FlavorManager(compute.FlavorManager):
    resource_class = Flavor

    def list(self):
        """
        Get a list of all flavors.
        
        :rtype: list of :class:`Flavor`.
        """
        return self._list("/extras/flavors", "flavors")
