import pandas
import time
import yaml
import numpy
import excel_to_yaml_config


def excel_to_yaml():
    apic_dir = []
    mso_dir = []
    apic_hosts = {
        'all': {
            'children': {
                'apic': {
                    'hosts': {},
                }
            }
        }
    }
    mso_hosts = {
        'all': {
            'children': {
                'mso': {
                    'hosts': {},
                },
            }
        }
    }
    for device in excel_to_yaml_config.config:
        yaml_data = {}
        sheets = []
        print('Opening %s' % device['excel'])
        excel = pandas.read_excel(device['excel'], None, engine='openpyxl')
        sheets_hosts = list(excel.keys())
        if 'apic_controller' in sheets_hosts:
            excel = pandas.read_excel(device['excel'], 'apic_controller', engine='openpyxl')
            apic_dir.append(device['output_dir'])
            host = excel['apic_hostname'][0]
            if excel['apic_hostname'].isnull()[0] == False:
                apic_hosts['all']['children']['apic']['hosts'][excel['apic_hostname'][0]] = {
                    'ansible_host': str(excel['oob_ipv4'][0]).split('/')[0]
                }
                if excel['username'].isnull()[0] == False:
                    apic_hosts['all']['children']['apic']['hosts'][excel['apic_hostname'][0]].update(
                        {
                            'ansible_user': excel['username'][0]
                        }
                    )
                if excel['password'].isnull()[0] == False:
                    apic_hosts['all']['children']['apic']['hosts'][excel['apic_hostname'][0]].update(
                        {
                            'ansible_password': excel['password'][0]
                        }
                    )
        elif 'mso_controller' in sheets_hosts:
            excel = pandas.read_excel(device['excel'], 'mso_controller', engine='openpyxl')
            mso_dir.append(device['output_dir'])
            host = excel['mso_hostname'][0]
            if excel['mso_hostname'].isnull()[0] == False:
                mso_hosts['all']['children']['mso']['hosts'][excel['mso_hostname'][0]] = {
                    'ansible_host': str(excel['oob_ipv4'][0]).split('/')[0]
                }
                if excel['username'].isnull()[0] == False:
                    mso_hosts['all']['children']['mso']['hosts'][excel['mso_hostname'][0]].update(
                        {
                            'ansible_user': excel['username'][0]
                        }
                    )
                if excel['password'].isnull()[0] == False:
                    mso_hosts['all']['children']['mso']['hosts'][excel['mso_hostname'][0]].update(
                        {
                            'ansible_password': excel['password'][0]
                        }
                    )

        print('Opening %s' % device['excel'])
        excel = pandas.read_excel(device['excel'], sheet_name='build_tasks', engine='openpyxl')
        for line in excel.index:
            if excel['include'][line] == 'yes':
                sheets.append(str(excel['input_worksheet'][line]))
        sheets = numpy.unique(sheets)

        for sheet in sheets:
            print('Sheet: %s' %sheet)
            excel = pandas.read_excel(device['excel'], sheet_name=sheet, engine='openpyxl')
            yaml_data.update({str(sheet):[]})
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

        file = open(device['output_dir']+'/host_vars/'+host+'.yaml', 'w')
        yaml.dump(yaml_data, file)
        file.close()
    for apic in apic_dir:
        file = open(apic + '/' + 'hosts.yml', 'w')
        yaml.dump(apic_hosts, file)
        file.close()
    for mso in mso_dir:
        file = open(mso + '/' + 'hosts.yml', 'w')
        yaml.dump(mso_hosts, file)
        file.close()

def main():
    start = time.time()
    excel_to_yaml()
    print("Elapsed time %s" % str(time.time()-start))

if __name__ == '__main__':
    main()