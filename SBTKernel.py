from enum import Enum
from ipykernel.kernelbase import Kernel
from telnetlib import Telnet

import datetime
import re
import signal

HOST = 'localhost'
PORT = 12700
ENCODING = 'ascii'

crlf_pattern = re.compile(r'[\r\n]+')
problem_regex = r'{"type":"xsbti.Problem","message":{"category":"","severity":"%s","message":"(?P<message>[^"]+)","position":{"line":(?P<position_line>\d+),"lineContent":"(?P<position_lineContent>[^"]+)","offset":(?P<position_offset>\d+),"pointer":(?P<position_pointer>\d+),"pointerSpace":"(?P<position_pointerSpace> *)","sourcePath":"(?P<position_sourcePath>[^"]+)","sourceFile":"file:(?P<position_sourceFile>[^"]+)"}},"level":"%s","channelName":"channel-\d+","execId":"[^"]+"}'
problem_error_pattern = re.compile(problem_regex % ('Error', 'error'))
problem_warn_pattern = re.compile(problem_regex % ('Warn', 'warn'))
string_event_regex = r'{"type":"StringEvent","level":"%s","message":"(?P<message>[^"]+)","channelName":"channel-\d+","execId":"[^"]+"}'
error_pattern = re.compile(string_event_regex % 'error')
warn_pattern = re.compile(string_event_regex % 'warn')
info_pattern = re.compile(string_event_regex % 'info')


class Status(Enum):
    Success = '[\x1b[32;1msuccess\x1b[30m] '
    Warn = '[\x1b[33;1mwarn\x1b[30m] '
    Error = '[\x1b[31;1merror\x1b[30m] '
    Info = '[info] '
    Help = '[help] '
    Debug = '[debug] '


class RunMode(Enum):
    Regular = 0
    Debug = 1


RUN_MODE = RunMode.Regular


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
        self.has_no_error = True

    def process_output(self, output):
        if not self.silent:
            self.send_response(self.iopub_socket, 'stream', {'name': 'stdout', 'text': output + '\n'})

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

    def do_execute(self, code, silent, store_history=True, user_expressions=None, allow_stdin=False):
        command = crlf_pattern.sub('\n', code.strip())
        ok = {
            'status': 'ok',
            'execution_count': self.execution_count,
            'payload': [],
            'user_expressions': {}
        }
        if command.startswith('sbt-server'):
            tokens = command.split(' ')
            if len(tokens) == 1:
                self._start_sbt(HOST, PORT)
            elif len(tokens) == 2 and tokens[1] == 'help':
                header = Status.Help.value
                self.process_output(
                    header + 'sbt-server needs an argument pair of host and port. For example, "sbt-server localhost 334"\n')
                self.process_output(
                    header + 'When sbt-server has no argument, run "sbt-server %s %d" as default\n' % (HOST, PORT))
                self.process_output(
                    header + 'You can add a dedicated port as "serverPort := 12700" in your build.sbt\n')
            elif len(tokens) == 3:
                self._start_sbt(tokens[1], tokens[2])
            else:
                return {
                    'status': 'error',
                    'ename': 'illegal argument exception',
                    'evalue': 'sbt-server needs an argument pair of host and port. For example, "sbt-server localhost 12700"',
                    'traceback': None
                }
            return ok
        code = '{"type":"ExecCommand","commandLine":"%s"}\n' % command
        if not code:
            return ok
        start_time = datetime.datetime.today()
        self.wrapper.write(code.encode(ENCODING))
        done = '{"type":"ExecStatusEvent","status":"Done","commandQueue":["%s","shell"]}' % command
        self.has_no_error = True
        line = ''

        if not silent:
            def display_json_to_debug():
                if RUN_MODE is RunMode.Debug:
                    self.send_response(self.iopub_socket, 'stream', {
                        'name': 'stdout',
                        'text': Status.Debug.value + line + '\n'
                    })
            while not line == done:
                line = self.wrapper.read_until('\n'.encode(ENCODING)).decode(ENCODING).strip()
                display_json_to_debug()
            while not line.endswith('"commandQueue":["shell"]}'):
                line = crlf_pattern.sub('\n', self.wrapper.read_until('\n'.encode(ENCODING)).decode(
                    ENCODING).strip()).replace(r'\u001b', '\x1b')
                display_json_to_debug()

                def to_message(status: Status,
                               message: str,
                               line_: str,
                               line_content: str,
                               offset: str,
                               pointer: str,
                               pointer_space: str,
                               source_path: str,
                               source_file: str) -> str:
                    ret = status.value
                    ret += message + '\n'
                    ret += 'line: %s\n' % line_
                    ret += 'line content: %s\n' % line_content
                    ret += 'offset: %s\n' % offset
                    ret += 'pointer: %s\n' % pointer
                    ret += 'pointer space: "%s"\n' % pointer_space
                    ret += 'source path: %s\n' % source_path
                    ret += 'source file: %s\n' % source_file
                    return ret.strip()

                def string_event_to_message(status: Status):
                    pattern = None
                    if status == Status.Info:
                        pattern = info_pattern
                    elif status == Status.Warn:
                        pattern = warn_pattern
                    elif status == Status.Error:
                        pattern = error_pattern
                    if pattern is not None:
                        matcher = pattern.match(line)
                        if matcher is not None:
                            self.process_output(status.value + matcher.group('message'))
                            if status == Status.Error:
                                self.has_no_error = False

                string_event_to_message(Status.Info)
                string_event_to_message(Status.Warn)
                string_event_to_message(Status.Error)

                def problem_to_message(status: Status):
                    pattern = None
                    if status == Status.Error:
                        pattern = problem_error_pattern
                    elif status == Status.Warn:
                        pattern = problem_warn_pattern
                    if pattern is not None:
                        matcher = pattern.match(line)
                        if matcher is not None:
                            self.process_output(to_message(
                                status,
                                matcher.group('message'),
                                matcher.group('position_line'),
                                matcher.group('position_lineContent'),
                                matcher.group('position_offset'),
                                matcher.group('position_pointer'),
                                matcher.group('position_pointerSpace'),
                                matcher.group('position_sourcePath'),
                                matcher.group('position_sourceFile')
                            ))
                            if status == Status.Error:
                                self.has_no_error = False

                problem_to_message(Status.Warn)
                problem_to_message(Status.Error)

            completed_time = datetime.datetime.today()
            elapsed_time = completed_time - start_time
            completed = 'Total time: %s, completed %s' % (elapsed_time, completed_time)

            if self.has_no_error:
                self.process_output(Status.Success.value + completed)
            else:
                self.process_output(Status.Error.value + completed)
        return ok


# ===== MAIN =====
if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp

    IPKernelApp.launch_instance(kernel_class=SBTKernel)
