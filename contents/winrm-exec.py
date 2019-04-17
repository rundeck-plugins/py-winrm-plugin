import argparse
try:
	import os; os.environ['PATH']
except:
	import os
	os.environ.setdefault('PATH', '')
import sys
import requests.packages.urllib3
import winrm_session
import threading
import traceback
import winrm
import logging
import colored_formatter
from colored_formatter import ColoredFormatter
requests.packages.urllib3.disable_warnings()

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

if os.getenv("RD_JOB_LOGLEVEL") == "DEBUG":
    debug = True

if "RD_CONFIG_CERTPATH" in os.environ:
    certpath = os.getenv("RD_CONFIG_CERTPATH")

exec_command = os.getenv("RD_EXEC_COMMAND") 

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

log.debug("------------------------------------------")
log.debug("endpoint:" + endpoint)
log.debug("authentication:" + authentication)
log.debug("username:" + username)
log.debug("nossl:" + str(nossl))
log.debug("diabletls12:" + str(diabletls12))
log.debug("shell:" + shell)
log.debug("------------------------------------------")

arguments = {}
arguments["transport"] = authentication

if(nossl == True):
    arguments["server_cert_validation"] = "ignore"
else:
    if(transport == "https"):
        arguments["server_cert_validation"] = "validate"
        arguments["ca_trust_path"] = certpath

arguments["credssp_disable_tlsv1_2"] = diabletls12

session = winrm.Session(target=endpoint,
                        auth=(username, password),
                        **arguments)

winrm.Session.run_cmd = winrm_session.run_cmd
winrm.Session.run_ps = winrm_session.run_ps
winrm.Session._clean_error_msg = winrm_session._clean_error_msg

tsk = winrm_session.RunCommand(session, shell, exec_command)
t = threading.Thread(target=tsk.get_response)
t.start()
realstdout = sys.stdout
realstderr = sys.stderr
sys.stdout = tsk.o_stream
sys.stderr = tsk.e_stream

lastpos = 0
lasterrorpos = 0

charset = "Windows-1252"
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

    if sys.stderr.tell() != lasterrorpos:
        try:
            sys.stderr.seek(lasterrorpos)
            errorread=session._clean_error_msg(sys.stderr.read())
            if isinstance(errorread, str):
                realstdout.write(errorread)
            else:
                realstdout.write(errorread.decode(charset))
            lasterrorpos = sys.stderr.tell()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    if not t.is_alive():
        break

sys.stdout.seek(0)
sys.stderr.seek(0)
sys.stdout = realstdout
sys.stderr = realstderr

if tsk.e_std:
    sys.stderr.write("Execution finished with the following error:\n %s" % tsk.e_std)
    sys.exit(1)
else:
    sys.exit(tsk.stat)