import openstack.admin
import openstack.compute
import openstack.auth
import openstack.extras
import random
import sys

if len(sys.argv) > 1:
    host = sys.argv[1]
else:
    host = 'localhost'


auth = openstack.auth.Auth(management_url='http://%s:8080/v2.0/' % host)
token = auth.tokens.create('1234', 'joeuser', 'secrete')

admin_token = auth.tokens.create('1234', 'admin', 'secrete')
accounts = openstack.extras.Account(auth_token=admin_token.id,
        management_url='http://%s:8081/v2.0' % host)

extras = openstack.extras.Extras(auth_token=token.id,
                                 auth_url='http://%s:8774/v1.1/' % host,
                                 management_url='http://%s:8774/v1.1/' % host)

admin = openstack.admin.Admin(auth_token=token.id,
                              auth_url='http://%s:8774/v1.1/' % host,
                              management_url='http://%s:8774/v1.1/' % host)

compute = openstack.compute.Compute(auth_token=token.id,
                                    auth_url='http://%s:8774/v1.1/' % host,
                                    management_url='http://%s:8774/v1.1/' % host)
#flavors = admin.flavors.list()
#services =  admin.services.list()
#print services
#for s in services:
#    print s._info
#    s.update(False)


#admin.flavors.delete(405)
#flavor = admin.flavors.create('', '', '', '', '')
#flavor.delete(True)

if True:
    print "%d tenants" % len(accounts.tenants.list())
    t = accounts.tenants.create('project:%d' % random.randint(0, 10000))
    print 'created %s' % t
    print "%d tenants" % len(accounts.tenants.list())
    t.delete()
    print "after delete: %d tenants" % len(accounts.tenants.list())

#console = extras.consoles.create(servers[0].id, 'vnc')
#print console.output

#print compute.servers.list()

if False:
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
