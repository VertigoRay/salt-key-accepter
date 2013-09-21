#!/usr/bin/env /usr/bin/python
# This script will auto accept key requests from machines in 10.120.33.0/24
# 
# Triggered by incron.  Use `incrontab -l` on the salt master to see the command.

import inspect
import logging
import netaddr
import os
import shutil
import subprocess
import sys
import time

allowed_ip_cidrs = (
    '10.120.33.0/24',
)
salt_master_config = '/etc/salt/master'

# Setup Logging
log = logging.getLogger(inspect.stack()[-1][1])
log.setLevel(logging.INFO)

log_location = '/var/log/CAS'
try: 
    os.makedirs(log_location)
except OSError as e:
    # Likely that the dir path exists.
    # if getting unknown errors, delete the directory 
    # structure and let this script recreate.
    # Troubleshoot by uncommentin this line:
    # print "os.makedirs(%s): OSError: %s" % (log_location, e)
    pass

fh = logging.FileHandler('%s/%s.log' % (log_location, os.path.split(inspect.stack()[-1][1])[1]))
fh.setLevel(logging.INFO)

# ch = logging.StreamHandler()
# ch.setLevel(logging.INFO)

formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
fh.setFormatter(formatter)
# ch.setFormatter(formatter)

log.addHandler(fh)
# log.addHandler(ch)
# / Setup Logging

def sh(script):
    """
    Opens bash shell subprocess
    Returns stdout(0), stderr(1), PID(2), and returncode(3) in a respective list
    """

    log.debug('> sh(%s)' % script)
    p = subprocess.Popen(script, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

    ret = {'out': out, 'err': err, 'pid': p.pid, 'returncode': p.returncode}
    log.debug('< sh: %s' % ret)
    return ret


try:
    key_path = sys.argv[1]
    key_name = sys.argv[2]

except IndexError as e:
    msg = 'IndexError: %s.\n\nUsage: %s <path_to_key> <key_name>' % (e, inspect.stack()[-1][1])
    log.error(msg)
    sys.exit(msg)

if not os.path.isfile('%s/%s' % (key_path, key_name)):
    # this should never be a thing ...
    msg = 'Certificate path does not exist: %s/%s' % (key_path, key_name)
    log.error(msg)
    sys.exit(msg)


salt = '/usr/bin/salt' if os.path.isfile('/usr/bin/salt') else sh('which salt')['out'].strip()
saltkey = '/usr/bin/salt-key' if os.path.isfile('/usr/bin/salt-key') else sh('which salt-key')['out'].strip()
cat = '/bin/cat' if os.path.isfile('/bin/cat') else sh('which cat')['out'].strip()
grep = '/bin/grep' if os.path.isfile('/bin/grep') else sh('which grep')['out'].strip()


log.info('Temporarily Accepting cert: %s' % key_name)
sh('%(saltkey)s --accept=%(key)s --yes' % {'saltkey':saltkey, 'key':key_name})

log.info('Waiting for accepted to show in list ...')
while len(sh('%(saltkey)s --list=accepted | grep %(key)s' % {'saltkey':saltkey, 'key':key_name})['out'].strip()) == 0:
    log.info('still waiting ...')
    time.sleep(1)

log.info('done waiting!')

log.info('Sync grains ...')
res = sh('%(salt)s \'%(key)s\' saltutil.sync_grains' % {'salt':salt, 'key':key_name})
log.info(res['out'])

log.info('Getting IPv4 info from grains ...')
ips = sh('%(salt)s \'%(key)s\' grains.item ipv4' % {'salt':salt, 'key':key_name})['out']
log.info(ips)
approved = False
for ip in ips.splitlines():
    if approved: break

    for cidr in allowed_ip_cidrs:
        try:
            if netaddr.IPAddress(ip.strip()) in list(netaddr.IPNetwork(cidr)):
                log.info('IP Address (%s) is in: %s' % (ip.strip(), cidr))
                approved = True
                break
            
            else:
                log.info('IP Address (%s) is NOT in: %s' % (ip.strip(), cidr))
                approved = False
        
        except netaddr.core.AddrFormatError as e:
            log.info('%s. Moving on ...' % e)
            
if not approved:
    log.info('Detecting pki_dir')

    minions_rejected = os.path.join(os.path.split(key_path)[0], 'minions_rejected')
    # in the sh(), we assume that if pki_dir exists more than once, than it only exists twice and the second one is the uncommented and effective one.
    minions_rejected = minions_rejected if os.path.isdir(minions_rejected) else sh('%(cat)S %(salt_master_config)s | %(grep)s pki_dir' % {'saltkey':saltkey, 'salt_master_config':salt_master_config, 'key':key_name}).splitlines()[-1].split(' ')[1]

    minions = os.path.join(os.path.split(key_path)[0], 'minions')
    minions = minions if os.path.isdir(minions) else sh('%(cat)S %(salt_master_config)s | %(grep)s pki_dir' % {'saltkey':saltkey, 'salt_master_config':salt_master_config, 'key':key_name}).splitlines()[-1].split(' ')[1]

    # Can't reject the key once it has been accepted ... 
    # instead we will move it the minions dir
    log.info('Moving key to Rejected list: %s' % minions_rejected)
    shutil.move(os.path.join(minions, key_name), minions_rejected)
    log.info(sh('%(saltkey)s --list=rejected' % {'saltkey': saltkey})['out'])

else:
    log.info('IP Address is in a valid subnet!  All Done!')
    ##do state highstate on minions
    log.info('Do state highstate after accepting the key')
    sh('%(salt)s \'%(key)s\' state.highstate' % {'salt':salt, 'key':key_name})
    log.info(res['out'])
