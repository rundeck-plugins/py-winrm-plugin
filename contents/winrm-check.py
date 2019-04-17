import winrm
try:
	import os; os.environ['PATH']
except:
	import os
	os.environ.setdefault('PATH', '')
import sys
import argparse
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()
import logging
import colored_formatter
from colored_formatter import ColoredFormatter

log_level = 'INFO'
if os.environ.get('RD_JOB_LOGLEVEL') == 'DEBUG':
    log_level = 'DEBUG'
else:
    log_level = 'ERROR'

console = logging.StreamHandler()
console.setFormatter(ColoredFormatter(colored_formatter.format()))
console.stream=sys.stdout

log = logging.getLogger()
log.addHandler(console)
log.setLevel(log_level)

parser = argparse.ArgumentParser(description='Run Bolt command.')
parser.add_argument('--username', help='the username')
parser.add_argument('--hostname', help='the hostname')
parser.add_argument('--password', help='Password')
parser.add_argument('--authentication', help='authentication', default="basic")
parser.add_argument('--transport', help='transport',default="http")
parser.add_argument('--port', help='port',default="5985")
parser.add_argument('--nossl', help='nossl',default="False")
parser.add_argument('--diabletls12', help='diabletls12',default="False")
parser.add_argument('--debug', help='debug',default="False")
parser.add_argument('--certpath', help='certpath')

args = parser.parse_args()

hostname = None
username = None
password = None
certpath = None

if args.hostname:
    hostname = args.hostname

if args.username:
    username = args.username

if args.password:
    password = args.password

if args.authentication:
    authentication = args.authentication

if args.transport:
    transport = args.transport

if args.port:
    port = args.port

if args.nossl:
    if args.nossl == "true":
        nossl = True
    else:
        nossl = False

if args.diabletls12:
    if args.diabletls12 == "true":
        diabletls12 = True
    else:
        diabletls12 = False

if args.debug:
    if args.debug == "true":
        debug = True
    else:
        debug = False

if args.certpath:
    certpath = args.certpath

if not hostname:
    print("hostname is required")
    sys.exit(1)

if not username:
    print("username is required")
    sys.exit(1)


if not password:
    print("password is required")
    sys.exit(1)

if os.getenv("RD_JOB_LOGLEVEL") == "DEBUG":
    debug = True

endpoint=transport+'://'+hostname+':'+port

log.debug("------------------------------------------")
log.debug("endpoint:" + endpoint)
log.debug("authentication:" + authentication)
log.debug("username:" + username)
log.debug("nossl:" + str(nossl))
log.debug("transport:" + str(transport))
log.debug("diabletls12:" + str(diabletls12))
if(certpath):
    log.debug("certpath:" + certpath)
log.debug("------------------------------------------")


arguments={}
arguments["transport"] = authentication

if(nossl == True):
    arguments["server_cert_validation"] = "ignore"
else:
    if(transport=="https"):
        arguments["server_cert_validation"] = "validate"
        arguments["ca_trust_path"] = certpath

arguments["credssp_disable_tlsv1_2"] = diabletls12

session = winrm.Session(target=endpoint,
                         auth=(username, password),
                         **arguments)

exec_command = "ipconfig"
result = session.run_cmd(exec_command)

if(result.std_err):
    print("Connection with host %s fail" % hostname)
    sys.exit(1)
else:
    print("Connection with host %s successfull" % hostname)
