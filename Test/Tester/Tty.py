"""Terminal management.

Provides the `StdTerm` class, which makes it easier to switch terminal
output to/from a file. When this module is imported it effectively does::

    stdout = sys.stdout = StdTerm(sys.__stdout__)
    stderr = sys.stderr = StdTerm(sys.__stderr__)

Initially this makes no practical difference, however you can do::

    stdout.setLog(f)

and then ``print`` statements will be redirected to the file ``f``. A
subsequent ``stdout.setLog(None)`` will end the redirection.

In order for this module to work as expected, you need to import it
reasonably early so that code like::

    saved, sys.stdout = sys.stdout, myFile
    try:
        # ...
    finally:
        sys.stdout = saved

does not cause odd behaviour.

:IVariables:
    our, err
        The original ``sys.__stdout__`` and ``sys.__stderr__``, wrapped
        up as ``RichTerm.RichTerminal`` instances. These ensure you can
        always write to the terminal when necessary.

    stdout, stderr
        Replaceements for ``sys.stdout``, ``sys.stderr``. These are `StdTerm`
        instances.

"""

import os
import sys

from cleversheep3.Test.Tester import Coordinator
from cleversheep3.TTY_Utils import RichTerm


class StdTerm:
    def __init__(self, f):
        self._f = f
        self._log = None
        self._buf = ""

    def setLog(self, log):
        if self._log and log is None:
            self.write("", flush=True)
        self._log = log

    def writelines(self, lines):
        """Write a sequence of lines to the terminal/log.

        """
        self.write("".join(lines))

    def write(self, s, flush=False):
        """Write a string to the terminal.

        :Parameters:
          flush
            If set then any partial line is written to the underlying
            terminal/log.

        """
        if self._log:
            reporter = Coordinator.getServiceProvider("report_manager")
            if reporter is not None:
                self._log = reporter.debug
        if self._log:
            # Output is currently for a log file, so buffer and only write
            # when we have one or more complete lines.
            self._buf += s
            if "\n" not in self._buf:
                return
            self._buf, lines = "", self._buf.splitlines(1)
            if not flush and not lines[-1].endswith("\n"):
                lines, self._buf = lines[:-1], lines[-1]
            self._log("%s", "".join(lines))
        else:
            # Output is to an underlying terminal so simply pass on.
            self._f.write(s)

    def fileno(self):
        if not self._log:
            return self._f.fileno()

    def isatty(self):
        if not self._log:
            return self._f.isatty()

    def flush(self):
        if not self._log:
            return self._f.flush()

    def __getattr__(self, name):
        if not self._f:
            raise AttributeError(name)
        return getattr(self._f, name)


# Early on, we need to record the orginal stdout/stderr.
# Wrapped up as Rich Terminals.
try:
    _initialised
except NameError:
    out = RichTerm.RichTerminal(sys.__stdout__)
    err = RichTerm.RichTerminal(sys.__stderr__)
    if not os.environ.get("CS_NOREDIRECT", False):
        stdout = sys.stdout = StdTerm(out)
        stderr = sys.stderr = StdTerm(err)
    else:
        stdout, stderr = sys.stdout, sys.stderr
    _initialised = None


class Provider:
    def __getattr__(self, name):
        try:
            return eval(name)
        except (NameError, TypeError, SyntaxError):
            raise AttributeError(name)


tty = Provider()

Coordinator.registerProvider("cscore", "tty", tty)
