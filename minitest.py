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
#flavors = admin.flavors.list()
#services =  admin.services.list()
#print services
#for s in services:
#    print s._info
#    s.update(False)


#admin.flavors.delete(405)
#flavor = admin.flavors.create('', '', '', '', '')
#flavor.delete(True)

#console = extras.consoles.create(servers[0].id, 'vnc')
#print console.output

#print compute.servers.list()

if True:
    try:
        project = admin.projects.create('test', 'joeuser', 'desc')
    except:
        admin.projects.delete('test')
        pass

    project.update('joeuser', 'desc2')

    for p in admin.projects.list():
        print p._info
    admin.projects.delete('test')
    #print compute.images.list()
