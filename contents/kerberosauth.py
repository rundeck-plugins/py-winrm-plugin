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



    def get_ticket(self):
        kinit = [self.kinit_command]

        kinit_arg = []
        kinit_arg.append("-f")
        kinit_arg.append("-V")
        kinit_arg.append(self.username)

        self.log.debug("running kinit %s" %kinit)

        krb5env=()
        if(self.krb5config):
            os.environ["KRB5_CONFIG"]=self.krb5config
            krb5env = dict(KRB5_CONFIG=self.krb5config)

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
