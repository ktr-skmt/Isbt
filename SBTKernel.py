from enum import Enum
from ipykernel.kernelbase import Kernel
from telnetlib import Telnet

import datetime
import re
import signal
import os
import pexpect

crlf_pattern = re.compile(r'[\r\n]+')
problem_regex = r'{"type":"xsbti.Problem","message":{"category":"","severity":"%s","message":"(?P<message>[^"]+)","position":{"line":(?P<position_line>\d+),"lineContent":"(?P<position_lineContent>[^"]+)","offset":(?P<position_offset>\d+),"pointer":(?P<position_pointer>\d+),"pointerSpace":"(?P<position_pointerSpace> *)","sourcePath":"(?P<position_sourcePath>[^"]+)","sourceFile":"file:(?P<position_sourceFile>[^"]+)"}},"level":"%s","channelName":"channel-\d+","execId":"[^"]+"}'
problem_error_pattern = re.compile(problem_regex % ('Error', 'error'))
problem_warn_pattern = re.compile(problem_regex % ('Warn', 'warn'))
string_event_regex = r'{"type":"StringEvent","level":"%s","message":"(?P<message>[^"]+)","channelName":"channel-\d+","execId":"[^"]+"}'
error_pattern = re.compile(string_event_regex % 'error')
warn_pattern = re.compile(string_event_regex % 'warn')
info_pattern = re.compile(string_event_regex % 'info')
url_regex = r'\[\x1b\[0m\x1b\[0minfo\x1b\[0m\] \x1b\[0m\x1b\[0msbt server started at (?P<host>[^:]+):(?P<port>\d+)\x1b\[0m\r\nsbt:[^\x1b]+\x1b\[36m> \x1b\[0m'
url_pattern = re.compile(url_regex)
connection_regex = r'\[\x1b\[0m\x1b\[0minfo\x1b\[0m\] \x1b\[0m\x1b\[0mnew client connected from: \d+'
connection_pattern = re.compile(connection_regex)
ENCODING = 'ascii'


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
    implementation = 'SBTKernel'
    implementation_version = '0.1.0'
    language_info = {
        'name': 'sbt',
        'codemirror_mode': 'scheme',
        'mimetype': 'text/plain',
        'file_extension': '.sbt'
    }
    language_version = '1.0.1'
    banner = 'SBT Kernel ' + language_version
    descriptions = [
        '1. sbt-server',
        '   Is a "build.sbt" right under the notebook directory?',
        '   If so, run sbt server and connect it.',
        '   If not, show help texts.',
        '2. sbt-server (sbt project root directory)',
        '   run sbt server and connect it',
        '   ex. "sbt-server /Users/ilham/IdeaProjects/FelisCatusZero"',
        '   Note that a "build.sbt" needs to be right under the root directory',
        '3. sbt-server (host) (port)',
        '   connect to sbt server, but do not run it',
        '   ex. "sbt-server localhost 12700"',
        '   Note that sbt server has to be run beforehand',
        '   Note that you can add a dedicated port as "serverPort := 12700" in your build.sbt',
        '4. sbt-server help',
        '   show help texts'
    ]

    def __init__(self, **kwargs):
        Kernel.__init__(self, **kwargs)
        self.silent = None
        self.has_no_error = True

    def println_(self, status: Status, output: str):
        if output is not '':
            self.println(status.value + output)

    def print(self, output: str):
        if not self.silent and output is not '':
            self.send_response(self.iopub_socket, 'stream', {'name': 'stdout', 'text': output})

    def println(self, output: str):
        self.print(output + '\n')

    def _start_sbt(self, host, port):
        sig = signal.signal(signal.SIGINT, signal.SIG_DFL)
        try:
            self.println_(Status.Info, 'Trying to run "telnet %s %s" to connect to sbt server' % (host, port))
            self.telnet = Telnet(host, port)
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
        error = {
            'status': 'error',
            'ename': 'illegal argument exception',
            'evalue': 'Confirm arguments',
            'traceback': None
        }

        def help_option():
            for description in self.descriptions:
                self.println_(Status.Help, description)

        def connected():
            self.println_(Status.Success, 'Connected!')

        def read_line():
            try:
                l: str = self.telnet.read_until('\n'.encode(ENCODING)).decode(ENCODING).strip()
                l: str = crlf_pattern.sub('\n', l).replace(r'\u001b', '\x1b')
                if RUN_MODE is RunMode.Debug:
                    self.println_(Status.Debug, l)
                return l
            except EOFError:
                return ''

        def run_sbt():
            process = pexpect.spawn('sbt')
            process.expect(url_regex)
            line_ = process.after.decode(ENCODING)
            self.print(process.before.decode(ENCODING))
            self.println(line_)
            url_matcher = url_pattern.match(line_)
            self._start_sbt(url_matcher.group('host'), url_matcher.group('port'))
            process.expect(connection_regex)
            self.print(process.before.decode(ENCODING))
            self.println(process.after.decode(ENCODING))
            process.close()
            connected()

        def has_build_sbt(p: str):
            return os.path.isfile(p + '/build.sbt')

        if command.startswith('sbt-server'):
            tokens = command.split(' ')
            if len(tokens) == 1:
                if has_build_sbt(os.path.curdir):
                    run_sbt()
                else:
                    self.println_(Status.Warn,
                                  'This notebook\'s directory has no build.sbt, so the following help is shown.')
                    help_option()
            elif len(tokens) == 2:
                if tokens[1] == 'help':
                    help_option()
                else:
                    path: str = tokens[1]
                    if os.path.isdir(path) and has_build_sbt(path):
                        os.chdir(path)
                        run_sbt()
                    else:
                        return error
            elif len(tokens) == 3:
                self._start_sbt(tokens[1], tokens[2])
                line = ''
                while not line.startswith(r'{"type":"ChannelAcceptedEvent","channelName":"channel-'):
                    line = read_line()
                connected()
            else:
                return error
        else:
            code = '{"type":"ExecCommand","commandLine":"%s"}\n' % command
            done = '{"type":"ExecStatusEvent","status":"Done","commandQueue":["%s","shell"]}' % command
            if RUN_MODE is RunMode.Debug:
                self.println_(Status.Debug, code)
            self.has_no_error = True
            line = ''
            start_time = datetime.datetime.today()
            self.telnet.write(code.encode(ENCODING))
            if not silent:
                while not line == done:
                    line = read_line()
                while not line.endswith('"commandQueue":["shell"]}'):
                    line = read_line()

                    def to_message(message: str,
                                   line_: str,
                                   line_content: str,
                                   offset: str,
                                   pointer: str,
                                   pointer_space: str,
                                   source_path: str,
                                   source_file: str) -> str:
                        ret = message + '\n'
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
                                self.println_(status, matcher.group('message'))
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
                                self.println_(status, to_message(
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
                    self.println_(Status.Success, completed)
                else:
                    self.println_(Status.Error, completed)
        return ok


# ===== MAIN =====
if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp

    IPKernelApp.launch_instance(kernel_class=SBTKernel)
