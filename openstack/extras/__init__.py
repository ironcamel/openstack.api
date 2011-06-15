from openstack.api.connection import ApiConnection
from openstack.extras.consoles import ConsoleManager
from openstack.extras.flavors import FlavorManager
from openstack.extras.tenants import TenantManager
from openstack.extras.users import UserManager
from openstack.extras.usage import UsageManager
from openstack.api.config import Config


class Extras(object):
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
        self.connection = ApiConnection(self.config)
        self.consoles = ConsoleManager(self)
        self.usage = UsageManager(self)
        self.flavors = FlavorManager(self)

    def authenticate(self):
        """
        Authenticate against the server.

        Normally this is called automatically when you first access the API,
        but you can call this method to force authentication right now.

        Returns on success; raises :exc:`~openstack.compute.Unauthorized` if
        the credentials are wrong.
        """
        self.connection.authenticate()

    def _get_config(self, kwargs):
        """
        Get a Config object for this API client.

        Broken out into a seperate method so that the test client can easily
        mock it up.
        """
        return Config(config_file=kwargs.pop('config_file', None),
                      env=kwargs.pop('env', None), overrides=kwargs)


class Account(object):
    """
    API to use keystone extension for tenant / user management

    Create an instance with your creds::

    >>> accounts = Account(auth_token='123', management_url='...')

    Then call methods on its managers::

        >>> accounts.tenants.list()
        ...
        >>> accounts.users.list()
        ...

    &c.
    """

    def __init__(self, **kwargs):
        self.config = self._get_config(kwargs)
        self.connection = ApiConnection(self.config)
        self.tenants = TenantManager(self)
        self.users = UserManager(self)

    def authenticate(self):
        """
        Authenticate against the server.

        Normally this is called automatically when you first access the API,
        but you can call this method to force authentication right now.

        Returns on success; raises :exc:`~openstack.compute.Unauthorized` if
        the credentials are wrong.
        """
        self.connection.authenticate()

    def _get_config(self, kwargs):
        """
        Get a Config object for this API client.

        Broken out into a seperate method so that the test client can easily
        mock it up.
        """
        return Config(config_file=kwargs.pop('config_file', None),
                      env=kwargs.pop('env', None), overrides=kwargs)
