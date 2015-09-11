#!/usr/bin/python

__author__ = 'ChakruHP'

DOCUMENTATION = '''
---
module: ov_server
short_description: Manage servers lifecycle using OneView Server profiles using a server profile template.
Selects Server Hardware automatically based on SHT
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
  server_template:
    required: true
    default: null
  name:
    required: true
    default: null
  state:
    default: present
    choices: ['present', 'powered_off', 'absent', 'powered_on', 'restarted']


Example :


- ov_server:
    oneview_host: <ip>
    username: user
    password: pass
    server_template: Compute-node-template
    name: <server-profile-name>

'''


import hpOneView as hpov
from hpOneView.exceptions import *


'''
update the server to match the template
'''


def update_profile(con, server_profile, server_template):
    changed = False
    servers= hpov.servers(con)
    if (server_profile['serverProfileTemplateUri'] != server_template['uri']):
        server_profile['serverProfileTemplateUri'] = server_template['uri']
        server_profile = servers.update_server_profile(server_profile)
        changed = True

    if (server_profile['templateCompliance'] != 'Compliant'):
        servers.update_server_profile_from_template(server_profile)
        changed = True

    return changed


def create_profile(con, server_name, server_template):
    servers= hpov.servers(con)
    # find servers that have no profile, powered off mathing SHT
    SHT = con.get(server_template['serverHardwareTypeUri'])
    server_hardware = servers.get_available_servers(server_hardware_type=SHT)

    # pick the first available, create profile
    server_profile = servers.new_server_profile_from_template(server_template)
    server_profile['name'] = server_name

    # TODO: uncomment temp hack to speed up dev/testing, let profiles remain unassigned
    #server_profile['serverHardwareUri'] = server_hardware['targets'][0]['serverHardwareUri']

    servers.create_server_profile(server_profile)


def delete_profile(con, server_profile):
    servers= hpov.servers(con)
    servers.remove_server_profile(server_profile)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            oneview_host=dict(required=True, type='str'),
            username=dict(required=True, type='str'),
            password=dict(required=True, type='str'),
            server_template=dict(required=True, type='str'),
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
            name=dict(required=True, type='str'),
            server_hardware=dict(required=False, type='str', default=None)))

    oneview_host = module.params['oneview_host']
    credentials = {'userName': module.params['username'], 'password': module.params['password']}
    server_template_name = module.params['server_template']
    server_name = module.params['name']
    state = module.params['state']

    try:
        # TODO: Need to add a OV utils to module_utils
        con = hpov.connection(oneview_host)

        con.login(credentials)
        servers = hpov.servers(con)
        server_template = servers.get_server_profile_template_by_name(server_template_name)

        # check if the server already exists - edit it to match the desired state
        server_profile = servers.get_server_profile_by_name(server_name)
        if server_profile:
            if state == 'present':
                changed = update_profile(con, server_profile, server_template)
                module.exit_json(
                    changed=changed, msg='Updated profile'
                )
            elif state == 'absent':
                delete_profile(con, server_profile)
                module.exit_json(
                    changed=True, msg='Deleted profile'
                )
            # TODO: Implement rest of states

        # we didnt find an existing one, so we create a profile
        create_profile(con, server_name, server_template)

        module.exit_json(
               changed=True, msg='Created profile'
            )
    except Exception, e:
        module.fail_json(msg=e.message)


from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
