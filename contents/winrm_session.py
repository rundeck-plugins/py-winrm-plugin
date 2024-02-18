from __future__ import unicode_literals
import xml.etree.ElementTree as ET

try:
    import os;

    os.environ['PATH']
except:
    import os

    os.environ.setdefault('PATH', '')
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
try:
    from BytesIO import BytesIO
except ImportError as e:
    from io import BytesIO

try:
    import protocol
    import winrm
except ImportError:
    pass

import base64
import sys
import types
import re
import time
import logging
from requests import ConnectionError

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3
PY34 = sys.version_info[0:2] >= (3, 4)
RD = "RD_"
INVALID_CHAR = "%"

if PY3:
    string_types = str,
    integer_types = int,
    class_types = type,
    text_type = str
    binary_type = bytes

    MAXSIZE = sys.maxsize
else:
    string_types = basestring,
    integer_types = (int, long)
    class_types = (type, types.ClassType)
    text_type = unicode
    binary_type = str

log = logging.getLogger()

# TODO: this PR https://github.com/diyan/pywinrm/pull/55 will add this fix.
# when this PR is merged, this won't be needed anymore
def run_cmd(self, command, args=(), out_stream=None, err_stream=None, retry=1, retry_delay=0, output_charset='utf-8'):
    self.protocol.get_command_output = protocol.get_command_output
    winrm.Session._clean_error_msg = self._clean_error_msg

    retryCount = 0

    envs = {}
    for a in os.environ:
        if a.startswith(RD) and INVALID_CHAR not in os.environ[a]:
            envs.update({a: os.getenv(a)})

    shell_id = None

    DEFAULT_CODEPAGE = 65001
    codepage = DEFAULT_CODEPAGE
    if "RD_NODE_CODEPAGE" in os.environ:
        codepage = os.getenv("RD_NODE_CODEPAGE")

    while retryCount < retry:
        try:
            shell_id = self.protocol.open_shell(codepage=codepage, env_vars=envs)
            break
        except ConnectionError as e:
            if retryCount < retry:
                retryCount += 1
                log.debug("error connecting " + str(e))
                log.debug("Retrying connection " + str(retryCount) + "/" + str(retry) + " in " + str(retry_delay) + " seconds")
                time.sleep(retry_delay)
            else:
                break


    if shell_id is None:
        raise Exception("Connection failed after {0} retries".format(retry))

    command_id = self.protocol.run_command(shell_id, command, args)
    rs = Response(self.protocol.get_command_output(self.protocol, shell_id, command_id, out_stream, err_stream))

    error = self._clean_error_msg(rs.std_err, output_charset)
    rs.std_err = error

    self.protocol.cleanup_command(shell_id, command_id)
    self.protocol.close_shell(shell_id)
    return rs


def run_ps(self, script, out_stream=None, err_stream=None, retry=1, retry_delay=0, output_charset='utf-8'):
    """base64 encodes a Powershell script and executes the powershell
    encoded script command
    """
    script = to_text(script)
    encoded_ps = base64.b64encode(script.encode('utf_16_le')).decode('ascii')
    rs = self.run_cmd('powershell -encodedcommand {0}'.format(encoded_ps),
                      out_stream=out_stream,
                      err_stream=err_stream,
                      output_charset=output_charset,
                      retry=retry,
                      retry_delay=retry_delay)

    return rs


def _clean_error_msg(self, msg, encoding='utf-8'):
    # data=""
    msg = to_text(msg, encoding)

    if msg.startswith("#< CLIXML") or "<Objs Version=" in msg or "-1</PI><PC>" in msg:
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
                new_msg += s.text.replace("_x000D__x000A_", "\n")
        except Exception as e:
            # if any of the above fails, the msg was not true xml
            # print a warning and return the orignal string
            # TODO do not print, raise user defined error instead
            # print("Warning: there was a problem converting the Powershell")
            ignore_error = True
        else:
            # if new_msg was populated, that's our error message
            # otherwise the original error message will be used
            msg = new_msg.strip()

    return msg


def _strip_namespace(self, xml):
    """strips any namespaces from an xml string"""
    value = to_bytes(xml)
    p = re.compile(b"xmlns=*[\"\"][^\"\"]*[\"\"]")
    allmatches = p.finditer(value)
    for match in allmatches:
        value = value.replace(match.group(), b"")
    return value


class Response(object):
    """Response from a remote command execution"""

    def __init__(self, args):
        self.std_out, self.std_err, self.status_code = args

    def __repr__(self):
        # TODO put tree dots at the end if out/err was truncated
        return '<Response code {0}, out "{1}", err "{2}">'.format(
            self.status_code, self.std_out[:20], self.std_err[:20])


class RunCommand:
    def __init__(self, session, shell, command, retry, retry_delay, output_charset='utf-8'):
        self.stat, self.o_std, self.e_std = None, None, None
        self.o_stream = BytesIO()
        self.e_stream = BytesIO()
        self.session = session
        self.exec_command = command
        self.shell = shell
        self.output_charset = output_charset
        self.retry = retry
        self.retry_delay = retry_delay

    def get_response(self):
        try:
            if self.shell == "cmd":
                response = self.session.run_cmd(self.exec_command, out_stream=self.o_stream, err_stream=self.e_stream,
                                                output_charset=self.output_charset, retry=self.retry, retry_delay=self.retry_delay)
                self.o_std = response.std_out
                self.e_std = response.std_err
                self.stat = response.status_code

            if self.shell == "powershell":
                response = self.session.run_ps(self.exec_command, out_stream=self.o_stream, err_stream=self.e_stream,
                                               output_charset=self.output_charset, retry=self.retry, retry_delay=self.retry_delay)
                self.o_std = response.std_out
                self.e_std = response.std_err
                self.stat = response.status_code

        except Exception as e:
            self.e_std = e
            self.stat = -1


def to_text(obj, encoding='utf-8', errors="ignore"):
    if isinstance(obj, text_type):
        return obj

    if isinstance(obj, binary_type):
        return obj.decode(encoding, errors)


def to_bytes(obj, encoding='utf-8', errors="ignore"):
    if isinstance(obj, binary_type):
        return obj

    if isinstance(obj, text_type):
        try:
            # Try this first as it's the fastest
            return obj.encode(encoding, errors)
        except UnicodeEncodeError:
            raise
