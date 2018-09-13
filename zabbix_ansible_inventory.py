#!/usr/bin/env python 
# coding: utf-8

""" zabbix_api_inventory.py: External Ansible inventory script which called Zabbix API to retrieve host, hostgroups and host inventory """ 

__author__ = "Tristan Le Toullec"
__license__ = "GPL"
__version__ = "0.1"
__email__ = "tristan.letoullec@cnrs.fr"
__status__ = ""

import argparse
import json
import sys
import requests
import os 
import logging

from ansible_vault import Vault
import pandas as pd
import configparser

class ZabbixAnsibleInventory:
    
    def __init__(self):

        # Logging stuff
        logging.basicConfig()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.WARNING)

        self.logger.info("Starting Zabbix API Inventory for Ansible external inventory")
        
        # Search ansible.cfg and check section [zabbix_api_params]
        config = self._get_config()

        # Get Zabbix API params
        zabbix_api_params = self._get_zabbix_api_params(config)

        # Connection to Zabbix API
        self.zabt = Zabtools()
        self.zabbix_url =  zabbix_api_params['zabbix_api_url']
        username = zabbix_api_params['zabbix_api_username']
        password = zabbix_api_params['zabbix_api_password']
        self.auth = self.zabt.zabapi_auth(self.zabbix_url, username, password)
       
        self._parse_cli_args()

        if self.args.flatfile:
            self.flat_export(self.args.flatfile)
            sys.exit(0)
        
        if self.args.hosts:
            response = self.get_host_inventory(self.args.hosts)
            print(json.dumps(response))
            sys.exit(0)

        if self.args.list:
            response = self.get_hg_inventory()
            print(json.dumps(response))
            sys.exit(0)

    def _get_config(self):
        """        
        Try to find ansible configuration 
        Use Ansible order: $ANSIBLE_CONFIG, ansible.cfg, ~/.ansible.cfg, /etc/ansible/ansible.cfg
        Search for [zabbix_api_params] sections inside ansible.cfg
        @output if ok : A configparser object with whole ansible.cfg configuration
        @output else : None
        """

        config = configparser.ConfigParser()

        try:
            config.read(os.environ["ANSIBLE_CONFIG"])
            zabbix_api_params = config["zabbix_api_params"]
            self.logger.info("Ansible configuration from $ANSIBLE_CONFIG")
            return config
        except:
            pass
            
        try:
            config.read("ansible.cfg")
            zabbix_api_params = config["zabbix_api_params"]
            self.logger.info("Ansible configuration from ./ansible.cfg")
            return config
        except:
            pass
        
        try:
            config.read("~/.ansible.cfg")
            zabbix_api_params = config["zabbix_api_params"]
            self.logger.info("Ansible configuration from ~/.ansible.cfg")
            return config
        except:
            pass

        try:
            config.read("/etc/ansible/ansible.cfg")
            zabbix_api_params = config["zabbix_api_params"]
            self.logger.info("Ansible configuration from /etc/ansible/ansible.cfg")
            return config
        except:
            pass

        self.logger.critical("Can't find an ansible configuration file with section [zabbix_api_params].")
        exit(0)

    def _get_zabbix_api_params(self, config):
        """
        @input: ConfigParser object with whole ansible.cdf configuration
        @output: Dict with Zabbix API Params
        """
        zabbix_api_params = { "zabbix_api_url": None,
                              "zabbix_api_username": None,
                              "zabbix_api_password": None }

        # Read [zabbix_api_params] section from config file and fill output
        # Warning ! these values should be override by configuration inside secured_yaml file
        for k in zabbix_api_params.keys():
            zabbix_api_params[k] = config.get('zabbix_api_params', k, fallback=None)
            self.logger.info("Ansible config : Found zabbix_api_params %s = %s " % (k, zabbix_api_params[k]) )

        # Is there some configuration inside a Vault secured yaml file ?
        secured_yaml = config.get('zabbix_api_params', 'secured_yaml', fallback=None)
        if secured_yaml:
            self.logger.info("Found secured_yaml config (%s). I like that." % (secured_yaml) )
            data = {}
            # Zabbix API Params was secured with Ansible Vault. Huumm... I like that.
            try:
                vault_password_file = config.get('defaults', 'vault_password_file')
            except:
                self.logger.error("Can't find vault_password_file configuration inside Ansible configuration ([defaults] section.")
                self.logger.error("No Vault password found, can't decode %s" % (vault_password_file))
                pass

            # Get password from vault_password_file
            try:
                f = open(vault_password_file, 'r')
                passwd = f.read().splitlines()[0]
            except:
                self.logger.error("Cannot read vault_password_file (%s)" % (vault_password_file))
            
            try:
                vault = Vault(passwd)
                data = vault.load(open(secured_yaml).read())
            except:
                self.logger.error("Unable to read secured_yaml. Check Vault password, secured_yaml file path")

            # Override output data with secured configuration
            for k in data.keys():
                zabbix_api_params[k] = data[k]
                self.logger.info("Secured yaml (vault): Found zabbix_api_params %s " % (k) )
        return zabbix_api_params



    def _parse_cli_args(self):
        """ Command line argument processing """

        parser = argparse.ArgumentParser(description='External Ansible inventory script which retrieve hosts, hostgroups and hosts inventories from Zabbix API server.')
        parser.add_argument('--list', action='store_true', default=True, help='List instances (default: True)')
        parser.add_argument('--hosts', action='store', help='Get all the variables about a specific instance')
        parser.add_argument('--flatfile', action='store', help='Create flat Ansible inventory inside provided filename')
        self.args = parser.parse_args()

    def flat_export(self, filename):
        """
        Called with --flatfile <filename> flags. Generate a flat Ansible inventory inside provided filename.
        """
        zabbix_hostgroups = self.zabt.get_zabbix_hostgroups_by_name(self.zabbix_url,
                                                                   self.auth)
        hgdf = pd.DataFrame(zabbix_hostgroups)
        
        with open(filename, 'w') as f:
            for hg in hgdf:
                f.write("[%s]\n" % hg.encode('utf-8'))
                f.write("%s\n\n" % "\n".join([ h['name'].encode('utf-8') for h in hgdf[hg].hosts ]))



    def get_hg_inventory(self):
        """
        Called with --list flags. It read all informations from Zabbix API (hostgroups and host inventory)
        @output Dict with _meta[hostvars] and hostgroups with subgroups
        """
        self.logger.info("--list ")
        zabbix_hosts = self.zabt.get_zabbix_hosts_by_name(self.zabbix_url,
                                                     self.auth)
        zabbix_hostgroups = self.zabt.get_zabbix_hostgroups_by_name(self.zabbix_url,
                                                               self.auth)

        # On Ansible 1.3 and newers, we can add hostvars on list to limit API Calls
        # Generate _meta for response
        # Only Zabbix Inventory was added to _meta
        hostvars = {}
        for hostname in zabbix_hosts.keys():
            if "inventory" in zabbix_hosts[hostname].keys():
                if zabbix_hosts[hostname]['inventory']:
                    hostvars[hostname] = zabbix_hosts[hostname]['inventory']
        #hostvars = { hostname:zabbix_hosts[hostname]['inventory'] for hostname in zabbix_hosts.keys() }
        hg_inventory = { "_meta": {
                          "hostvars": hostvars
                         }
                       }
        # Generate hostgroup list with members
        hgdf = pd.DataFrame(zabbix_hostgroups)
        for hg in hgdf:
            hg_inventory[hg] = { "hosts": [ h['name'] for h in hgdf[hg].hosts ] }

        return hg_inventory

    def get_host_inventory(self, host):
        """
        Called with --hosts <host> return Zabbix Inventory for specified host
        @output a dict with Zabbix inventory keys and value
        """
        self.logger.info("--hosts %s" % host)
        zabbix_hosts = self.zabt.get_zabbix_hosts_by_name(self.zabbix_url,
                                                         self.auth)
        if host in zabbix_hosts.keys():
            return zabbix_hosts[host]['inventory']
        else:
            return {}

