import openstack.admin
import openstack.compute
admin = openstack.admin.Admin(username='admin', auth_token='887665443383838',auth_url='http://localhost:8774/v1.1/',management_url='http://localhost:8774/v1.1/')

print admin.projects.list()

admin.projects.create('test', 'joeuser')
admin.projects.delete('test')
#admin.projects.get('admin')

print admin.projects.list()


compute = openstack.compute.Compute(username='admin', auth_token='887665443383838',auth_url='http://localhost:8774/v1.1/',management_url='http://localhost:8774/v1.1/')

print compute.images.list()
