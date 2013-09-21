# salt-key-accepter

This script will auto accept key requests from machines in the `allow_ip_cidrs` list.

## Requirements

On your salt-master, install:
`incron` (part of `inotify`).

Once install, you can edit your inotify jobs with `incrontab -e`.  Here's my `incrontab -l`:
```bash
/etc/salt/pki/master/minions_pre IN_CREATE /usr/bin/env /usr/bin/python /usr/local/git/salt-key-accepter.py $@ $#
```

## Usage

Just set the following two variables:
* `allowed_ip_cidrs`
* `salt_master_config` 

### `allowed_ip_cidrs`

A `list` of IP subnets in [CIDR notation](http://en.wikipedia.org/wiki/Classless_Inter-Domain_Routing#CIDR_notation).

### `salt_master_config`

The path to your salt master config file.
