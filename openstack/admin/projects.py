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

    def get(self, group):
        """Get an Project."""
        return self._get("/admin/projects/%s" % base.getid(group), "Projects")

    def create(self, name, manager_user, description=None, member_users=None):
        """Create a new Project."""
        data = {"project": {"name": name, 'manager_user': manager_user}}
        return self._create('/admin/projects', data, "project")

    def delete(self, group):
        """ Delete a group."""
        self._delete("/admin/projects/%s" % base.getid(group))
