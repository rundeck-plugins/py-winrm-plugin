import argparse
try:
	import os; os.environ['PATH']
except:
	import os
	os.environ.setdefault('PATH', '')
import sys
import winrm_session
import threading
import logging
import colored_formatter
import kerberosauth
import common
from colored_formatter import ColoredFormatter


class SuppressFilter(logging.Filter):
    def filter(self, record):
        return 'wsman' not in record.getMessage()

try:
    from urllib3.connectionpool import log
    log.addFilter(SuppressFilter())
except:
    pass

#checking and importing dependencies
ISPY3 = sys.version_info[0] == 3
WINRM_INSTALLED = False
URLLIB_INSTALLED = False
KRB_INSTALLED = False
HAS_NTLM = False
HAS_CREDSSP = False
HAS_PEXPECT = False

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

if os.environ.get('RD_JOB_LOGLEVEL') == 'DEBUG':
    log_level = 'DEBUG'
else:
    log_level = 'INFO'

##end

console = logging.StreamHandler()
console.setFormatter(ColoredFormatter(colored_formatter.format()))
console.stream=sys.stdout
log = logging.getLogger()
log.addHandler(console)
log.setLevel(log_level)

parser = argparse.ArgumentParser(description='Run Bolt command.')
parser.add_argument('hostname', help='the hostname')
args = parser.parse_args()

password=None
authentication = "basic"
transport = "http"
port = "5985"
nossl=False
diabletls12=False
debug=False
shell = "cmd"
certpath = None
krb5config = None
kinit = None
krbdelegation = False
forceTicket = False
readtimeout = None
operationtimeout = None
forcefail = False
exitBehaviour = "console"

if "RD_CONFIG_AUTHTYPE" in os.environ:
    authentication = os.getenv("RD_CONFIG_AUTHTYPE")

if "RD_CONFIG_WINRMTRANSPORT" in os.environ:
    transport = os.getenv("RD_CONFIG_WINRMTRANSPORT")

if "RD_CONFIG_WINRMPORT" in os.environ:
    port = os.getenv("RD_CONFIG_WINRMPORT")

if "RD_CONFIG_NOSSL" in os.environ:
    if os.getenv("RD_CONFIG_NOSSL") == "true":
        nossl = True
    else:
        nossl = False

if "RD_CONFIG_DISABLETLS12" in os.environ:
    if os.getenv("RD_CONFIG_DISABLETLS12") == "true":
        diabletls12 = True
    else:
        diabletls12 = False

if "RD_CONFIG_SHELL" in os.environ:
    shell = os.getenv("RD_CONFIG_SHELL")

if "RD_CONFIG_EXITBEHAVIOUR" in os.environ:
    exitBehaviour = os.getenv("RD_CONFIG_EXITBEHAVIOUR")

if os.getenv("RD_JOB_LOGLEVEL") == "DEBUG":
    debug = True

if "RD_CONFIG_CERTPATH" in os.environ:
    certpath = os.getenv("RD_CONFIG_CERTPATH")

if "RD_CONFIG_READTIMEOUT" in os.environ:
    readtimeout = os.getenv("RD_CONFIG_READTIMEOUT")

if "RD_CONFIG_OPERATIONTIMEOUT" in os.environ:
    operationtimeout = os.getenv("RD_CONFIG_OPERATIONTIMEOUT")

exec_command = os.getenv("RD_EXEC_COMMAND")

if "cmd" in shell:
     exec_command = common.replace_single_quotes_format(exec_command)

endpoint=transport+'://'+args.hostname+':'+port

if "RD_OPTION_USERNAME" in os.environ and os.getenv("RD_OPTION_USERNAME"):
    log.debug('Using option.username: %s' % os.environ['RD_OPTION_USERNAME'])
    #take user from job
    username = os.getenv("RD_OPTION_USERNAME").strip('\'')
else:
    # take user from node
    if "RD_NODE_USERNAME" in os.environ and os.getenv("RD_NODE_USERNAME"):
        log.debug('Using username from node definition: %s' % os.environ['RD_NODE_USERNAME'])
        username = os.getenv("RD_NODE_USERNAME").strip('\'')
    else:
        # take user from project
        if "RD_CONFIG_USERNAME" in os.environ and os.getenv("RD_CONFIG_USERNAME"):
            log.debug('Using username from project definition: %s' % os.environ['RD_CONFIG_USERNAME'])
            username = os.getenv("RD_CONFIG_USERNAME").strip('\'')

if "RD_OPTION_WINRMPASSWORD" in os.environ and os.getenv("RD_OPTION_WINRMPASSWORD"):
    log.debug('Using option.winrmpassword')
    #take password from job
    password = os.getenv("RD_OPTION_WINRMPASSWORD").strip('\'')
