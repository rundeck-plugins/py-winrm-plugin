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
import sysconfig
import os.path

class SuppressFilter(logging.Filter):
    def filter(self, record):
        return 'wsman' not in record.getMessage()

try:
    from urllib3.connectionpool import log
    #log.addFilter(SuppressFilter())
except:
    pass

import http.client
httpclient_logger = logging.getLogger("http.client")


def httpclient_logging_patch(level=logging.DEBUG):
    def httpclient_log(*args):
        httpclient_logger.log(level, " ".join(args))

    http.client.print = httpclient_log
    http.client.HTTPConnection.debuglevel = 1

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

requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

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
cleanescapingflg = False
enabledHttpDebug = False
retryconnection = 1
retryconnectiondelay = 0
username = None
winrmproxy = None

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

if "RD_CONFIG_CLEANESCAPING" in os.environ:
     if os.getenv("RD_CONFIG_CLEANESCAPING") == "true":
        cleanescapingflg = True
     else:
        cleanescapingflg = False

if "RD_CONFIG_WINRMPROXY" in os.environ:
    winrmproxy = os.getenv("RD_CONFIG_WINRMPROXY")
    log.debug("winrmproxy: " + str(winrmproxy))

if "RD_CONFIG_ENABLEDHTTPDEBUG" in os.environ:
    if os.getenv("RD_CONFIG_ENABLEDHTTPDEBUG") == "true":
        enabledHttpDebug = True
    else:
        enabledHttpDebug = False

if "RD_CONFIG_RETRYCONNECTION" in os.environ:
    retryconnection = int(os.getenv("RD_CONFIG_RETRYCONNECTION"))

if "RD_CONFIG_RETRYCONNECTIONDELAY" in os.environ:
    retryconnectiondelay = int(os.getenv("RD_CONFIG_RETRYCONNECTIONDELAY"))

exec_command = os.getenv("RD_EXEC_COMMAND")
log.debug("Command will be executed: " + exec_command)

if cleanescapingflg:
     exec_command = common.removeSimpleQuotes(exec_command)
     log.debug("Command escaped will be executed: " + exec_command)

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

DEFAULT_CHARSET = 'utf-8'
output_charset = DEFAULT_CHARSET
if "RD_NODE_OUTPUT_CHARSET" in os.environ:
    output_charset = os.getenv("RD_NODE_OUTPUT_CHARSET")

log.debug("------------------------------------------")
log.debug("endpoint:" + endpoint)
log.debug("authentication:" + authentication)
log.debug("username:" + username)
log.debug("nossl:" + str(nossl))
log.debug("diabletls12:" + str(diabletls12))
log.debug("krb5config:" + str(krb5config))
log.debug("kinit command:" + str(kinit))
log.debug("kerberos delegation:" + str(krbdelegation))
log.debug("shell:" + shell)
log.debug("output_charset:" + output_charset)
log.debug("readtimeout:" + str(readtimeout))
log.debug("operationtimeout:" + str(operationtimeout))
log.debug("exit Behaviour:" + exitBehaviour)
log.debug("cleanescapingflg: " + str(cleanescapingflg))
log.debug("enabledHttpDebug: " + str(enabledHttpDebug))
log.debug("retryConnection: " + str(retryconnection))
log.debug("retryConnectionDelay: " + str(retryconnectiondelay))
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

if(winrmproxy):
    arguments["proxy"] = winrmproxy

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

tsk = winrm_session.RunCommand(session, shell, exec_command, retryconnection, retryconnectiondelay, output_charset)
t = threading.Thread(target=tsk.get_response)
t.start()
realstdout = sys.stdout
realstderr = sys.stderr
sys.stdout = tsk.o_stream
sys.stderr = tsk.e_stream

lastpos = 0
lasterrorpos = 0

while True:
    t.join(.1)

    try:
        if sys.stdout.tell() != lastpos:
            sys.stdout.seek(lastpos)
            read=sys.stdout.read()
            if isinstance(read, str):
                realstdout.write(read)
            else:
                realstdout.write(read.decode(output_charset))
    except UnicodeDecodeError:
        try:
            realstdout.write(read.decode(DEFAULT_CHARSET))
        except Exception as e:
            log.error(e)
    except Exception as e:
        log.error(e)
    
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
