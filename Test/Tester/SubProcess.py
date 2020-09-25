"""Extended ``subprocess`` module.

This provides a `Popen` object based on the ``subprocess.Popen``, but this
is designed to play nicely with the PollManager.

This also provides the following standard library replacements:

    - `os.system`

These should produce the same results, but are implmeneted to allow the
the test framework to provide status updates.

"""
__docformat__ = "restructuredtext"


import subprocess
from subprocess import PIPE
import fcntl
import time
import errno

import os

import cleversheep3
from cleversheep3.Test.Tester import Suites
from cleversheep3.Test.Tester import Coordinator

_system = None
_getstatusoutput = None
_getoutput = None
_Popen = None


def egregiouslyMonkeyPatch():
    """This monkey patches the functions in some standard modules with
    cleversheep3 replacements.

    The patched functions are:

    - os.system
    - subprocess.Popen

    The replacement versions attempt to behave in a compatible manner, but
    they allow the Tester status line to be updated appropriately.

    The original versions are made available as ``cs_system``, ``cs_Popen``,
    *etc.* This allows 'cleversheep3 aware' code to avoid 'polluting' the
    status line.

    """
    global _system, _getstatusoutput, _Popen, _getoutput

    if _system is not None:
        return

    os.cs_system = os.system
    subprocess.cs_Popen = subprocess.Popen

    _system = os.system
    _Popen = subprocess.Popen

    os.system = system
    subprocess.Popen = Popen


def unPatch():
    global _system
    if _system is None:
        return

    os.system = _system
    subprocess.Popen = _Popen

    _system = None


class Struct:
    pass


