try:
	import os; os.environ['PATH']
except:
	import os
	os.environ.setdefault('PATH', '')
import winrm
import argparse
import sys
import base64
import time
import common
import logging
import ntpath
import xml.etree.ElementTree as ET
import colored_formatter
from colored_formatter import ColoredFormatter
import kerberosauth
import http.client
import winrm_session
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

# end

console = logging.StreamHandler()
console.setFormatter(ColoredFormatter(colored_formatter.format()))
console.stream=sys.stdout

log = logging.getLogger()
log.addHandler(console)
log.setLevel(log_level)

httpclient_logger = logging.getLogger("http.client")


def httpclient_logging_patch(level=logging.DEBUG):
    def httpclient_log(*args):
        httpclient_logger.log(level, " ".join(args))

    http.client.print = httpclient_log
    http.client.HTTPConnection.debuglevel = 1


def _clean_error_msg(self, msg):
    """converts a Powershell CLIXML message to a more human readable string
    """
    # TODO prepare unit test, beautify code
    # if the msg does not start with this, return it as is
    if type(msg) == bytes and msg.startswith(b"#< CLIXML\r\n"):
        # for proper xml, we need to remove the CLIXML part
        # (the first line)
        msg_xml = msg[11:]
        try:
            # remove the namespaces from the xml for easier processing
            msg_xml = self._strip_namespace(msg_xml)
            root = ET.fromstring(msg_xml)
            # the S node is the error message, find all S nodes
            nodes = root.findall("./S")
            new_msg = ""
            for s in nodes:
                # append error msg string to result, also
                # the hex chars represent CRLF so we replace with newline
                print(s.text)
                new_msg += s.text.replace("_x000D__x000A_", "\n")
        except Exception as e:
            # if any of the above fails, the msg was not true xml
            # print a warning and return the orignal string
            # TODO do not print, raise user defined error instead
            print("Warning: there was a problem converting the Powershell"
                  " error message: %s" % (e))
        else:
            # if new_msg was populated, that's our error message
            # otherwise the original error message will be used
            if len(new_msg):
                # remove leading and trailing whitespace while we are here
                msg = new_msg.strip()
    return msg


requests.packages.urllib3.disable_warnings()

if os.environ.get('RD_CONFIG_DEBUG') == 'true':
    log_level = 'DEBUG'
else:
    log_level = 'ERROR'

logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, log_level),
    format='%(levelname)s: %(name)s: %(message)s'
)
log = logging.getLogger('winrm-filecopier')


class RemoteCommandError(Exception):
    def __init__(self, command, return_code, std_out='', std_err=''):
        super(RemoteCommandError, self).__init__(
            'Remote execution of "{}" failed with exit code {}. '
            'STDOUT: {}. STDERR: {}.'.format(
                command, return_code, std_out, std_err
            )
        )


class WinRmError(RemoteCommandError):
    pass


class CopyFiles(object):

    def __init__(self, session, retry, retry_delay):
        self.session = session
        self.retry = retry
        self.retry_delay = retry_delay


    def winrm_upload(self,
                    remote_path,
                    remote_filename,
                    local_path,
                    step=2048,
                    quiet=True,
                    override=False):

        if remote_path.endswith('/') or remote_path.endswith('\\'):
            full_path = remote_path + remote_filename
        else:
            full_path = remote_path + "\\" + remote_filename

        print("coping file %s to %s" % (local_path, full_path))

        self.session.run_ps('if (!(Test-Path {0})) {{ New-Item -ItemType directory -Path {0} }}'.format(remote_path),
                            retry=self.retry,
                            retry_delay=self.retry_delay)

        if override:
            self.session.run_ps('if ((Test-Path {0} -PathType Leaf)) {{ rm {0} }}'.format(full_path), retry=self.retry, retry_delay=self.retry_delay)

        size = os.stat(local_path).st_size
        with open(local_path, 'rb') as f:
            for i in range(0, size, step):
                script = (
                    'add-content -value '
                    '$([System.Convert]::FromBase64String("{}")) '
                    '-encoding byte -path {}'.format(
                        base64.b64encode(f.read(step)).decode(),
                        full_path
                    )
                )
                while True:
                    result = self.session.run_ps(script)
                    code=result.status_code
                    stdout=result.std_out
                    stderr=result.std_err

                    if code == 0:
                        break
                    elif code == 1 and 'used by another process' in stderr:
                        time.sleep(0.1)
                    else:
                        raise WinRmError(script, code, stdout, stderr)
                if not quiet:
                    transferred = i + step
                    if transferred > size:
                        transferred = size
                    progress_blocks = transferred * 30 // size
                    percentage_string = str(
                        (100 * transferred) // size
                    ) + ' %'
                    percentage_string = (
                        ' ' * (10 - len(percentage_string)) +
                        percentage_string
                    )
                    print(percentage_string)
                    sys.stdout.flush()


