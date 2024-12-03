try:
	import os; os.environ['PATH']
except:
	import os
	os.environ.setdefault('PATH', '')
import sys
import argparse
import logging
import colored_formatter
from colored_formatter import ColoredFormatter
import kerberosauth
import sysconfig
import os.path

#checking and importing dependencies
ISPY3 = sys.version_info[0] == 3
WINRM_INSTALLED = False
URLLIB_INSTALLED = False
KRB_INSTALLED = False
HAS_NTLM = False
HAS_CREDSSP = False
HAS_PEXPECT = False
SYSTEM_INTERPRETER = False

if ISPY3:
    from inspect import getfullargspec as getargspec
else:
    from inspect import getargspec

try:
    import requests.packages.urllib3
    requests.packages.urllib3.disable_warnings()
    URLLIB_INSTALLED = True
except ImportError as e:
    URLLIB_INSTALLED = False

try:
    import winrm

    WINRM_INSTALLED = True
except ImportError as e:
    WINRM_INSTALLED = False

try:
    from requests_kerberos import HTTPKerberosAuth, REQUIRED, OPTIONAL, DISABLED

    KRB_INSTALLED = True
except ImportError:
    KRB_INSTALLED = False

try:
    from requests_ntlm import HttpNtlmAuth

    HAS_NTLM = True
except ImportError as ie:
    HAS_NTLM = False

try:
    from requests_credssp import HttpCredSSPAuth

    HAS_CREDSSP = True
except ImportError as ie:
    HAS_CREDSSP = False

try:
    import pexpect

    if hasattr(pexpect, 'spawn'):
        argspec = getargspec(pexpect.spawn.__init__)
        if 'echo' in argspec.args:
            HAS_PEXPECT = True
except ImportError as e:
    HAS_PEXPECT = False

try:
    externally_managed_path = os.path.join(sysconfig.get_path("stdlib"), "EXTERNALLY-MANAGED")
    SYSTEM_INTERPRETER = os.path.exists(externally_managed_path)
except:
    SYSTEM_INTERPRETER = False

log_level = 'INFO'
if os.environ.get('RD_JOB_LOGLEVEL') == 'DEBUG':
    log_level = 'DEBUG'
else:
    log_level = 'ERROR'

##end


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
parser.add_argument('--krb5config', help='krb5config',default="/etc/krb5.conf")


args = parser.parse_args()

hostname = None
username = None
password = None
certpath = None
forceTicket = False

krb5config = None
kinit = "kinit"
krbdelegation = False

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

if args.krb5config:
    krb5config = args.krb5config

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

if "RD_CONFIG_KRB5CONFIG" in os.environ:
    krb5config = os.getenv("RD_CONFIG_KRB5CONFIG")

if "RD_CONFIG_KINIT" in os.environ:
    kinit = os.getenv("RD_CONFIG_KINIT")

if "RD_CONFIG_KRBDELEGATION" in os.environ:
    if os.getenv("RD_CONFIG_KRBDELEGATION") == "true":
        krbdelegation = True
    else:
        krbdelegation = False

endpoint=transport+'://'+hostname+':'+port

log.debug("------------------------------------------")
log.debug("endpoint:" + endpoint)
log.debug("authentication:" + authentication)
log.debug("username:" + username)
log.debug("nossl:" + str(nossl))
log.debug("transport:" + str(transport))
log.debug("diabletls12:" + str(diabletls12))
log.debug("krb5config:" + krb5config)
log.debug("kinit command:" + kinit)
log.debug("kerberos delegation:" + str(krbdelegation))

if(certpath):
    log.debug("certpath:" + certpath)
log.debug("------------------------------------------")


URLLIB_ERRORMESSAGE_BASE = "requests and urllib3 not installed"
WINRM_ERRORMESSAGE_BASE = "pywinrm not installed"
KRB_ERRORMESSAGE_BASE = "requests-kerberos not installed"
PEXPECT_ERRORMESSAGE_BASE = "pexpect not installed"
CREDSSP_ERRORMESSAGE_BASE = "pywinrm[credssp] not installed"
NTLM_ERRORMESSAGE_BASE = "requests-ntlm not installed"

