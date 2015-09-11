#!/usr/bin/python

__author__ = 'ChakruHP'

DOCUMENTATION = '''
---
module: ov_server_hardware
short_description: Manage servers hardware lifecycle
options:
  name:
    required : true
    default : null
  oneview_host:
      required: true
      default: null
      aliases: []
  username:
    default: null
    required: true
  password:
    description:
    required: true
    default: null
  ip_address:
    description:
    required: true
  state:
    default: present
    choices: ['present', 'powered_off', 'absent', 'powered_on', 'restarted']


Example:

Import a rack mount server

- ov_server_hardware:
    oneview_host: 16.125.74.211
    username: Administrator
    password: hpvse123
    ilo_ip_address: "{{ inventory_hostname }}"
    ilo_user: dcs
    ilo_password: dcs

To remove server, add state: absent.


'''

import hpOneView as hpov
from hpOneView.exceptions import *


'''
update the server to match the template
'''


def import_server_hardware(con, module):
    ip_address = module.params['ilo_ip_address']
    ilo_user = module.params['ilo_user']
    ilo_password = module.params['ilo_password']
    license = module.params['license']
    mode= module.params['mode']
    force= module.params['force']
    server = hpov.make_server_dict(ip_address,ilo_user, ilo_password, force ,license, mode)
    srv = hpov.servers(con)
    return srv.add_server(server)


def remove_server_hardware(con, module, server):
    force= module.params['force']
    srv = hpov.servers(con)
    srv.delete_server(server, force)


def gather_nic_info(module):
    # {'iLO': 'mac-addr', nic: [ nic mac addrs] }

    # TODO - ideally this info should come from oneview, but oneview discovers this info only for blades.
    # for now, gather this from iLO directly

    ip_address = module.params['ilo_ip_address']
    import http.client
    con = http.client.HTTPSConnection(ip_address)
    con.request('GET', '/xmldata?item=all')
    resp = con.getresponse()

    tempbytes = resp.read()
    tempbody = tempbytes.decode('utf-8')
    import xml.etree.ElementTree as ET
    root = ET.fromstring(tempbody)
    nic_descs = root.findall('./HSI/NICS/NIC/DESCRIPTION')
    nic_mac_addrs = root.findall('./HSI/NICS/NIC/MACADDR')

    nic_descs = [nic.text for nic in nic_descs]
    nic_mac_addrs = [nic.text for nic in nic_mac_addrs]

    # Looks like this list has first he iLO nic followed by server nics.. need to validate this
    network_adapter_info = {'iLO':nic_mac_addrs[0], 'NICs':[nic_mac_addrs[1:]]}
    return network_adapter_info


def gather_facts(module, server_hardware):
    #return server serial number/UUID/nics
    nic_info = gather_nic_info(module)
    sh_facts = { 'serial_num':server_hardware['serialNumber'],
                 'uuid': server_hardware['uuid'],
                 'model' : server_hardware['model'],
                 'iLO': nic_info['iLO'],
                 'nics':nic_info['NICs']}

    return sh_facts

def main():
    module = AnsibleModule(
        argument_spec=dict(
            oneview_host=dict(required=True, type='str'),
            username=dict(required=True, type='str'),
            password=dict(required=True, type='str'),
            ilo_ip_address=dict(required=True, type='str'),
            ilo_user=dict(required=True, type='str'),
            ilo_password=dict(required=True, type='str'),
            state=dict(
                required=False,
                choices=[
                    'powered_on',
                    'powered_off',
                    'present',
                    'absent',
                    'restarted'
                ],
                default='present'),
            force=dict(required=False, default=False),
            license=dict(required=False, choice = ['OneView', 'OneViewNoiLO', 'OneViewStandard'],  default='OneView'),
            mode= dict(required=False, choices=['Managed', 'Monitored'], default='Managed'))
            )

    oneview_host = module.params['oneview_host']
    credentials = {'userName': module.params['username'], 'password': module.params['password']}
    ip_address = module.params['ilo_ip_address']
    state = module.params['state']


    try:
        con = hpov.connection(oneview_host)

        con.login(credentials)
        srv = hpov.servers(con)

        matched_server = None
        # check if server is already managed
        # TODO: oneview should really have a way to search based on IP...
        servers = srv.get_servers()
        for server in servers:
            # we could be adding by IP address or host name...
            if server['mpHostInfo']['mpHostName'] in ip_address:
                matched_server = server
                break
            ips = server['mpHostInfo']['mpIpAddresses']
            for ip in ips:
                if ((ip['type'] in ('Static', 'DHCP')) and
                     ip['address'] == ip_address):
                    matched_server = server
                    break

        facts = {}

        if state == 'present':
            if matched_server is None:
                added_server = import_server_hardware(con, module)
                facts = gather_facts(module, added_server)
                module.exit_json(
                  changed=True,msg = 'Added server', ansible_facts = facts
                    )
            else:
                facts = gather_facts(module, matched_server)
                module.exit_json(
                    changed=False,  ansible_facts = facts
                    )
        elif state == 'absent' and matched_server != None:
            remove_server_hardware(con, module, matched_server)
            module.exit_json(
               changed=True, msg = 'Removed Server', ansible_facts = facts
            )
    except Exception, e:
        module.fail_json(msg=e.message)


from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
