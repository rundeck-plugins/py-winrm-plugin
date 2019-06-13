## Rundeck Python-Winrm Plugin

This is a Rundeck Node Execution/ File Copier plugin that uses WinRM to connect to Windows and execute commands and scripts. It uses the python WinRM Library to provide the WinRM implementation.

## Install 

Download from the releases page and copy the py-winrm-plugin-X.X.X.zip to the libext/ directory for Rundeck.

## Requierments

The plugin needs the python module **pywinrm**. It can be installed with the following command: ```pip install pywinrm``` 

For further information see: 
[https://pypi.python.org/pypi/pywinrm
](https://pypi.python.org/pypi/pywinrm)


## Configuration

* **Authentication Type**: The authentication type used for the connection: basic, ntlm, credssp, kerberos. It can be overwriting at node level using `winrm-authtype`
* **Username**: (Optional) Username that will connect to the remote node. This value can be set also at node level or as a job input option (with the name `username)
* **Password Storage Path**: Key storage path of the window's user password. It can be overwriting at node level using `winrm-password-storage-path`. 
  Also the password can be overwritten on the job level using an input secure option called `winrmpassword`
* **No SSL Verification**: When set to true SSL certificate validation is not performed.  It can be overwriting at node level using `winrm-nossl`
* **WinRM Transport Protocol**: WinRM transport protocol (http or https). It can be overwriting at node level using `winrm-transport`
* **WinRM Port**: WinRM port (Default: 5985/5986 for http/https). It can be overwriting at node level using `winrm-port`
* **Shell**: Windows Shell interpreter (powershell o cmd).  It can be overwriting at node level using `winrm-shell`

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
$ pip install pexpect
```

#### for RHEL/CentOS/etc:
```
$ sudo yum install gcc krb5-devel krb5-workstation
$ pip install pywinrm[kerberos]
$ pip install pexpect
```


## Limitations
 
Don't use the file copier to transfer big files, the performance is not the best to transfer large files. It works OK passing inline scripts to remote windows nodes


## Check Step/Script

This plugin include a connectivity test script that can be used as a Workflow Step or it could be called it directly, for example:

```
python contents/winrm-check.py --username <username> --hostname <windows-server> --password <password>
```

## Troubleshooting

If you get the following error:

```
module object has no attribute 'SSL_ST_INIT'
```

Update your verion of PyOpenSSL:

```
python -m easy_install --upgrade pyOpenSSL
```
If you get the following error after run a PowerShell Script:
```
Failed: NonZeroResultCode: [WinRM Python] Result code: 1
```
Please check first if you have disable the ExecutionPolicy on PowerShell
```
Get-ExecutionPolicy
```
If the result is Restricted, please run the following command:
```
Set-ExecutionPolicy -ExecutionPolicy Unrestricted
```


## Docker example
Check these [instructions](docker/README.md) for docker test 