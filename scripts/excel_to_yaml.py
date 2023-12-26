import pandas
import time
import yaml
import excel_to_yaml_config
import os
import glob
import argparse
import logging
import sys
import re
from deepdiff import DeepDiff


def list_all_excel_files():
    ###loop all the input file and folder to determine if the input file or folder exist
    excel_files =[]
    for input in excel_to_yaml_config.config:
        if os.path.exists(input):
            if os.path.isfile(input):
                excel_files.append(input)
            else:
                #get all xlsx files from the folde
                if input.endswith('/') == False:
                    input = input+'/'
                files = glob.glob(input+'[!~]*.xlsx')
                for file in files:
                    excel_files.append(file)
        else:
            print('Input %s does not exist' % input)

    return excel_files

def determine_automation_type(excel_file):
    logging.info(f'Opening file {excel_file}. Trying to determine the automation Type')
    try:
        excel = pandas.read_excel(excel_file, None, engine='openpyxl')
        sheets_hosts = list(excel.keys())
        if 'apic_controller' in sheets_hosts:
            excel = pandas.read_excel(excel_file, 'apic_controller', engine='openpyxl')
            try:
                hostname = excel['apic_hostname'][0]
                ansible_host = str(excel['oob_ipv4'][0]).split('/')[0]
                ansible_user = None
                ansible_password = None
                if excel['username'].isnull()[0] == False:
                    ansible_user= excel['username'][0]
                if excel['password'].isnull()[0] == False:
                    ansible_password= excel['password'][0]
                automation_type = 'aci'
                return automation_type, hostname, ansible_host, ansible_user, ansible_password
            except:
                automation_type = None
                hostname = None
                ansible_host = None
                ansible_user = None
                ansible_password = None
                return automation_type, hostname, ansible_host, ansible_user, ansible_password
        else:
            try:
                excel = pandas.read_excel(excel_file, 'nd', engine='openpyxl')
                hostname = excel['nexus_dashboard'][0]
                ansible_host = str(excel['oob_ipv4'][0]).split('/')[0]
                ansible_user = None
                ansible_password = None
                if excel['username'].isnull()[0] == False:
                    ansible_user = excel['username'][0]
                if excel['password'].isnull()[0] == False:
                    ansible_password = excel['password'][0]
                automation_type = 'ndo'
                return automation_type, hostname, ansible_host, ansible_user, ansible_password
            except:
                automation_type = None
                hostname = None
                ansible_host = None
                ansible_user = None
                ansible_password = None
                return automation_type, hostname, ansible_host, ansible_user, ansible_password
    except:
        automation_type = None
        hostname = None
        ansible_host = None
        ansible_user = None
        ansible_password = None
        return automation_type, hostname, ansible_host, ansible_user, ansible_password

def reading_build_tasks(excel_file, only_yes=True):
    sheets = []
    logging.info(f'Opening file {excel_file}. Reading the Build Tasks. Mode only_yes: {only_yes}')
    excel = pandas.read_excel(excel_file, sheet_name='build_tasks', engine='openpyxl')
    if only_yes:
        for line in excel.index:
            if excel['include'][line] == 'yes':
                sheets.append(str(excel['input_worksheet'][line]))
    else:
        for line in excel.index:
            sheets.append(str(excel['input_worksheet'][line]))
    sheets = list(dict.fromkeys(sheets))
    return sheets

def excel_to_yaml(only_yes=True):

    all_yaml_data = {}
    excel_files = list_all_excel_files()

    for excel_file in excel_files:
        yaml_data = {}

        logging.info(msg=f'Excel File {excel_file}')
        automation_type, hostname, ansible_host, ansible_user, ansible_password = determine_automation_type(excel_file=excel_file)
        if automation_type:
            if automation_type not in all_yaml_data:
                all_yaml_data.update({automation_type : {}})
            host = {}
            logging.info(msg=f'Automation type: {automation_type}')
            host.update({hostname: {'ansible_host': ansible_host}})
            if ansible_user:
                host[hostname].update({'ansible_user': ansible_user})
                if ansible_password:
                    host[hostname].update({'ansible_password': ansible_password})



            #determine sheet to be read
            sheets = reading_build_tasks(excel_file=excel_file, only_yes=only_yes)


            for sheet in sheets:
                logging.info(f'Excel file {excel_file}. Sheet {sheet}')
                excel = pandas.read_excel(excel_file, sheet_name=sheet, engine='openpyxl')
                yaml_data.update({str(sheet): []})
                columns = list(excel.keys())
                for line in excel.index:
                    current_line = {}
                    if 'status' not in columns or excel['status'][line] != 'ignored':
                        for column in columns:
                            if excel[column].isnull()[line] == False:
                                current_line.update(
                                    {
                                        column: str(excel[column][line]).strip().lstrip()
                                    }
                                )
                            elif column == 'status':
                                current_line.update(
                                    {
                                        column: 'present'
                                    }
                                )
                            else:
                                current_line.update(
                                    {
                                        column: ''
                                    }
                                )
                        yaml_data[sheet].append(current_line)
            all_yaml_data[automation_type][hostname] = yaml_data
            all_yaml_data[automation_type][hostname]['ansible_config'] = host
        else:
            logging.error(f'Excel File {excel_file} failed. Verify tab nexus_dashboard or apic_hostname')

    return all_yaml_data


