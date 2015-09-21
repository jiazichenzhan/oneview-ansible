#!/usr/bin/python

__author__ = 'ChakruHP'

DOCUMENTATION = '''
---
module: ov_appliance_settings
short_description: Manages OV appliance settings, FTS etc.

options:
  accept_eula:
    required: false
    default: true
  username:
      required: true
  password:
    description:
    required: true
  ipv4_type:
    required: false
  initial_ip:
    required: true
  ipv4_address:
    required: false
  ipv4_subnet:
    required: false
  ipv4_gateway:
    required: false
  hostname:
    required: true
  domain_name:
    required: true


Example :


- ov_appliance_settings:
    initial_ip: <dhcp assigned IP >
    username: user
    password: pass
    ipv4_type: <DHCP|STATIC>
    ipv4_address: <blank if DHCP>
    hostname : <fqdn>
    domain_name: <domain name>
    ipv4_subnet: <subnet>
    ipv4_gateway : <gateway>


'''


import hpOneView as hpov
from hpOneView.exceptions import *

import time



def changeDefaultPassword(con, newPassword):
    request = {'userName': 'Administrator',
               'oldPassword':'admin',
               'newPassword':newPassword}
    con.post(hpov.common.uri['users'] + '/changePassword', request)

def login(con, credential):
    # Login with givin credentials

    try:
        con.login(credential)
        return True

    except HPOneViewException as e:
        #TODO: Need to ignore the failure if the appliance still has the default initial password
        return False


def main():
    module = AnsibleModule(
        argument_spec=dict(
            initial_ip=dict(required=True, type='str'),
            username=dict(required=True, type='str'),
            password=dict(required=True, type='str'),
            ipv4_type=dict(required=True, choices=['DHCP', 'STATIC'], type='str'),
            ipv4_address=dict(required=False, type='str'),
            hostname =dict(required=True, type='str'),
            domain_name=dict(required=False, type='str'),
            ipv4_subnet=dict(required=False, type='str'),
            ipv4_gateway = dict(required= False, type='str' )

        ))

    initial_ip = module.params['initial_ip']
    credentials = {'userName': module.params['username'], 'password': module.params['password']}
    ipv4_type = module.params['ipv4_type']
    ipv4_address= module.params['ipv4_address']
    if ipv4_address == None:
        ipv4_address = initial_ip

    hostname = module.params['hostname']
    domain_name = module.params['domain_name']
    ipv4_subnet = module.params['ipv4_subnet']
    ipv4_gateway = module.params['ipv4_gateway']

    changed = False
    try:

        # Is FTS really required? Check EULA, attempt logging in to ipv4 address using creds
        # if creds dont work (still with default creds) and eula status shows not accepted,
        # accept eula
        # change default password from admin to what was passed here
        # do initial appliance network config

        tries = 0
        while tries < 20:
            try:
                con = hpov.connection(initial_ip)
                # if appliance is starting up, wait for startup to complete
                sts = hpov.settings(con)
                startup_progress = sts.get_startup_progress()
                complete = startup_progress ['complete']
                total = startup_progress ['total']
                #TODO handle timeout
                while startup_progress ['complete'] < startup_progress ['total']:
                    time.sleep(15)
                    startup_progress =  sts.get_startup_progress()
                break
            except Exception, e:
                time.sleep(60)
                tries += 1
        else:
            raise Exception("OneView did not start...")


        if (con.get_eula_status() is False and login(con, credentials)):
            # FTS not needed. nothing to do
            changed = False
        else:
            con.set_eula('yes')
            changeDefaultPassword(con, credentials['password'])
            login(con, credentials)
            settings=hpov.settings(con)
            network_settings = settings.get_appliance_network_interfaces()

            network_settings['applianceNetworks'][0]['hostname'] = hostname
            network_settings['applianceNetworks'][0]['ipv4Type'] = ipv4_type
            network_settings['applianceNetworks'][0]['domainName'] = domain_name
            network_settings['applianceNetworks'][0]['searchDomains'] = [domain_name]
            network_settings['applianceNetworks'][0].pop('virtIpv4Addr', None)
            network_settings['applianceNetworks'][0]['interfaceName']=''
            network_settings['applianceNetworks'][0]['aliasDisabled']=True

            if ipv4_type == 'DHCP':
                network_settings['applianceNetworks'][0]['app1Ipv4Addr']= None
                network_settings['applianceNetworks'][0]['ipv4Subnet']= None
                network_settings['applianceNetworks'][0]['ipv4Gateway']= None
            else:
                network_settings['applianceNetworks'][0]['app1Ipv4Addr']= ipv4_address
                network_settings['applianceNetworks'][0]['ipv4Subnet']= ipv4_subnet
                network_settings['applianceNetworks'][0]['ipv4Gateway']= ipv4_gateway

            settings.set_appliance_network_interface(network_settings)
            #wait till we can login before proceeding
            con = hpov.connection(ipv4_address)
            tries  = 0
            for tries in [1-5]:
                try:
                    login(con, credentials)
                    break
                except:
                    time.sleep(15)

            time.sleep(30)
            changed = True

        module.exit_json(changed=changed)

    except Exception, e:
        module.fail_json(msg= e.message)


from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
