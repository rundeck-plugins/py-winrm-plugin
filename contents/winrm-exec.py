import winrm
import argparse
import os
import sys
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()
from winrm.protocol import Protocol

parser = argparse.ArgumentParser(description='Run Bolt command.')
parser.add_argument('hostname', help='the hostname')
args = parser.parse_args()

password=None
authentication = "basic"
transport = "http"
port = "5985"
nossl=False
debug=False
shell = "cmd"
certpath = None

if "RD_CONFIG_PASSWORD_STORAGE_PATH" in os.environ:
    password = os.getenv("RD_CONFIG_PASSWORD_STORAGE_PATH")

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

if "RD_CONFIG_SHELL" in os.environ:
    shell = os.getenv("RD_CONFIG_SHELL")

if os.getenv("RD_JOB_LOGLEVEL") == "DEBUG":
    debug = True

if "RD_CONFIG_CERTPATH" in os.environ:
    certpath = os.getenv("RD_CONFIG_CERTPATH")

exec_command = os.getenv("RD_EXEC_COMMAND") 

endpoint=transport+'://'+args.hostname+':'+port

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

if(debug):
    print "------------------------------------------"
    print "endpoint:" +endpoint
    print "authentication:" +authentication
    print "username:" +username
    print "nossl:" + str(nossl)
    print "------------------------------------------"

arguments = {}
arguments["transport"] = authentication

if(nossl == True):
    arguments["server_cert_validation"] = "ignore"
else:
    if(transport=="https"):
        arguments["server_cert_validation"] = "validate"
        arguments["ca_trust_path"] = certpath

session = winrm.Session(target=endpoint,
                        auth=(username, password),
                        **arguments)

if shell == "cmd":
    result = session.run_cmd(exec_command)

if shell == "powershell":
    result = session.run_ps(exec_command)

print result.std_out

if(result.std_err):
    print result.std_err

sys.exit(result.status_code)
