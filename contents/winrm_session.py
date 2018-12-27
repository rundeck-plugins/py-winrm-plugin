from __future__ import unicode_literals
import re
from base64 import b64encode
import xml.etree.ElementTree as ET
from StringIO import StringIO

from winrm.protocol import Protocol

# TODO: this PR https://github.com/diyan/pywinrm/pull/55 will add this fix.
# when this PR is merged, this won't be needed anymore

# Feature support attributes for multi-version clients.
# These values can be easily checked for with hasattr(winrm, "FEATURE_X"),
# "'auth_type' in winrm.FEATURE_SUPPORTED_AUTHTYPES", etc for clients to sniff features
# supported by a particular version of pywinrm
FEATURE_SUPPORTED_AUTHTYPES=['basic', 'certificate', 'ntlm', 'kerberos', 'plaintext', 'ssl', 'credssp']
FEATURE_READ_TIMEOUT=True
FEATURE_OPERATION_TIMEOUT=True

import protocol

class Response(object):
    """Response from a remote command execution"""
    def __init__(self, args):
        self.std_out, self.std_err, self.status_code = args

    def __repr__(self):
        # TODO put tree dots at the end if out/err was truncated
        return '<Response code {0}, out "{1}", err "{2}">'.format(
            self.status_code, self.std_out[:20], self.std_err[:20])


class Session(object):
    # TODO implement context manager methods
    def __init__(self, target, auth, **kwargs):
        username, password = auth
        self.url = self._build_url(target, kwargs.get('transport', 'plaintext'))
        self.protocol = Protocol(self.url,
                                 username=username, password=password, **kwargs)

    def run_cmd(self, command, args=(), out_stream=None, err_stream=None):

        self.protocol.get_command_output = protocol.get_command_output

        # TODO optimize perf. Do not call open/close shell every time
        shell_id = self.protocol.open_shell()
        command_id = self.protocol.run_command(shell_id, command, args)
        rs = Response(self.protocol.get_command_output(self.protocol, shell_id, command_id, out_stream, err_stream))

        error = self._clean_error_msg(rs.std_err)
        rs.std_err = error

        self.protocol.cleanup_command(shell_id, command_id)
        self.protocol.close_shell(shell_id)
        return rs

    def run_ps(self, script, out_stream=None, err_stream=None):
        """base64 encodes a Powershell script and executes the powershell
        encoded script command
        """
        # must use utf16 little endian on windows
        encoded_ps = b64encode(script.encode('utf_16_le')).decode('ascii')
        rs = self.run_cmd('powershell -encodedcommand {0}'.format(encoded_ps),out_stream=out_stream, err_stream=err_stream)

        return rs

    def _clean_error_msg(self, msg):
        if msg.startswith(b"#< CLIXML\r\n") or "<Objs Version=" or "-1</PI><PC>" in msg:
            new_msg = ""
            msg_xml = msg[11:]
            try:
                # remove the namespaces from the xml for easier processing
                msg_xml = self._strip_namespace(msg_xml)
                root = ET.fromstring(msg_xml)

                # the S node is the error message, find all S nodes
                nodes = root.findall("./S")
                for s in nodes:
                    # append error msg string to result, also
                    # the hex chars represent CRLF so we replace with newline
                    new_msg += s.text.replace("_x000D__x000A_", "\n")
                return new_msg
            except Exception as e:
                # if any of the above fails, the msg was not true xml
                return ""
        else:
            return msg

    def _strip_namespace(self, xml):
        """strips any namespaces from an xml string"""
        p = re.compile(b"xmlns=*[\"\"][^\"\"]*[\"\"]")
        allmatches = p.finditer(xml)
        for match in allmatches:
            xml = xml.replace(match.group(), b"")
        return xml

    @staticmethod
    def _build_url(target, transport):
        match = re.match(
            '(?i)^((?P<scheme>http[s]?)://)?(?P<host>[0-9a-z-_.]+)(:(?P<port>\d+))?(?P<path>(/)?(wsman)?)?', target)  # NOQA
        scheme = match.group('scheme')
        if not scheme:
            # TODO do we have anything other than HTTP/HTTPS
            scheme = 'https' if transport == 'ssl' else 'http'
        host = match.group('host')
        port = match.group('port')
        if not port:
            port = 5986 if transport == 'ssl' else 5985
        path = match.group('path')
        if not path:
            path = 'wsman'
        return '{0}://{1}:{2}/{3}'.format(scheme, host, port, path.lstrip('/'))


class RunCommand:
    def __init__(self, session, shell, command ):
        self.stat, self.o_std, self.e_std = None, None, None
        self.o_stream = StringIO()
        self.e_stream = StringIO()
        self.session = session
        self.exec_command = command
        self.shell = shell

    def get_response(self):
        try:
            if self.shell == "cmd":
                response = self.session.run_cmd(self.exec_command, out_stream=self.o_stream, err_stream=self.e_stream)
                self.o_std = response.std_out
                self.e_std = response.std_err
                self.stat = response.status_code

            if self.shell == "powershell":
                response = self.session.run_ps(self.exec_command, out_stream=self.o_stream, err_stream=self.e_stream)
                self.o_std = response.std_out
                self.e_std = response.std_err
                self.stat = response.status_code

        except Exception as e:
            print(e)
            self.e_std = e
            self.stat=-1
