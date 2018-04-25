import winrm
import os
import sys


if "RD_CONFIG_HOSTNAME" in os.environ:
    hostname = os.getenv("RD_CONFIG_HOSTNAME")

if "RD_CONFIG_USERNAME" in os.environ:
    username = os.getenv("RD_CONFIG_USERNAME")

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


if os.getenv("RD_JOB_LOGLEVEL") == "DEBUG":
    debug = True

endpoint=transport+'://'+hostname+':'+port


if(nossl):
    session  = winrm.Session(endpoint, auth=(username, password),
                                       transport=authentication,
                                       server_cert_validation='ignore')
else:
    session  = winrm.Session(endpoint, auth=(username, password),
                                       transport=authentication)

exec_command = "ipconfig"
result = session.run_cmd(exec_command)

if(result.std_err):
    print "Connection with host %s fail" % hostname
    sys.exit(1)
else:
    print "Connection with host %s successfull" % hostname
