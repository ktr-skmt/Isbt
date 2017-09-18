from ipykernel.kernelbase import Kernel
from telnetlib import Telnet

import datetime
import re
import signal

HOST = 'localhost'
PORT = 12700
ENCODING = 'ascii'

crlf_pattern = re.compile(r'[\r\n]+')
problem_ew_regex = r'{"type":"xsbti.Problem","message":{"category":"","severity":"%s","message":"(?P<message>[^"]+)","position":{"line":(?P<position_line>\d+),"lineContent":"(?P<position_lineContent>[^"]+)","offset":(?P<position_offset>\d+),"pointer":(?P<position_pointer>\d+),"pointerSpace":"(?P<position_pointerSpace> *)","sourcePath":"(?P<position_sourcePath>[^"]+)","sourceFile":"file:(?P<position_sourceFile>[^"]+)"}},"level":"%s","channelName":"channel-\d+","execId":"[^"]+"}'
problem_error_regex = problem_ew_regex % ('Error', 'error')
problem_warn_regex = problem_ew_regex % ('Warn', 'warn')
problem_error_pattern = re.compile(problem_error_regex)
problem_warn_pattern = re.compile(problem_warn_regex)
string_event_pattern = re.compile(
    r'{"type":"StringEvent","level":"info","message":"(?P<message>[^"]+)","channelName":"channel-\d+","execId":"[^"]+"}')
ew_regex = r'{"type":"StringEvent","level":"%s","message":"(?P<message>[^"]+)","channelName":"channel-\d+","execId":"[^"]+"}'
error_regex = ew_regex % 'error'
warn_regex = ew_regex % 'warn'
error_pattern = re.compile(error_regex)
warn_pattern = re.compile(warn_regex)


def matcher_to_message(message: str, line: str, line_content: str, offset: str,
                       pointer: str, pointer_space: str, source_path: str, source_file: str, is_error: bool) -> str:
    ret = ''
    if is_error:
        ret += '[\x1b[31;1merror'
    else:
        ret += '[\x1b[33;1mwarn'
    ret += '\x1b[30m] '
    ret += message + '\n'
    ret += 'line: %s\n' % line
    ret += 'line content: %s\n' % line_content
    ret += 'offset: %s\n' % offset
    ret += 'pointer: %s\n' % pointer
    ret += 'pointer space: "%s"\n' % pointer_space
    ret += 'source path: %s\n' % source_path
    ret += 'source file: %s\n' % source_file
    return ret


class SBTKernel(Kernel):
    implementation: 'SBTKernel'
    implementationVersion: '0.0.1'
    language_info = {
        'name': 'sbt',
        'codemirror_mode': 'scheme',
        'mimetype': 'text/plain',
        'file_extension': '.sbt'
    }
    language_version = '1.0.0'
    banner = 'SBT Kernel ' + language_version

    def __init__(self, **kwargs):
        Kernel.__init__(self, **kwargs)
        self.silent = None

    def process_output(self, output):
        if not self.silent:
            self.send_response(self.iopub_socket, 'stream', {'name': 'stdout', 'text': output})

    def _start_sbt(self, host, port):
        sig = signal.signal(signal.SIGINT, signal.SIG_DFL)
        try:
            self.wrapper = Telnet(host, port)
        finally:
            signal.signal(signal.SIGINT, sig)

    def do_clear(self):
        """DEPRECATED"""
        raise NotImplementedError

    def do_apply(self, content, bufs, msg_id, reply_metadata):
        """DEPRECATED"""
        raise NotImplementedError

    def do_execute(self, code, silent, store_history=True,
                   user_expressions=None, allow_stdin=False):
        command = crlf_pattern.sub('', code.strip())
        if command.startswith('sbt-server'):
            tokens = command.split(' ')
            if len(tokens) == 1:
                self._start_sbt(HOST, PORT)
            elif len(tokens) == 2 and tokens[1] == 'help':
                self.process_output(
                    '[help] sbt-server needs an argument pair of host and port. For example, "sbt-server localhost 334"\n')
                self.process_output(
                    '[help] When sbt-server has no argument, run "sbt-server %s %d" as default\n' % (HOST, PORT))
                self.process_output(
                    '[help] You can add a dedicated port as "serverPort := 12700" in your build.sbt\n')
            elif len(tokens) == 3:
                self._start_sbt(tokens[1], tokens[2])
            else:
                return {
                    'status': 'error',
                    'ename': 'illegal argument exception',
                    'evalue': 'sbt-server needs an argument pair of host and port. For example, "sbt-server localhost 12700"',
                    'traceback': None
                }
            return {
                'status': 'ok',
                'execution_count': self.execution_count,
                'payload': [],
                'user_expressions': {}
            }
        code = '{"type":"ExecCommand","commandLine":"%s"}\n' % command
        if not code:
            return {
                'status': 'ok',
                'execution_count': self.execution_count,
                'payload': [],
                'user_expressions': {}
            }
        start_time = datetime.datetime.today()
        self.wrapper.write(code.encode(ENCODING))
        done = '{"type":"ExecStatusEvent","status":"Done","commandQueue":["%s","shell"]}' % command
        has_no_error = True
        line = ''
        if not silent:
            while not line == done:
                line = self.wrapper.read_until('\n'.encode(ENCODING)).decode(ENCODING).strip()
            while not (line.endswith('"commandQueue":["shell"]}') or line.endswith('"commandQueue":["shell"]}\n')):
                line = crlf_pattern.sub('', self.wrapper.read_until('\n'.encode(ENCODING)).decode(
                    ENCODING).strip()).replace(r'\u001b', '\x1b')
                # self.send_response(self.iopub_socket, 'stream', {
                #    'name': 'stdout',
                #    'text': 'LINE\n' + line + '\n'
                # })
                matcher = string_event_pattern.match(line)
                if matcher is not None:
                    self.process_output('[info] %s\n' % matcher.group('message'))

                def m2m(is_e: bool):
                    self.process_output(matcher_to_message(
                        matcher.group('message'),
                        matcher.group('position_line'),
                        matcher.group('position_lineContent'),
                        matcher.group('position_offset'),
                        matcher.group('position_pointer'),
                        matcher.group('position_pointerSpace'),
                        matcher.group('position_sourcePath'),
                        matcher.group('position_sourceFile'),
                        is_error=is_e
                    ))
                matcher = problem_warn_pattern.match(line)
                if matcher is not None:
                    m2m(is_e=False)
                matcher = problem_error_pattern.match(line)
                if matcher is not None:
                    has_no_error = False
                    m2m(is_e=True)
                matcher = warn_pattern.match(line)
                if matcher is not None:
                    self.process_output('[\x1b[33;1mwarn\x1b[30m] %s\n' % matcher.group('message'))
                matcher = error_pattern.match(line)
                if matcher is not None:
                    self.process_output('[\x1b[31;1merror\x1b[30m] %s\n' % matcher.group('message'))
            completed_time = datetime.datetime.today()
            elapsed_time = completed_time - start_time
            completed = ' Total time: %s, completed %s\n' % (elapsed_time, completed_time)

            if has_no_error:
                self.process_output('[\x1b[32;1msuccess\x1b[30m]' + completed)
            else:
                self.process_output('[\x1b[31;1merror\x1b[30m]' + completed)
        return {
            'status': 'ok',
            'execution_count': self.execution_count,
            'payload': [],
            'user_expressions': {}
        }


# ===== MAIN =====
if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp

    IPKernelApp.launch_instance(kernel_class=SBTKernel)
