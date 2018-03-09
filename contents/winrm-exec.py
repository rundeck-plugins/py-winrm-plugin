import winrm
import argparse
import os
import sys

from winrm.protocol import Protocol


parser = argparse.ArgumentParser(description='Run Bolt command.')
parser.add_argument('username', help='the username')
parser.add_argument('hostname', help='the hostname')
args = parser.parse_args()

password=None
authentication = "basic"
transport = "http"
port = "5985"
nossl=False
debug=False
shell = "cmd"

if "RD_CONFIG_PASSWORD_STORAGE_PATH" in os.environ:
    password = os.getenv("RD_CONFIG_PASSWORD_STORAGE_PATH")

if "RD_CONFIG_AUTHTYPE" in os.environ:
    authentication = os.getenv("RD_CONFIG_AUTHTYPE")

if "RD_CONFIG_WINRMTRANSPORT" in os.environ:
    transport = os.getenv("RD_CONFIG_WINRMTRANSPORT")

if "RD_CONFIG_WINRMPORT" in os.environ:
    port = os.getenv("RD_CONFIG_WINRMPORT")

if "RD_CONFIG_NOSSL" in os.environ:
    nossl = os.getenv("RD_CONFIG_NOSSL")

if "RD_CONFIG_SHELL" in os.environ:
    shell = os.getenv("RD_CONFIG_SHELL")

if os.getenv("RD_JOB_LOGLEVEL") == "DEBUG":
    debug = True


exec_command = os.getenv("RD_EXEC_COMMAND") 

endpoint=transport+'://'+args.hostname+':'+port

username = args.username.strip('\'')

if(debug):
    print "------------------------------------------"
    print "endpoint:" +endpoint
    print "authentication:" +authentication
    print "username:" +username
    print "------------------------------------------"


if(nossl):
    session  = winrm.Session(endpoint, auth=(username, password),
                                       transport=authentication,
                                       server_cert_validation='ignore')
else:
    session  = winrm.Session(endpoint, auth=(username, password),
                                       transport=authentication)

#print exec_command

if shell == "cmd":
    result = session.run_cmd(exec_command)

if shell == "powershell":
    result = session.run_ps(exec_command)


print result.std_out
print result.std_err

sys.exit(result.status_code)
