import pandas
import time
import yaml
import excel_to_yaml_config
import os
import glob
import argparse
import logging
import sys


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

def normal_mode():
    yaml_data = excel_to_yaml()
    yaml_data = create_ansible_hosts(data=yaml_data)
    create_ansible_hosts_data(data=yaml_data)


def update_status_file(hostname, sheets):
    print(hostname)

def diff_input():
    print('diff')

def main():
    start = time.time()
    logging.basicConfig(filename='excel_to_yaml.log', filemode='a', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
    parser = argparse.ArgumentParser(description="Script to Update and Fix the Excel File.")
    parser.add_argument("--mode", required=False, choices=['normal', 'diff_input','update_status_file'], default='normal', help="Operation mode")
    parser.add_argument("--hostname", type=str, required=False, help="current_hostname")
    parser.add_argument("--sheets", required=False, type=str, nargs='+', help="list of sheets")

    args = parser.parse_args()
    if args.mode == 'normal':
        logging.info(msg='Running in normal mode')
        normal_mode()
        logging.info(msg='Normal mode completed')
    elif args.mode == 'diff_input':
        diff_input()
    else:
        update_status_file(hostname=args.hostname, sheets=args.sheets)

    logging.info(msg="Elapsed time %s" % str(time.time()-start))

if __name__ == '__main__':
    main()