parser = argparse.ArgumentParser(description='Run Bolt command.')
parser.add_argument('hostname', help='the hostname')
parser.add_argument('source', help='Source File')
parser.add_argument('destination', help='Destination File')

args = parser.parse_args()

#it is necesarry to avoid the debug error
print(args.destination)

password=None
authentication = "basic"
transport = "http"
port = "5985"
nossl = False
debug = False
diabletls12 = False
kinit = None
krb5config = None
krbdelegation = False
forceTicket = False
override=False
enabledHttpDebug = False
readtimeout = None
operationtimeout = None
retryconnection = 1
retryconnectiondelay = 0
certpath = None
username = None
winrmproxy = None

if os.environ.get('RD_CONFIG_OVERRIDE') == 'true':
    override = True

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

if "RD_CONFIG_CERTPATH" in os.environ:
    certpath = os.getenv("RD_CONFIG_CERTPATH")

if "RD_CONFIG_WINRMPROXY" in os.environ:
    winrmproxy = os.getenv("RD_CONFIG_WINRMPROXY")

if "RD_OPTION_USERNAME" in os.environ and os.getenv("RD_OPTION_USERNAME"):
    #take user from job
    username = os.getenv("RD_OPTION_USERNAME").strip('\'')
else:
    # take user from node
    if "RD_NODE_USERNAME" in os.environ and os.getenv("RD_NODE_USERNAME"):
        username = os.getenv("RD_NODE_USERNAME").strip('\'')
    else:
        # take user from project
        if "RD_CONFIG_USERNAME" in os.environ and os.getenv("RD_CONFIG_USERNAME"):
            username = os.getenv("RD_CONFIG_USERNAME").strip('\'')

if "RD_OPTION_WINRMPASSWORD" in os.environ and os.getenv("RD_OPTION_WINRMPASSWORD"):
    #take password from job
    password = os.getenv("RD_OPTION_WINRMPASSWORD").strip('\'')
else:
    if "RD_CONFIG_PASSWORD_STORAGE_PATH" in os.environ:
        password = os.getenv("RD_CONFIG_PASSWORD_STORAGE_PATH")

quiet = True
if "RD_CONFIG_DEBUG" in os.environ:
    quiet = False

if "RD_CONFIG_KRB5CONFIG" in os.environ:
    krb5config = os.getenv("RD_CONFIG_KRB5CONFIG")

if "RD_CONFIG_KINIT" in os.environ:
    kinit = os.getenv("RD_CONFIG_KINIT")

if "RD_CONFIG_KRBDELEGATION" in os.environ:
    if os.getenv("RD_CONFIG_KRBDELEGATION") == "true":
        krbdelegation = True
    else:
        krbdelegation = False

if "RD_CONFIG_READTIMEOUT" in os.environ:
    readtimeout = os.getenv("RD_CONFIG_READTIMEOUT")

if "RD_CONFIG_OPERATIONTIMEOUT" in os.environ:
    operationtimeout = os.getenv("RD_CONFIG_OPERATIONTIMEOUT")

if "RD_CONFIG_ENABLEDHTTPDEBUG" in os.environ:
    if os.getenv("RD_CONFIG_ENABLEDHTTPDEBUG") == "true":
        enabledHttpDebug = True
    else:
        enabledHttpDebug = False

if "RD_CONFIG_RETRYCONNECTION" in os.environ:
    retryconnection = int(os.getenv("RD_CONFIG_RETRYCONNECTION"))

if "RD_CONFIG_RETRYCONNECTIONDELAY" in os.environ:
    retryconnectiondelay = int(os.getenv("RD_CONFIG_RETRYCONNECTIONDELAY"))

if enabledHttpDebug:
    httpclient_logging_patch(logging.DEBUG)

endpoint = transport+'://'+args.hostname+':'+port
arguments = {"transport": authentication}

if(nossl == True):
    arguments["server_cert_validation"] = "ignore"
else:
    if(transport=="https"):
        arguments["server_cert_validation"] = "validate"
        arguments["ca_trust_path"] = certpath

arguments["credssp_disable_tlsv1_2"] = diabletls12

if(winrmproxy):
    arguments["proxy"] = winrmproxy

if(readtimeout):
    arguments["read_timeout_sec"] = readtimeout

if(operationtimeout):
    arguments["operation_timeout_sec"] = operationtimeout

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

copy = CopyFiles(session, retryconnection, retryconnectiondelay)

destination = args.destination
filename = ntpath.basename(args.destination)
if filename is None:
    filename = os.path.basename(args.source)

if filename in args.destination:
    destination = destination.replace(filename, '')
else:
    isFile = common.check_is_file(args.destination)
    if isFile:
        filename = common.get_file(args.destination)
        destination = destination.replace(filename, '')
    else:
        filename = os.path.basename(args.source)

if not os.path.isdir(args.source):
    copy.winrm_upload(remote_path=destination,
                      remote_filename=filename,
                      local_path=args.source,
                      quiet=quiet,
                      override=override)
else:
    log.warn("The source is a directory, skipping copy")

