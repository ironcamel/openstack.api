from openstack.api import base


class Project(base.Resource):
    def __repr__(self):
        return "<Project: %s>" % self.name

    def delete(self):
        """
        Delete this group.
        """
        self.manager.delete(self)


class ProjectManager(base.ManagerWithFind):
    resource_class = Project

    def list(self):
        """Get a list of all groups."""
        return self._list("/admin/projects", "projectSet")

    def get(self, project_id):
        """Get an Project."""
        return self._get("/admin/projects/%s" % project_id, "project")

    def create(self, name, manager_user, description=None, member_users=None):
        """Create a new Project."""
        body = {"project": {"name": name, 'manager_user': manager_user}}
        
        return self._create('/admin/projects', body, "project")

    def delete(self, project_id):
        """ Delete a group."""
        self._delete("/admin/projects/%s" % (project_id))

    def update(self, project, name, manager_user, description=None):
        """
        Update the name or the password for a server.

        :param server: The :class:`Server` (or its ID) to update.
        :param name: Update the server's name.
        :param password: Update the root password.
        """

        body = {"project": {'name': name, 'manager_user': manager_user}}
        if description:
            body["project"]["description"] = description
        self._update("/projects/%s" % base.getid(project), body)