class Zabtools:

    def zabapi_auth(self, zabbix_url, login, password):
        auth_data = {"jsonrpc": "2.0",
                     "method": "user.login",
                     "params": { "user": login,
                                "password": password},
                     "id": 1,
                     "auth": None}
        
        try:
            auth_response = requests.post(zabbix_url, json=auth_data)
        except:
            print("Failed to communicate with Zabbix API")
            exit(0)
        
        try:
            auth_response.raise_for_status()
        except auth_response.HTTPError:
            print('Bad response from Zabbix API code %s, message %s' % (auth_response.status_code, auth_response.text))
            exit(0)
        
        if not "result" in auth_response.json():
            print("Zabbix API Auth failed")
            exit(0)
        
        #AUTH OK 
        return auth_response.json()['result']

    def get_zabbix_hosts_by_name(self, zabbix_url, auth):
        # Host catalog
        req = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {
                "limit": 999,
                "output": [
                    "hostid",
                    "host",
                    "proxy_hosts"
                ],
                "selectGroups": "extend",
                "selectInventory": "extend",
                "selectInterfaces": [
                    "interfaceid",
                    "ip"
                ]
            },
            "id": 2,
            "auth": auth,
        }
        zabbix_hosts = requests.post(zabbix_url, json=req).json()['result']
        zabbix_hosts_by_name = {}
        for h in zabbix_hosts:
            zabbix_hosts_by_name[h['host']] = h
        
        return zabbix_hosts_by_name
    
    def get_zabbix_hostgroups_by_name(self, zabbix_url, auth):
        # Templates catalogs
        req = {
            "jsonrpc": "2.0",
            "method": "hostgroup.get",
            "params": {
                "limit": 999,
                "output": [
                    "groupid",
                    "name"
                ],
            "selectHosts": "extend",
            },
            "id": 2,
            "auth": auth
        } 
        zabbix_hostgroups = requests.post(zabbix_url, json=req).json()['result']
        
        zabbix_hostgroups_by_name = {}
        for t in zabbix_hostgroups:
            zabbix_hostgroups_by_name[t['name']] = t
        
        return zabbix_hostgroups_by_name

ZabbixAnsibleInventory()


