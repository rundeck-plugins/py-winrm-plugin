import xml.etree.ElementTree as ET
import xmltodict
import base64

from winrm.exceptions import WinRMError, WinRMTransportError, WinRMOperationTimeoutError

# TODO: this PR https://github.com/diyan/pywinrm/pull/55 will add this fix.
# when this PR is merged, this won't be needed anymore


def get_command_output(protocol, shell_id, command_id, out_stream=None, err_stream=None):
    """
    Get the Output of the given shell and command
    @param string shell_id: The shell id on the remote machine.
     See #open_shell
    @param string command_id: The command id on the remote machine.
     See #run_command
    @param stream out_stream: The stream of which the std_out would be directed to. (optional)
    @param stream err_stream: The stream of which the std_err would be directed to. (optional)
    #@return [Hash] Returns a Hash with a key :exitcode and :data.
     Data is an Array of Hashes where the cooresponding key
    #   is either :stdout or :stderr.  The reason it is in an Array so so
     we can get the output in the order it ocurrs on
    #   the console.
    """
    stdout_buffer, stderr_buffer = [], []
    command_done = False
    while not command_done:
        try:
            stdout, stderr, return_code, command_done = \
                _raw_get_command_output(protocol, shell_id, command_id, out_stream, err_stream)

            stdout_buffer.append(stdout)
            stderr_buffer.append(stderr)
        except WinRMOperationTimeoutError as e:
            # this is an expected error when waiting for a long-running process, just silently retry
            pass
    return b''.join(stdout_buffer), b''.join(stderr_buffer), return_code


def _raw_get_command_output(protocol,shell_id, command_id, out_stream=None, err_stream=None):
    req = {'env:Envelope': protocol._get_soap_header(
        resource_uri='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd',  # NOQA
        action='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Receive',  # NOQA
        shell_id=shell_id)}

    stream = req['env:Envelope'].setdefault('env:Body', {}).setdefault(
        'rsp:Receive', {}).setdefault('rsp:DesiredStream', {})
    stream['@CommandId'] = command_id
    stream['#text'] = 'stdout stderr'

    res = protocol.send_message(xmltodict.unparse(req))
    root = ET.fromstring(res)
    stream_nodes = [
        node for node in root.findall('.//*')
        if node.tag.endswith('Stream')]
    stdout = stderr = b''
    return_code = -1
    for stream_node in stream_nodes:
        if not stream_node.text:
            continue

        content = base64.b64decode(stream_node.text.encode('ascii'))

        if stream_node.attrib['Name'] == 'stdout':
            if out_stream:
                out_stream.write(content)
            stdout += content
        elif stream_node.attrib['Name'] == 'stderr':
            if err_stream:
                err_stream.write(content)
            stderr += content

    command_done = len([
        node for node in root.findall('.//*')
        if node.get('State', '').endswith('CommandState/Done')]) == 1
    if command_done:
        return_code = int(
            next(node for node in root.findall('.//*')
                 if node.tag.endswith('ExitCode')).text)

    return stdout, stderr, return_code, command_done

