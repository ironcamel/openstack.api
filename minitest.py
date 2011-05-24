import openstack.admin
admin = openstack.admin.Admin(username='admin', auth_token='887665443383838',auth_url='http://localhost:8774/v1.1/',management_url='http://localhost:8774/v1.1/')

print admin.projects.list()