def create_ansible_hosts(data):
    apic_hosts = {
        'all': {
            'children': {
                'apic': {
                    'hosts': {},
                }
            }
        }
    }
    nd_hosts = {
        'all': {
            'children': {
                'nd': {
                    'hosts': {},
                },
            }
        }
    }
    for automation_type in data:
        for hostname in data[automation_type]:
            if automation_type == 'aci':
                apic_hosts['all']['children']['apic']['hosts'].update(data[automation_type][hostname]['ansible_config'])
            else:
                nd_hosts['all']['children']['nd']['hosts'].update(data[automation_type][hostname]['ansible_config'])
            data[automation_type][hostname].pop('ansible_config')

    if nd_hosts['all']['children']['nd']['hosts']:
        try:
            file = open(excel_to_yaml_config.ndo_output_dir + '/' + 'hosts.yml', 'w')
            yaml.dump(apic_hosts, file)
            file.close()
        except:
            logging.error(msg='Unable to Create the hosts file for NDO, aborting')
            sys.exit('Unable to Create the hosts file for NDO, aborting')

    if apic_hosts['all']['children']['apic']['hosts']:
        try:
            file = open(excel_to_yaml_config.aci_output_dir + '/' + 'hosts.yml', 'w')
            yaml.dump(apic_hosts, file)
            file.close()
        except:
            logging.error(msg='Unable to Create the hosts file for ACI, aborting')
            sys.exit('Unable to Create the hosts file for ACI, aborting')

    return data

def create_ansible_hosts_data(data):
    if 'aci' in data:
        output_dir = excel_to_yaml_config.aci_output_dir+'/host_vars/'
        for hostname in data['aci']:
            try:
                file = open(output_dir+hostname+'.yaml', 'w')
                yaml.dump(data['aci'][hostname], file)
            except:
                logging.error(msg='Unable to Create the host data file for ACI, aborting')
                sys.exit('Unable to Create the host data file for ACI, aborting')

    if 'ndo' in data:
        output_dir = excel_to_yaml_config.ndo_output_dir+'/host_vars/'
        for hostname in data['aci']:
            try:
                file = open(output_dir+hostname+'.yaml', 'w')
                yaml.dump(data['ndo'][hostname], file)
            except:
                logging.error(msg='Unable to Create the host data file for ACI, aborting')
                sys.exit('Unable to Create the host data file for NDO, aborting')

def create_ansible_hosts_data_full(data):
    folder = {
        'aci': excel_to_yaml_config.aci_output_dir,
        'ndo': excel_to_yaml_config.ndo_output_dir
    }
    if 'aci' in data:
        output_dir = folder['aci'] + '/host_vars/diff_mode/'
        if not os.path.exists(output_dir):
            os.mkdir(folder['aci']+'/host_vars/diff_mode/')
        for hostname in data['aci']:
            try:
                file = open(output_dir+hostname+'_full.yaml', 'w')
                yaml.dump(data['aci'][hostname], file)
            except:
                logging.error(msg='Unable to Create the host data file for ACI, aborting')
                sys.exit('Unable to Create the host data file for ACI, aborting')

    if 'ndo' in data:
        output_dir = folder['ndo'] + '/host_vars/diff_mode/'
        if not os.path.exists(output_dir):
            os.mkdir(folder['ndo']+'/host_vars/diff_mode/')
        for hostname in data['ndo']:
            try:
                file = open(output_dir+hostname+'_full.yaml', 'w')
                yaml.dump(data['ndo'][hostname], file)
            except:
                logging.error(msg='Unable to Create the host data file for ACI, aborting')
                sys.exit('Unable to Create the host data file for NDO, aborting')

def normal_mode():
    yaml_data = excel_to_yaml()
    yaml_data = create_ansible_hosts(data=yaml_data)
    create_ansible_hosts_data(data=yaml_data)