class CS_Popen(subprocess.Popen):
    """A replacement for subprocess.Popen, which updates the status line.

    This version also supports a number of additional arguments, which
    allow more useful inrofmation to be displayed in the status line.

    """
    def __init__(self, *args, **kwargs):
        """Constructor:

        :Parameters:
        :Keywords:
          callback_interval
            Not yet used: Defines the interval in seconds between calls to the
            callback_function.

          callback_function
            Note yet used: A function to be called regularly.

          progString
            A string to display in the status line as the description of the
            program being executed. The line will show::

                Running: <progString>

          message
            The message to be put in the status line. If provided and not
            ``None`` this will be used in preference to the progString.

        """
        callback_interval = kwargs.pop("callback_interval", None)
        callback_function = kwargs.pop("callback_function", None)
        progString = kwargs.pop("progString", None)
        message = kwargs.pop("message", None)
        super(CS_Popen, self).__init__(*args, **kwargs)
        self.callback_interval = callback_interval
        self.callback_function = callback_function
        self._pollman = Suites.control().poll
        self._args = (args, kwargs)
        self._start_time = time.time()
        self._progString = progString
        self._message = message
        self._initStatus()

    def _initStatus(self):
        status = Coordinator.getServiceProvider("status")
        if self._message:
            status.setField("commentary", "%s" % (self._message))
        elif self._progString:
            status.setField("commentary", "Running: %s" % (
                repr(self._progString,)))
        else:
            status.setField("commentary", "Running: %s" % (
                self._args,))

    def _update(self):
        status = Coordinator.getServiceProvider("status")
        if self.poll() is not None:
            self._pollman.quit()
        status.setField("delay", "T:%5.1f"
                % (time.time() - self._start_time))
        status.update()

    def wait(self):
        tid = self._pollman.addRepeatingTimeout(0.05, self._update)
        try:
            self._pollman.run()
        finally:
            self._pollman.removeTimeout(tid)
        return super(CS_Popen, self).wait()

    def communicate(self, input=None, **kwargs):
        """Interact with process until it terminates.

        This is like ``subprocess.Popen.communicate``, but uses the
        PollManager to manage the pipes to the subprocess.

        :Parameters:
          input
            The optional input argument should be a string to be sent to the
            child process, or ``None``, if no data should be sent to the child.

        :Return:
            A tuple (stdout, stderr).

        """
        data = Struct()
        blockSize = 1024
        def do_io_op(op, *args, **kwargs):
            hack = kwargs.get("hack", False)
            try:
                ret = op(*args)
                if ret is None:
                    try:
                        return len(args[-1])
                    except TypeError:
                        pass
                return ret
            except IOError as exc:
                # In earlier versions of Python3 we get an incorrect IOError if
                # the underlying raw I/O returns None. This appears fixed in
                # Python3.3 (currently in alpha).
                s = str(exc)
                if "length -1" in s and hack:
                    # Treat this as EAGAIN.
                    return None
                try:
                    if exc.characters_written > 0:
                        return exc.characters_written
                except AttributeError:
                    pass
                if exc.args[0] == errno.EAGAIN:
                    return None
                return ""

        def on_stdin(*args):
            while data.stdin:
                n = do_io_op(self.stdin.write, data.stdin[:blockSize],
                        hack=True)
                if n is None:
                    return
                elif n == "":
                    break
                data.stdin = data.stdin[n:]

            self._pollman.removeOutputCallback(self.stdin)
            data.fileCount -= 1
            self.stdin.close()

        def do_read(f, buf):
            while True:
                s = do_io_op(f.read, blockSize)
                if s is None:
                    return
                elif not s:
                    self._pollman.removeInputCallback(f)
                    f.close()
                    return
                else:
                    # TODO: The decode below is possibly the wrong answer.
                    buf.append(s.decode("ascii"))

        def on_stdout(*args):
            do_read(self.stdout, data.stdout)

        def on_stderr(*args):
            do_read(self.stderr, data.stderr)

        data.stdin = input
        data.stdout = []
        data.stderr = []
        data.fileCount = 0

        if self.stdin:
            fcntl.fcntl(self.stdin, fcntl.F_SETFL, os.O_NDELAY)
            self._pollman.addOutputCallback(self.stdin, on_stdin)
            data.fileCount += 1
        if self.stdout:
            fcntl.fcntl(self.stdout, fcntl.F_SETFL, os.O_NDELAY)
            self._pollman.addInputCallback(self.stdout, on_stdout)
            data.fileCount += 1
        if self.stderr:
            fcntl.fcntl(self.stderr, fcntl.F_SETFL, os.O_NDELAY)
            self._pollman.addInputCallback(self.stderr, on_stderr)
            data.fileCount += 1

        tid = self._pollman.addRepeatingTimeout(0.05, self._update)
        try:
            self._pollman.run()
        finally:
            self._pollman.removeTimeout(tid)
        self.wait()

        stdout = stderr = None
        if self.stdout:
            stdout = "".join(data.stdout)
        if self.stderr:
            stderr = "".join(data.stderr)
        return stdout, stderr

    def _handle_exitstatus(self, sts):
        """Version of Popen._handle_exitstatus, preserves full exist status."""
        self.exitstatus = sts
        return super(CS_Popen, self)._handle_exitstatus(sts)


def system(cmd):
    status = Coordinator.getServiceProvider("status")
    pollman = Suites.control().poll
    if pollman.active:
        return _system(cmd)

    try:
        proc = CS_Popen(cmd, shell=True, progString=cmd)
        return proc.wait()
    finally:
        status.setField("commentary", "")
        status.update()


def getstatusoutput(cmd):
    status = Coordinator.getServiceProvider("status")
    pollman = Suites.control().poll
    if pollman.active:
        return _getstatusoutput(cmd)

    try:
        cmd = '{ ' + cmd + '; } 2>&1'
        proc = CS_Popen(cmd, shell=True, progString=cmd, stdout=subprocess.PIPE)
        stdout, stdin = proc.communicate()
        return proc.exitstatus, stdout
    finally:
        status.setField("commentary", "")
        status.update()


def getoutput(cmd):
    return getstatusoutput(cmd)[1]


def Popen(*args, **kwargs):
    pollman = Suites.control().poll
    if not pollman.active:
        return CS_Popen(*args, **kwargs)

    callback_interval = kwargs.pop("callback_interval", None)
    callback_function = kwargs.pop("callback_function", None)
    progString = kwargs.pop("progString", None)
    message = kwargs.pop("message", None)
    return _Popen(*args, **kwargs)
