import os
import json

try:
    import pexpect
except ImportError as e:
    pass


class KerberosAuth(object):
    def __init__(self, krb5config, kinit_command, log, username, password):
        self.krb5config = krb5config
        self.kinit_command = kinit_command
        self.log = log
        self.username = username
        self.password = password

        # Derive a per-execution credential cache path so concurrent executions
        # never share the same cache file (RUN-2869: concurrent kinit race condition).
        # RD_JOB_EXECID is injected by Rundeck and is unique per execution; fall back
        # to the OS process ID when running outside of Rundeck (e.g. tests).
        exec_id = os.environ.get("RD_JOB_EXECID", str(os.getpid()))
        self.ccache_path = "/tmp/krb5cc_rundeck_{}".format(exec_id)
        self.ccache_env = "FILE:{}".format(self.ccache_path)

    def get_ticket(self):
        kinit = [self.kinit_command]

        kinit_arg = []
        kinit_arg.append("-f")
        kinit_arg.append("-V")
        kinit_arg.append(self.username)

        self.log.debug("running kinit %s" %kinit)

        # Build the child environment from the current process env so that kinit
        # has access to PATH, LANG, LD_LIBRARY_PATH, etc.  Only override the
        # Kerberos-specific variables so the per-execution cache is used.
        krb5env = os.environ.copy()
        krb5env["KRB5CCNAME"] = self.ccache_env
        if(self.krb5config):
            os.environ["KRB5_CONFIG"]=self.krb5config
            krb5env["KRB5_CONFIG"] = self.krb5config

        # Set KRB5CCNAME in the current process so requests_kerberos reads the
        # correct per-execution cache during the subsequent WinRM SPNEGO handshake.
        os.environ["KRB5CCNAME"] = self.ccache_env
        self.log.debug("using kerberos cache: %s" % self.ccache_env)

        try:
            process = pexpect.spawn(kinit.pop(0), kinit_arg, timeout=60, env=krb5env)
        except pexpect.ExceptionPexpect as err:
            msg = "Error creating kerberos ticket %s" % err
            self.log.error(msg)
            raise Exception(msg)

        process.expect("Password for .*:")
        process.sendline(self.password)

        output = process.read()
        process.wait()
        self.log.debug("Exist status: %s" %process.exitstatus)

        exitCode = process.exitstatus

        if exitCode != 0:
            msg = "kinit failed"
            self.log.error(msg)
            raise Exception(msg)

        self.log.debug("kinit succeeded for %s" % self.username)

    def cleanup(self):
        """Remove the per-execution credential cache file.

        Must be called in a finally block after WinRM execution completes so
        that temporary Kerberos ticket files do not accumulate on the Runner host.
        Silently ignores missing files to keep caller code simple.
        """
        try:
            if self.ccache_path and os.path.exists(self.ccache_path):
                os.remove(self.ccache_path)
                self.log.debug("removed kerberos cache: %s" % self.ccache_path)
        except OSError:
            pass


    #just for macos (skipped by the moment)
    def check_ticket(self):
        try:

            klist_command = ["klist"]
            kinit_arg = []
            kinit_arg.append("--list-all")
            kinit_arg.append("--json")
            self.log.debug("running klist %s %s" % (klist_command,kinit_arg))

            krb5env = ()
            if (self.krb5config):
                os.environ["KRB5_CONFIG"] = self.krb5config
                krb5env = dict(KRB5_CONFIG=self.krb5config)

            try:
                process = pexpect.spawn(klist_command.pop(0), kinit_arg, timeout=60,
                                        env=krb5env, echo=False)
            except pexpect.ExceptionPexpect as err:
                msg = "Error checking klist %s" % err
                self.log.error(msg)
                return False

            process.expect("Password for .*")
            output = process.read()
            process.wait()
            if process.exitstatus != 0:
                return False

            results = json.loads(output)

            for item in results:
                ticket_name=item["Name"]
                expired=item["Expired"]

                if ticket_name.upper() == self.username.upper():
                    self.log.debug("Ticket found for user %s, expired: %s"%(ticket_name, expired))
                    if expired == "no":
                        self.log.debug("Ticket not expired, skipping kinit")

                        return True

            return False
        except Exception as e:
            self.log.debug("error running klist command : %s" %e)
            return False