def update_status_file(hostname, sheets, automation_type):
    folder = {
        'aci': excel_to_yaml_config.aci_output_dir,
        'ndo': excel_to_yaml_config.ndo_output_dir
    }
    pattern_values_changed = r"root\[(\d+)\]\['(\w+)'\]"

    ###load full data vars:
    try:
        file = open(folder[automation_type]+'/host_vars/diff_mode/'+hostname+'_full.yaml')
        current_yaml_data = yaml.safe_load(file)
    except:
        sys.exit("Failed to load current yaml data, aborting")
    ####check if the current status file exist
    if os.path.exists(folder[automation_type]+'/host_vars/diff_mode/'+hostname+'.yaml'):
        file = open(folder[automation_type]+'/host_vars/diff_mode/'+ hostname+'.yaml')
        status_yaml = yaml.safe_load(file)
        file.close()
        for sheet in sheets:
            if status_yaml and sheet in status_yaml:
                diff = DeepDiff(status_yaml[sheet], current_yaml_data[sheet], ignore_order=True)
                if diff:
                    if 'iterable_item_added' in diff:
                        for item in diff['iterable_item_added']:
                            status_yaml[sheet].append(diff['iterable_item_added'][item])
                    if 'values_changed' in diff:
                        for item in diff['values_changed']:
                            re_result = re.search(pattern_values_changed, item)
                            index = int(re_result.group(1))
                            field = re_result.group(2)
                            status_yaml[sheet][index][field] = diff['values_changed'][item]['new_value']
            else:
                status_yaml[sheet] = current_yaml_data[sheet]
        file = open(folder[automation_type] + '/host_vars/diff_mode/' + hostname + '.yaml', 'w')
        yaml.dump(status_yaml, file)
        file.close()

    else:
        diff_yaml = {}
        ###check if the folder diff mode folder exist, if not exist create
        if not os.path.exists(folder[automation_type]+'/host_vars/diff_mode/'):
            os.mkdir(folder[automation_type]+'/host_vars/diff_mode/')
        for sheet in sheets:
            diff_yaml[sheet] = current_yaml_data[sheet]
        #write diff file
        file = open(folder[automation_type]+'/host_vars/diff_mode/'+hostname+'.yaml','w')
        yaml.dump(diff_yaml, file)
        file.close()

def diff_mode():
    pattern = r"root\['(.*?)'\]"
    pattern_values_changed = r"root\['(\w+)'\]\[(\d+)\]"

    yaml_data = excel_to_yaml(only_yes=False)
    yaml_data = create_ansible_hosts(data=yaml_data)
    diff_dict = {}
    folder = {
        'aci': excel_to_yaml_config.aci_output_dir,
        'ndo': excel_to_yaml_config.ndo_output_dir
    }
    if 'aci' in yaml_data:
        diff_dict.update({'aci': {}})
        for hostname in yaml_data['aci']:
            diff_dict['aci'].update({hostname: {}})
            if os.path.exists(folder['aci']+'/host_vars/diff_mode/'+hostname+'.yaml'):
                file = open(folder['aci']+'/host_vars/diff_mode/'+hostname+'.yaml')
                previous_data = yaml.safe_load(file)
                diff = DeepDiff(previous_data, yaml_data['aci'][hostname], ignore_order=True)
                if 'dictionary_item_added' in diff:
                    for item in diff['dictionary_item_added']:
                        key = re.search(pattern, item)[1]
                        diff_dict['aci'][hostname][key] = yaml_data['aci'][hostname][key]
                if 'values_changed' in diff:
                    for item in diff['values_changed']:
                        re_result = re.search(pattern_values_changed, item)
                        key = re_result.group(1)
                        index = int(re_result.group(2))
                        if key not in diff_dict['aci'][hostname]:
                            diff_dict['aci'][hostname][key] = []
                        diff_dict['aci'][hostname][key].append(yaml_data['aci'][hostname][key][index])
                if 'iterable_item_added' in diff:
                    for item in diff['iterable_item_added']:
                        key = re.search(pattern, item)[1]
                        if key not in diff_dict['aci'][hostname]:
                            diff_dict['aci'][hostname][key] = []
                        diff_dict['aci'][hostname][key].append(diff['iterable_item_added'][item])
            else:
                logging.error(msg=f'Diff mode for {hostname} failed. No previous configuration found. Running in full mode')
                diff_dict['aci'][hostname] = yaml_data['aci'][hostname]
                # file = open(folder+hostname+'.yaml', 'w')
                # # yaml.dump(yaml_data['aci'][hostname], file)
                # # file.close()


    create_ansible_hosts_data(data=diff_dict)
    create_ansible_hosts_data_full(data=yaml_data)


def main():
    start = time.time()
    logging.basicConfig(filename='excel_to_yaml.log', filemode='a', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
    parser = argparse.ArgumentParser(description="Script to Update and Fix the Excel File.")
    parser.add_argument("--mode", required=False, choices=['normal', 'diff_mode','update_status_file'], default='normal', help="Operation mode")
    parser.add_argument("--hostname", type=str, required=False, help="current_hostname")
    parser.add_argument("--sheets", required=False, type=str, nargs='+', help="list of sheets")
    parser.add_argument("--automation_type", required=False, choices=['aci', 'ndo'], help="Automation Type")

    args = parser.parse_args()
    if args.mode == 'normal':
        logging.info(msg='Running in normal mode')
        normal_mode()
        logging.info(msg='Normal mode completed')
    elif args.mode == 'diff_mode':
        logging.info(msg='Running in diff mode')
        diff_mode()
        logging.info(msg='Diff mode completed')
    else:
        logging.info(msg='Running in update status file mode')
        update_status_file(hostname=args.hostname, sheets=args.sheets, automation_type=args.automation_type)
        logging.info(msg='Update status file mode completed')

    logging.info(msg="Elapsed time %s" % str(time.time()-start))

if __name__ == '__main__':
    main()