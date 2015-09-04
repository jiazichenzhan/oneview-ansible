#!/usr/bin/python

__author__ = 'ChakruHP'

DOCUMENTATION = '''
---
module: ov_server_template
short_description: Manages oneview server profile templates lifecycle
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
  state:
    default: present
    choices: ['present', 'absent']
  server_hardware_type:
    required: true
  firmware_baseline:
    default: null
    required: false
  local_storage:
    default: null
    required : false



Example:
- ov_server_template
    name: Compute-node-template
    oneview_host: <ip>
    username: <user>
    password: <pass>
    server_hardware_type: <Server Hardware Type name from OneView>
    firmware_baseline: <SPP Version as seen in OneView FW Bundles, optional>
    local_storage:
      0:  # RAID controller slot number
        mode: RAID
        initialize: true
        logical_drives:
          Boot volume:
            raid_level: RAID1
            bootable: true
            drive_technology: SasHdd
            num_drives: 2
          Data volume:
            raid_level : RAID6
            num_drives: 4


'''

import hpOneView as hpov
from hpOneView.exceptions import *


'''
update the template to match desired config
'''


def update_local_storage_config(module, server_template):
    '''
    local_storage:
       controller_0:
          slot_number : 0  #RAID controller slot number
          mode: RAID
          initialize: true
          logical_drives:
            Boot volume:
              raid_level: RAID1
              bootable: true
              drive_technology: SAS
              num_drives: 2
             Data volume:
              raid_level : RAID6
              num_drives: 4'''
    local_storage_config = {}

    # TODO -simpler way to do this? just mirror OV datamodel in yaml, and replace keys, adjust defaults?

    changed = False
    controllers_spec = module.params['local_storage']
    if controllers_spec:
        controllers_config =  []
        for controller_num in controllers_spec:
            slot_number = controller_num
            controller_config_spec = controllers_spec[slot_number]
            mode = controller_config_spec.get('mode', 'RAID')
            initialize = controller_config_spec.get('initialize', False)
            drives_spec = controller_config_spec['logical_drives']
            drives_config = []
            for drive_name in drives_spec:
                drive_spec = drives_spec[drive_name]
                bootable = drive_spec.get('bootable', False)
                raid_level = drive_spec['raid_level']
                drive_technology = drive_spec.get('drive_technology', None)
                num_drives = drive_spec['num_drives']
                drive_config = {'driveName': drive_name,
                                'raidLevel': raid_level,
                                'bootable': bootable,
                                'numPhysicalDrives': num_drives,
                                'driveTechnology': drive_technology
                                }
                drives_config.append(drive_config)
            controller_config = {'slotNumber':slot_number,
                                 'managed': True,
                                 'mode': mode,
                                 'initialize': initialize,
                                 'logicalDrives': drives_config}
            controllers_config.append(controller_config)
        server_template['localStorage'] = {'controllers':controllers_config}


        changed = True
    # module.fail_json(msg= server_template)

    return changed

def get_spp(con, firmware_baseline):
    spp = None
    settings = hpov.settings(con)
    spps = settings.get_spps()
    if spps:
        spp = (spp  for spp in spps if spp['version'] == firmware_baseline).next()
    return spp


def update_profile_template(con, module):
    changed = False
    server_template_name = module.params['name']
    firmware_baseline = module.params['firmware_baseline']
    # TODO: .. and a lot more attributes

    servers = hpov.servers(con)
    server_template = servers.get_server_profile_template_by_name(server_template_name)

    current_firmware_settings = server_template['firmware']
    if firmware_baseline:
        spp = get_spp(con, firmware_baseline)

        if spp:
            if (current_firmware_settings == None or
                current_firmware_settings['firmwareBaselineUri'] != spp['uri']):

                firmware = {'firmwareBaselineUri': spp['uri'],
                            'firmwareInstallType': 'FirmwareOnlyOfflineMode',
                            'forceInstallFirmware': False,
                            'manageFirmware': True
                            }

                server_template['firmware'] = firmware

    update_local_storage_config(module, server_template)
    servers= hpov.servers(con)
    servers.update_server_profile_template(server_template)
    changed = True

    return changed


def create_profile_template(con, module):
    server_template_name = module.params['name']
    firmware_baseline = module.params['firmware_baseline']
    server_hardware_type_name = module.params['server_hardware_type']

    servers = hpov.servers(con)
    server_hardware_type = (SHT for SHT in servers.get_server_hardware_types() if SHT['name'] == server_hardware_type_name).next()

    server_template = {'type': 'ServerProfileTemplateV1',
                       'name': server_template_name,
                       'serverHardwareTypeUri': server_hardware_type['uri'],
                       'macType': 'Physical',
                       'serialNumberType':'Physical',
                       'wwnType':'Physical'
                       }

    if firmware_baseline:
        spp = get_spp(con, firmware_baseline)
        if spp:
            firmware = {'firmwareBaselineUri': spp['uri'],
                        'firmwareInstallType': 'FirmwareOnlyOfflineMode',
                        'forceInstallFirmware': False,
                        'manageFirmware': True
                        }
            server_template['firmware'] = firmware

    update_local_storage_config(module, server_template)

    servers.create_server_profile_template(server_template)


def delete_profile_template(con, server_profile_template):
    servers= hpov.servers(con)
    servers.remove_server_profile_template(server_profile_template)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(required=True, type='str'),
            oneview_host=dict(required=True, type='str'),
            username=dict(required=True, type='str'),
            password=dict(required=True, type='str'),
            state=dict(
                required=False,
                choices=[
                    'present',
                    'absent',
                ],
                default='present'),
            server_hardware_type=dict(required=True, type='str', default=None),
            firmware_baseline=dict(required=False, type='str', default=None),
            local_storage=dict(required=False, type='dict', default=None))

        )

    server_template_name = module.params['name']
    oneview_host = module.params['oneview_host']
    credentials = {'userName': module.params['username'], 'password': module.params['password']}
    # try:
    con = hpov.connection(oneview_host)
    con.login(credentials)

    servers = hpov.servers(con)
    server_template = servers.get_server_profile_template_by_name(server_template_name)
    changed  = False
    if server_template:
        changed = update_profile_template(con, module)
    else:
        create_profile_template(con, module)
        changed = True

    module.exit_json(changed=changed)
    # except Exception, e:
    #    module.fail_json(msg=e.message)

from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()


