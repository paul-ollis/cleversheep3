#!/usr/bin/env python
"""The Tester's Logging module.

The tester has very specific logging requirements, which this module provides.
The standard logging module is used to handle the details.
"""
__docformat__ = "restructuredtext"

import os
import sys
import logging
import time

from cleversheep3.Test.Tester import Coordinator

from cleversheep3.TTY_Utils import Colours

from cleversheep3.Test.Tester import options

# TODO: What is this for?
validLevels = ("debug", "info", "warning", "error", "critical")


def disableStatus():
    status = Coordinator.getServiceProvider("status")
    status.stop()


def enableStatus():
    status = Coordinator.getServiceProvider("status")
    status.start()


class MultiLineFormatter(logging.Formatter):
    """A formatter that handles multiple lines in a clean way.

    This reformats additional lines to make it clear that they are
    part of a single log record, but still easily parsable. The ouptput
    produced looks something like::

        08:11:07.773 root INFO The widget failed.
        |                      We do not know why!
        |                      But we are trying to find out.

    The first line is formatted using the base class. The second and subsequent
    lines are prefixed by a '|' character plus spaces to align with the rest
    of the message. The indentation is determined from the first line.
    """
    def __init__(self, *args, **kwargs):
        logging.Formatter.__init__(self, *args, **kwargs)
        self.lPadChars = ""
        self.recNum = 0
        self.hooks = []

    def format(self, record):
        s = logging.Formatter.format(self, record)
        lines = s.splitlines()
        self.recNum += 1

        pad = 21
        if options.no_times:
            pad = 8
        prefix, lines[0] = lines[0][:pad], lines[0][pad:]
        while lines and not lines[0].strip():
            del lines[0]
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            lines = [""]

        newLines = [prefix + self.lPadChars + lines[0]]
        padChars = "|" + " " * (pad - 1) + self.lPadChars
        for l in lines[1:]:
            newLines.append(padChars + l)
        s = "\n".join(newLines)
        for func in self.hooks:
            func(s)
        return "\n".join(newLines)

    def formatTime(self, record, fmt):
        if options.no_times:
            return ""
        s = time.strftime("%H:%M:%S", time.localtime(record.created))
        return s + ".%03d" % record.msecs

    def addLogHook(self, func):
        self.hooks.append(func)


#: The core logger is where all output goes (eventually)
coreLog = logging.getLogger("cs_test")
coreLog.propagate = False


#: The current ``logging.Handler``, to which logged output is written.
logFile = None

def _tidy():
    if logFile:
        logFile.flush()

logFormatter = MultiLineFormatter('%(asctime)s %(levelname)-8s\n%(message)s')

def addLogHook(func):
    logFormatter.addLogHook(func)

_prevLogPath = None
_logPath = "test.log"
_logLevel = logging.DEBUG


def setLevel(level):
    global _logLevel
    _logLevel = level
    _apply_changes()


def getLogger(*args, **kwargs):
    if not logFile:
        _setLogPath(_logPath)
    return logging.getLogger(*args, **kwargs)


# TODO: Decide whether this should do something.
def flush():
    pass


def set_columns(columns):
    """Set the number of columns for logged output.

    :Parameters:
      columns
        The number of columns to use. If this is None, then the normal
        automatic detection of screen width will be used.

    """
    if columns is not None:
        try:
            sys.stdout.set_width(columns)
            sys.stderr.set_width(columns)
        except AttributeError:
            pass


# ============================================================================
#  Temp Hacking!!
# ============================================================================
import atexit

def _run_exitfuncs():
    """run any registered exit functions

    _exithandlers is traversed in reverse order so functions are executed
    last in, first out.
    """

    exc_info = None
    while atexit._exithandlers:
        func, targs, kargs = atexit._exithandlers.pop()
        try:
            func(*targs, **kargs)
        except SystemExit:
            exc_info = sys.exc_info()
        except:
            import traceback
            sys.__stderr__.write("Error in atexit._run_exitfuncs:")
            sys.__stderr__.write("\n")
            traceback.print_exc(10, sys.__stderr__)
            exc_info = sys.exc_info()

    if exc_info is not None:
        raise exc_info[0](exc_info[1], exc_info[2])


def setLogPath(path):
    global _logPath
    _logPath = path
    _apply_changes()


def _apply_changes():
    global _prevLogPath
    if not logFile:
        return
    if _logPath != _prevLogPath:
        _setLogPath(_logPath)
        _prevLogPath = _logPath
    coreLog.setLevel(_logLevel)


def start():
    if not logFile:
        _setLogPath(_logPath)
    #sys.stdout = logStream
    #sys.stderr = logStream
    _apply_changes()


def _setLogPath(path):
    """Start logging to a specific file.

    :Param path:
        The path of the file to log to. Set this to ``None`` to stop logging.

    """
    global logFile
    if logFile and isinstance(logFile, logging.FileHandler):
        logFile.close()
        coreLog.removeHandler(logFile)

    if path is None:
        logFile = logging.FileHandler("/dev/null", "w")
    else:
        if not os.path.isabs(path):
            from cleversheep3.Test import Tester
            path = os.path.join(Tester.execDir, path)
        logFile = logging.FileHandler(path, "w")

    logFile.setLevel(logging.DEBUG)
    logFile.setFormatter(logFormatter)
    coreLog.addHandler(logFile)
    coreLog.setLevel(logging.DEBUG)
    coreLog.info("Started on %s" % time.strftime("%d/%m/%Y",
            time.localtime(time.time())))

sys.exitfunc = _run_exitfuncs