else:
    if "RD_CONFIG_PASSWORD_STORAGE_PATH" in os.environ:
        log.debug('Using password from node')
        password = os.getenv("RD_CONFIG_PASSWORD_STORAGE_PATH")

if "RD_CONFIG_KRB5CONFIG" in os.environ:
    krb5config = os.getenv("RD_CONFIG_KRB5CONFIG")

if "RD_CONFIG_KINIT" in os.environ:
    kinit = os.getenv("RD_CONFIG_KINIT")

if "RD_CONFIG_KRBDELEGATION" in os.environ:
    if os.getenv("RD_CONFIG_KRBDELEGATION") == "true":
        krbdelegation = True
    else:
        krbdelegation = False

log.debug("------------------------------------------")
log.debug("endpoint:" + endpoint)
log.debug("authentication:" + authentication)
log.debug("username:" + username)
log.debug("nossl:" + str(nossl))
log.debug("diabletls12:" + str(diabletls12))
log.debug("krb5config:" + krb5config)
log.debug("kinit command:" + kinit)
log.debug("kerberos delegation:" + str(krbdelegation))
log.debug("shell:" + shell)
log.debug("readtimeout:" + str(readtimeout))
log.debug("operationtimeout:" + str(operationtimeout))
log.debug("exit Behaviour:" + exitBehaviour)
log.debug("------------------------------------------")

if not URLLIB_INSTALLED:
    log.error("request and urllib3 not installed, try: pip install requests &&  pip install urllib3")
    sys.exit(1)

if not WINRM_INSTALLED:
    log.error("winrm not installed, try: pip install pywinrm")
    sys.exit(1)

if authentication == "kerberos" and not KRB_INSTALLED:
    log.error("Kerberos not installed, try: pip install requests-kerberos")
    sys.exit(1)

if authentication == "kerberos" and not HAS_PEXPECT:
    log.error("pexpect not installed, try: pip install pexpect")
    sys.exit(1)

if authentication == "credssp" and not HAS_CREDSSP:
    log.error("CredSSP not installed, try: pip install pywinrm[credssp]")
    sys.exit(1)

if authentication == "ntlm" and not HAS_NTLM:
    log.error("NTLM not installed, try: pip install requests_ntlm")
    sys.exit(1)

arguments = {}
arguments["transport"] = authentication

if(nossl == True):
    arguments["server_cert_validation"] = "ignore"
else:
    if(transport == "https"):
        arguments["server_cert_validation"] = "validate"
        arguments["ca_trust_path"] = certpath

if(readtimeout):
    arguments["read_timeout_sec"] = readtimeout

if(operationtimeout):
    arguments["operation_timeout_sec"] = operationtimeout

arguments["credssp_disable_tlsv1_2"] = diabletls12

if authentication == "kerberos":
    k5bConfig = kerberosauth.KerberosAuth(krb5config=krb5config, log=log, kinit_command=kinit,username=username, password=password)
    k5bConfig.get_ticket()
    arguments["kerberos_delegation"] = krbdelegation

session = winrm.Session(target=endpoint,
                        auth=(username, password),
                        **arguments)

winrm.Session.run_cmd = winrm_session.run_cmd
winrm.Session.run_ps = winrm_session.run_ps
winrm.Session._clean_error_msg = winrm_session._clean_error_msg
winrm.Session._strip_namespace = winrm_session._strip_namespace

tsk = winrm_session.RunCommand(session, shell, exec_command)
t = threading.Thread(target=tsk.get_response)
t.start()
realstdout = sys.stdout
realstderr = sys.stderr
sys.stdout = tsk.o_stream
sys.stderr = tsk.e_stream

lastpos = 0
lasterrorpos = 0

charset = "utf-8"
if "RD_NODE_CHARSET" in os.environ:
    charset = os.getenv("RD_NODE_CHARSET")

while True:
    t.join(.1)

    if sys.stdout.tell() != lastpos:
        sys.stdout.seek(lastpos)
        read=sys.stdout.read()
        if isinstance(read, str):
            realstdout.write(read)
        else:
            realstdout.write(read.decode(charset))

        lastpos = sys.stdout.tell()

    if not t.is_alive():
        break

sys.stdout.seek(0)
sys.stderr.seek(0)
sys.stdout = realstdout
sys.stderr = realstderr

if exitBehaviour == 'console':
    if tsk.e_std:
        log.error("Execution finished with the following error")
        log.error(tsk.e_std)
        sys.exit(1)
    else:
        sys.exit(tsk.stat)
else:
    if tsk.stat != 0:
        log.error("Execution finished with the following exit code: {} ".format(tsk.stat))
        log.error(tsk.stat)
        log.error(tsk.e_std)

        sys.exit(tsk.stat)
    else:
        if tsk.e_std:
            log.warning(tsk.e_std)
        sys.exit(tsk.stat)