if SYSTEM_INTERPRETER:
    import configparser
    externally_managed_file = configparser.RawConfigParser()
    externally_managed_file.read(externally_managed_path)
    SYSTEM_INTERPRETER_ERRORMESSAGE=externally_managed_file.get("externally-managed", "Error")

    ERRORMESSAGE = ", please install it using your systems package manager or consider using a virtual environment.\n{}".format(SYSTEM_INTERPRETER_ERRORMESSAGE)
    URLLIB_ERRORMESSAGE = "{}{}".format(URLLIB_ERRORMESSAGE_BASE, ERRORMESSAGE)
    WINRM_ERRORMESSAGE = "{}{}".format(WINRM_ERRORMESSAGE_BASE, ERRORMESSAGE)
    KRB_ERRORMESSAGE = "{}{}".format(KRB_ERRORMESSAGE_BASE, ERRORMESSAGE)
    PEXPECT_ERRORMESSAGE = "{}{}".format(PEXPECT_ERRORMESSAGE_BASE, ERRORMESSAGE)
    CREDSSP_ERRORMESSAGE = "{}{}".format(CREDSSP_ERRORMESSAGE_BASE, ERRORMESSAGE)
    NTLM_ERRORMESSAGE = "{}{}".format(NTLM_ERRORMESSAGE_BASE, ERRORMESSAGE)
else:
    URLLIB_ERRORMESSAGE = "{}, try: {} -m pip install requests urllib3".format(URLLIB_ERRORMESSAGE_BASE, sys.executable)
    WINRM_ERRORMESSAGE = "{}, try: {} -m pip install pywinrm".format(WINRM_ERRORMESSAGE_BASE, sys.executable)
    KRB_ERRORMESSAGE = "{}, try: {} -m pip install requests-kerberos".format(KRB_ERRORMESSAGE_BASE, sys.executable)
    PEXPECT_ERRORMESSAGE = "{}, try: {} -m pip install pexpect".format(PEXPECT_ERRORMESSAGE_BASE, sys.executable)
    CREDSSP_ERRORMESSAGE = "{}, try: {} -m pip install pywinrm[credssp]".format(CREDSSP_ERRORMESSAGE_BASE, sys.executable)
    NTLM_ERRORMESSAGE = "{}, try: {} -m pip install requests-ntlm".format(NTLM_ERRORMESSAGE_BASE, sys.executable)


if enabledHttpDebug:
    httpclient_logging_patch(logging.DEBUG)

PACKAGE_ERROR = False

if not URLLIB_INSTALLED:
    log.error(URLLIB_ERRORMESSAGE)
    PACKAGE_ERROR = True

if not WINRM_INSTALLED:
    log.error(WINRM_ERRORMESSAGE)
    PACKAGE_ERROR = True

if authentication == "kerberos" and not KRB_INSTALLED:
    log.error(KRB_ERRORMESSAGE)
    PACKAGE_ERROR = True

if authentication == "kerberos" and not HAS_PEXPECT:
    log.error(PEXPECT_ERRORMESSAGE)
    PACKAGE_ERROR = True

if authentication == "credssp" and not HAS_CREDSSP:
    log.error(CREDSSP_ERRORMESSAGE)
    PACKAGE_ERROR = True

if authentication == "ntlm" and not HAS_NTLM:
    log.error(NTLM_ERRORMESSAGE)
    PACKAGE_ERROR = True

if PACKAGE_ERROR:
    sys.exit(1)

arguments={}
arguments["transport"] = authentication

if(nossl == True):
    arguments["server_cert_validation"] = "ignore"
else:
    if(transport=="https"):
        arguments["server_cert_validation"] = "validate"
        arguments["ca_trust_path"] = certpath

arguments["credssp_disable_tlsv1_2"] = diabletls12

if authentication == "kerberos":
    k5bConfig = kerberosauth.KerberosAuth(krb5config=krb5config, log=log, kinit_command=kinit,username=username, password=password)
    k5bConfig.get_ticket()
    arguments["kerberos_delegation"] = krbdelegation

session = winrm.Session(target=endpoint,
                         auth=(username, password),
                         **arguments)

exec_command = "ipconfig"
result = session.run_cmd(exec_command)
print(result.std_out)

if(result.std_err):
    print("Connection with host %s fail" % hostname)
    sys.exit(1)
else:
    print("Connection with host %s successfull" % hostname)
