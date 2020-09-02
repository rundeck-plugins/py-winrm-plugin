## Rundeck Python-Winrm Plugin

This is a Rundeck Node Execution/ File Copier plugin that uses WinRM to connect to Windows and execute commands and scripts. It uses the python WinRM Library to provide the WinRM implementation.

## Install 

Download from the releases page and copy the py-winrm-plugin-X.X.X.zip to the libext/ directory for Rundeck.

## Requirements

* Linux, Mac OS X or Windows
* CPython 2.6-2.7, 3.3-3.5 or PyPy2
* pywinrm
* requests-kerberos and requests-credssp is optional

It can be installed with the following command: `pip install pywinrm` 

For further information see: 
[Python Winrm Requirements](https://github.com/diyan/pywinrm/#requirements)

* To install requests-kerberos [See](https://github.com/diyan/pywinrm/#to-use-kerberos-authentication-you-need-these-optional-dependencies)
* To install requests-credssp  [See](https://github.com/diyan/pywinrm/#to-use-credssp-authentication-you-need-these-optional-dependencies)

## Configuration

* **Authentication Type**: The authentication type used for the connection: basic, ntlm, credssp, kerberos. It can be overwriting at node level using `winrm-authtype`
* **Username**: (Optional) Username that will connect to the remote node. This value can be set also at node level or as a job input option (with the name `username`)
* **Password Storage Path**: Key storage path of the window's user password. It can be overwriting at node level using `winrm-password-storage-path`. 
  Also the password can be overwritten on the job level using an input secure option called `winrmpassword`
* **No SSL Verification**: When set to true SSL certificate validation is not performed.  It can be overwriting at node level using `winrm-nossl`
* **WinRM Transport Protocol**: WinRM transport protocol (http or https). It can be overwriting at node level using `winrm-transport`
* **WinRM Port**: WinRM port (Default: 5985/5986 for http/https). It can be overwriting at node level using `winrm-port`
* **Shell**: Windows Shell interpreter (powershell o cmd).  It can be overwriting at node level using `winrm-shell`
* **Script Exit Behaviour**: Script Exit Behaviour. console: if the std error console has data (default), the process fails. exitcode: script won't fail by default, the user must control the exit code (eg: using try/catch block). See https://github.com/rundeck-plugins/py-winrm-plugin/tree/master#running-scripts
* **connect/read times out**: maximum seconds to wait before an HTTP connect/read times out (default 30). This value should be slightly higher than operation timeout, as the server can block *at least* that long.  
It can be overwriting at node level using `winrm-readtimeout`
* **operation timeout**: maximum allowed time in seconds for any single wsman HTTP operation (default 20). Note that operation timeouts while receiving output (the only wsman operation that should take any significant time, and where these timeouts are expected) will be silently retried indefinitely.
It can be overwriting at node level using `winrm-operationtimeout`

For Kerberos
* **krb5 Config File**: path of the krb5.conf (default: /etc/krb5.conf)
* **Kinit Command**: `kinit` command used for create ticket (default: kinit)

## Node definition example


```
<node name="Hostname" 
      description="Windows Server" 
      tags="windows" 
      hostname="192.168.0.1" 
      osArch="amd64" 
      osFamily="windows" 
      osName="Windows Server 2012 R2" 
      osVersion="6.3" 
      username="rundeckuser@domain.local" 
      winrm-password-storage-path="keys/node/windows.password"
      winrm-authtype="basic"/>
```
 
The username can be overwritten using a job input option called "username"` or it can be set at project level.
 
## Transport methods
The transport methods supported are:

* basic
* kerberos
* ntlm
* credssp

Further information [here](https://github.com/diyan/pywinrm#valid-transport-options)


### CredSSP

To use CredSSP authentication you need these optional dependencies
```
pip install pywinrm[credssp]
```

## Kerberos

The pywinrm library has support for kerberos authentication, but it cannot create the kerberos ticket, which needs to be initiate outside the pywinrm scope:

```
kerberos: Will use Kerberos authentication for domain accounts which only works when the client is in the same domain as the server and the required dependencies are installed. Currently a Kerberos ticket needs to be initialized outside of pywinrm using the kinit command.

```
Source [here](https://github.com/diyan/pywinrm#valid-transport-options)


So, in order to connect to a windows box using kerberos we added a call to the `kinit username` command before connecting to the node.

In resume, to use Kerberos authentication the following requirements are needed:

* domain accounts which only works when the client is in the same domain as the server
* kerberos client installed
* domain set on krb5.conf file (default /etc/krb5.conf)
* python `pexpect` library
* python `kerberos` library 
* Kerberos authentication enabled on remote windows node (WINRM settings)

### Install Basic dependencies
#### for Debian/Ubuntu/etc:

```
$ sudo apt-get install python-dev libkrb5-dev
$ pip install pywinrm[kerberos]
$ pip install requests-kerberos
$ pip install pexpect
```

#### for RHEL/CentOS/etc:
```
$ sudo yum install python-devel krb5-devel krb5-workstation requests-kerberos
$ pip install pywinrm[kerberos]
$ pip install requests-kerberos
$ pip install pexpect
```


## Limitations
 
Don't use the file copier to transfer big files, the performance is not the best to transfer large files. It works OK passing inline scripts to remote windows nodes


## Check Step/Script

This plugin include a connectivity test script that can be used as a Workflow Step or it could be called it directly, for example:

```
python contents/winrm-check.py --username <username> --hostname <windows-server> --password <password>
```

## Running Scripts

From version 2.0.8, we added a config option to control the way a script finishes (about success/failure status)

The option called `Script Exit Behaviour` defines the behavior of scripts step status.

* **console**:  This is the default behavior and the way previous versions work. The script will fail if there are any logs in the error console (stderr).
In some cases, a script can return a warning which will produce that the step fails.

* **exitcode**:  This is the new approach. The script step will fail if the exit code is set manually.
So if you need to control errors, you will need to find the way to capture the exit code of your commands inside the script, for example:

* Option 1: check the last exit code
```
# some code with error
get-services

# if last exit code is not zero, return a value 
if ($lastExitCode -ne "0") {
    exit 1
}

```

* Option 2: add a try/catch block

```
try {
    # some code with error
    get-services
}
catch {
    Write-Error $_
    exit 1
}
```

## Troubleshooting

If you get the following error:

```
module object has no attribute 'SSL_ST_INIT'
```

Update your version of PyOpenSSL:

```
python -m easy_install --upgrade pyOpenSSL
```
If you get the following error after run a PowerShell Script:
```
Failed: NonZeroResultCode: [WinRM Python] Result code: 1
```
Configure the Script Invocation Script as:
```
powershell.exe -ExecutionPolicy Bypass
```


## Docker example
Check these [instructions](docker/README.md) for docker test 
