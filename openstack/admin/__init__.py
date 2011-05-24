import os
import ConfigParser
from distutils.util import strtobool
from openstack.api.client import ApiClient
from openstack.api.exceptions import (ApiException, BadRequest, Unauthorized,
    Forbidden, NotFound, OverLimit)
from openstack.admin.projects import ProjectManager
from openstack.api.config import Config


class Admin(object):
    """
    Top-level object to access the OpenStack Admin API.

    Create an instance with your creds::

    >>> compute = Admin(username=USERNAME, apikey=API_KEY)

    Then call methods on its managers::

        >>> compute.servers.list()
        ...
        >>> compute.flavors.list()
        ...

    &c.
    """

    def __init__(self, **kwargs):
        self.config = self._get_config(kwargs)
        self.client = ApiClient(self.config)
        self.projects = ProjectManager(self)

    def authenticate(self):
        """
        Authenticate against the server.

        Normally this is called automatically when you first access the API,
        but you can call this method to force authentication right now.

        Returns on success; raises :exc:`~openstack.compute.Unauthorized` if
        the credentials are wrong.
        """
        self.client.authenticate()

    def _get_config(self, kwargs):
        """
        Get a Config object for this API client.

        Broken out into a seperate method so that the test client can easily
        mock it up.
        """
        return Config(config_file=kwargs.pop('config_file', None),
                      env=kwargs.pop('env', None), overrides=kwargs)
