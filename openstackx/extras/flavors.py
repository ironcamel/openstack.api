from openstackx.api import base
from openstackx import compute # fixme import from jacobian


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
        return self._list("/admin/flavors", "flavors")
