import openstack.admin
import openstack.compute
import openstack.auth


auth = openstack.auth.Auth(management_url='http://localhost:8080/v2.0/token')
token = auth.tokens.create('1234', 'joeuser', 'secrete')

admin = openstack.admin.Admin(username='admin',
                              auth_token=token.id,
                              auth_url='http://localhost:8774/v1.1/',
                              management_url='http://localhost:8774/v1.1/')

print admin.projects.list()

admin.projects.create('test', 'joeuser')
admin.projects.delete('test')
#admin.projects.get('admin')

print admin.projects.list()


compute = openstack.compute.Compute(username='admin',
                                    auth_token=token.id,
                                    auth_url='http://localhost:8774/v1.1/',
                                    management_url='http://localhost:8774/v1.1/')

print compute.images.list()
