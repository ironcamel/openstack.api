import openstack.admin
import openstack.compute
import openstack.auth
import openstack.extras


auth = openstack.auth.Auth(management_url='http://localhost:8080/v2.0/')
token = auth.tokens.create('1234', 'joeuser', 'secrete')

extras = openstack.extras.Extras(auth_token=token.id,
                                 auth_url='http://localhost:8774/v1.1/',
                                 management_url='http://localhost:8774/v1.1/')

admin = openstack.admin.Admin(auth_token=token.id,
                              auth_url='http://localhost:8774/v1.1/',
                              management_url='http://localhost:8774/v1.1/')

compute = openstack.compute.Compute(auth_token=token.id,
                                    auth_url='http://localhost:8774/v1.1/',
                                    management_url='http://localhost:8774/v1.1/')
flavors = admin.flavors.list()
for f in flavors:
    print f._info


#admin.flavors.delete(405)
flavor = admin.flavors.create('', '', '', '', '')
#flavor.delete(True)

#console = extras.consoles.create(servers[0].id, 'vnc')
#print console.output

#print compute.servers.list()

if False:
    admin.projects.create('test', 'joeuser')
    admin.projects.delete('test')

    print admin.projects.list()
    print compute.images.list()
