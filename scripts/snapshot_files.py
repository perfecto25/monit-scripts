#!/usr/bin/python
#from __future__ import print_function
import os
import sys
import subprocess
import time
from subprocess import Popen, PIPE
from utils import send_email, render_template, log

from_addr = 'monit@company.com'
to_addr = 'admin@company.com'

base_dir = '/etc/monit/scripts/'
hostname = os.uname()[1]
path = sys.argv[1]

def diskspace(path):
    ''' list of largest files in directory '''
    # check if dir or file exists
    if not os.path.exists(path):
        log.error('provided directory or file does not exist: {}'.format(path))
        return 'error'

    cmd1 = 'sudo find {0} -type f -exec du -Sh {{}} + | sort -rh | head -n 15'.format(path)
    try:
        result = subprocess.Popen(cmd1, shell=True, stdout=PIPE)
    except subprocess.CalledProcessError as e:
        log.error(e.output)

    result =  result.stdout.read().split('\n')

    return result

def email(html, to_addr, from_addr):
    subject = 'Monit (%s): Largest files' % hostname
    try:
        log.info('sending Monit "largest files in %s" snapshot' % path)
        send_email(to_addr, from_addr, cc=None, bcc=None, subject=subject, body=html)
    except Exception as e:
        log.error(str(e))

if __name__ == "__main__":
    date = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime())
    html = render_template(base_dir + '/j2/files.j2', result=diskspace(path), hostname=hostname, date=date, path=path)
    email(html, to_addr, from_addr)
