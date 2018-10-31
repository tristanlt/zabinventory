# zabinventory : Zabbix Ansible inventory script

Zabinventory is an external [Ansible inventory script](https://docs.ansible.com/ansible/latest/user_guide/intro_dynamic_inventory.html). It request Zabbix API to retrieve hosts, hostgroups and hosts inventories.

It permit to use Zabbix Hostgroups with Ansible
```bash
ansible-playbook playbooks/ntp.yaml zabbixdefinedgroup
```

Play with Zabbix inventory variables...
```bash
ansible cercloud-mfs -m debug -a "var=[date_hw_expiry]" --limit br156-156
```

## Installation

Zabinventory is a Python script. It requires some extra-module.

```bash
pip install pandas
pip install ansible_vault
pip install config_parser
```

Or more simply (use requirements.txt from repo)
```bash
pip install -r requirements.txt
```

Create your inventory folder
```
inventory/
├── group_vars
│   ├── all
│   ├── hadoop-hdplops1
│   ├── hadoop-hdplops1-hbase-regionserver
│   └── IUEM-DC203-server
└── zabinventory
```

## Zabbix API User creation

On the Zabbix user interface, create a user, this user will connect to the API to retrieve information. This user must be allowed to read all hostgroups that you want to configure with Ansible. It doesn't need frontend access.

> Be sure that Zabbix User can read related hostgroups.

## Configuration

Zabinventory respect Ansible configuration placement rules. It will try to find configuration file inside :

* $ANSIBLE_CONFIG  
* ./ansible.cfg
* ~/.ansible.cfg
* /etc/ansible/ansible.cfg

Edit or create your ansible.cfg

```ini
[defaults]
inventory      = ./inventory/zabinventory

[zabbix_api_params]
zabbix_api_url = https://zabbix.server.tld/zabbix/api_jsonrpc.php
zabbix_api_username = username
zabbix_api_password = passw0rd
```

## Test

Inside folder which contains ansible.cfg file, simply run zabinventory script :
```
./inventory/zabinventory
```
It should return complete list of monitored hosts, hostgroups and inventory variables (inside \_meta).

## Protect Zabbix credentials with Ansible Vault

It is a good idea to protect your Zabbix credentials with Ansible Vault. 

Zabinventory can read one to all parameters from an encrypted file. Unfortunatly, Ansible inventory script wasn't interactive, you must use a password file.

Inside your ansible configuration, define password file :
```ini
[defaults]
vault_password_file = ansible_vault_pass.txt
```

Next, you can create an encrypted configuration with :
```bash
ansible-vault edit ./inventory/zabbix-api-params.yaml 
```

Configure Zabinventory ( yaml !) :
```yaml
---
zabbix_api_url: https://zabbix.server.tld/zabbix/api_jsonrpc.php
zabbix_api_username: username
zabbix_api_password: passw0rd
```   

Finally, edit ansible configuration, **zabbix\_api\_params** section, to point encrypted configuration :
```ini
[zabbix_api_params]
secured_yaml = ./inventory/zabbix-api-params.yaml
```

## Contribute
Feel free to fork, submit issues, PR, offence or thanks.

Current state is "that works for us", if Zabinventory work for you to, feel free to notify me on Twitter @tristanlt.
