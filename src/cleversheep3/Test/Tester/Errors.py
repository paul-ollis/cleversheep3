#!/usr/bin/env python
"""The errors and exceptions used by the Tester.

Actual failure exceptions:
::

                                 Problem
                                    |
                     ,-------------------------------,
                     |                               |
                   Error                          Failure
                     |                               |
      ,-----------------------------,           ChildFailure
      |             |               |
  SetUpError  TearDownError  ExecutionError

We also have exceptions that are not failure conditions, but do bring
about the early exit from a suite or test run.

"""
__docformat__ = "restructuredtext"

import inspect
import linecache

from cleversheep3.Prog.Aspects import intelliprop
from cleversheep3.Test.Tester import options


class Oops(Exception):
    """Raise one of these to by-pass normal test failure handling.

    The Tester framework normally handles pretty much any exception.
    This exception will not be intercepted, so you can use it to help
    debugging.

    """
    pass


class FailureCondition(Exception):
    """This is used by `cleversheep3.Test.Tester` to store information about
    a test failure.

    Typically this holds information copied from a `Problem` exception, which
    was raised by one of the assertions in this module.

    :Ivar errType:
        An exception indicating the type of failure. For example `Failure`
        # Just convert args[0], see constructor/PEP-352 for why.
        or `Error`.
    :Ivar args:
        Arguments providing more information about the failure. These are used
        in the same way standard asserion args are used.
    :Ivar origExc:
        The original exception that cause the error. May be ``None``.
    :Ivar stack:
        The call stack. This is a list of tuples, each containing::

          (fileName, lineNum, funcName, context, ctxOffset)

        The first element is the innermost frame; i.e. the failure point.

    """
    def __init__(self, args, stack=None, origExc=None, message=""):
        """Constructor:"""
        self.args = args
        self.stack = stack or saveStack(inspect.stack(7))
        self.altStack = None
        self.origExc = origExc
        self.message = message

    def __str__(self):
        # Just convert args[0], see PEP-352 for why.
        return str(self.args[0])


_stackFilters = []


def addStackFilter(func):
    _stackFilters.append(func)


def _filterStack(stack):
    ret = []
    for fileName, lineNum, funcName, context, ctxOffset, meta in stack:
        for filt in _stackFilters:
            if not filt(fileName, lineNum, funcName, meta):
                break
        else:
            ret.append((fileName, lineNum, funcName, context, ctxOffset, meta))

    return ret


def saveStack(theStack, savedBy="Anon"):
    """Save details of the call stack for any test failure condition.

    By default this extracts only those stack entries that are part of the test
    code. Frames that are part of cleversheep3 of are not included. Also the
    frame and inner frames for any functions decorated by `Tester.assertion`
    are also ignored.

    If options.full_stack is set then no frames are supressed.

    :Parameters:
      theStack
        The python stack to be saved. This is as, for example, returned by
        ``inspect.stack()``.

    :Return:
        A list containing details of the stack frames. Each entry is a tuple
        of::

            (fileName, lineNum, funcName, context, ctxOffset)

    """
    linecache.clearcache()
    highWater = 0
    midWater = 0
    lowWater = 10000
    stack = []
    meta = []
    for i, data in enumerate(theStack):
        frame, fileName, lineNum, funcName, context, ctxOffset = data
        if "_cs_enter_pollmanager_" in frame.f_code.co_varnames:
            meta = list(meta)
            meta.append("_cs_pollmanager")

        stack.append((fileName, lineNum, funcName, context, ctxOffset, meta))
        try:
            if "_cs_preamble_" in frame.f_code.co_varnames:
                highWater = max(i + 1, highWater)
                continue
            if "_cs_assertion_" in frame.f_code.co_varnames:
                midWater = max(i, midWater)
                continue
            if "_cs_assertion_" in frame.f_globals:
                lowWater = min(i, lowWater)
                continue
            if "_cs_leave_pollmanager_" in frame.f_code.co_varnames:
                if "_cs_pollmanager" in meta:
                    meta = list(meta)
                    meta.remove("_cs_pollmanager")
        finally:
            del frame
    if options.full_inner_stack:
        stack = stack[highWater:]
    elif options.partial_inner_stack and midWater > 0:
        stack = stack[highWater:midWater + 2]
    elif not options.full_stack:
        if midWater > 0:
            stack = stack[highWater:midWater]
        else:
            stack = stack[highWater:lowWater]

    return _filterStack(stack)


class ExitSuite(Exception):
    """Raised when the suite should terminate."""


class ExitAll(Exception):
    """Raised when the the entire test run should terminate."""


class Problem(Exception):
    # TODO: Needs a cleanout!
    """The base class for exceptions raised by the assertions in this module.

    Any assertion in this module will raise one of these (or a derived
    exception) if the assertion fails.

    """
    def __init__(self, message, altStack=None):
        """Constructor:

        :Parameters:
          message
            The message describing the failure. This may be multi-line.
          altStack
            The actual stack to use for displaying a traceback rather that the
            calling stack at the point this exception was raised.

        """
        self.tb_list = [] # TODO: What is this for?
        self.args = (message, ) # See FailureCondition for why we do this.
        self.stack = saveStack(inspect.stack(7))
        self.altStack = altStack

    @intelliprop
    def message(self):
        """The message describing the failure."""
        return self.args[0]

    def __str__(self):
        # Just convert args[0], see constructor/PEP-352 for why.
        return str(self.args[0])


class Failure(Problem):
    """The base class for all test failures.

    A failure indicates that the test ran correctly but a failure condition
    was detected.

    """
    def __str__(self):
        return str(self.args[0])


class ChildFailure(Failure):
    """Raised when a child test of a group failed."""


class Error(Problem):
    """The base class for all test errors.

    An error indicates that the test code itself has a bug or serious problem.
    """


class SetUpError(Error): pass
class TearDownError(Error): pass
class ExecutionError(Error): pass


class DiscoveryError(Exception):
    """Raised when a module causes an exception during test discovery.

    This indicates that one of the test scripts raised an unhandled exception.

    """
    def __init__(self, exc, details):
        """Constructor:

        :Parameters:
          exc
            The exception that was originally raised. This is stored as
            args[0].
          details
            Details of the problem. This should typically be a stack
            traceback, as created by ``traceback.format_exc``. This is stored
            as args[1].

        """
        self.args = exc, details

    def __str__(self):
        if self.args[0]:
            return str(self.args[0])
        return str(self.args[1])


class SuiteNoDocstringError(DiscoveryError):
    """Raised when a suite has no docstring.

    """


class TestNoDocstringError(DiscoveryError):
    """Raised when a test has no docstring.

    """


# TODO: Delete this!
def fmtException(exc):
    #assert 0
    from cleversheep3.Prog import Files
    stack = exc.stack
    lines = []
    lines.append("%s" % exc)
    for i, x in enumerate(stack):
        try:
            path, lnum, funcName, context, lineIdx = x
        except ValueError:
            path, lnum, funcName, context, lineIdx, _ = x
        lines.append("%s: %s" % (Files.relName(path),
            funcName))
        lines.extend(_fmtStackFrame(path, lnum, funcName, context,
                lineIdx, showContext=(i == 0) or (i == len(stack) - 1)))
    return "\n".join(lines)


def _fmtStackFrame(path, lnum, funcName, context, lineIdx,
        showContext=False, ind=""):
    lines = []
    if not showContext or not context:
        if not context:
            lines.append("%s   %-4d: <no context>" % (ind, lnum,))
        else:
            l = context[lineIdx].rstrip()
            if l.strip():
                lines.append("   %-4d: %s" % (lnum, l))
            else:
                lines.append("   %-4d:" % (lnum, ))
        return lines

    for i, line in enumerate(context):
        ci = i + lnum - lineIdx
        l = line.rstrip()
        if i == lineIdx:
            lines.append("==>%-4d: %s" % (ci, l))
        else:
            if l.strip():
                lines.append("   %-4d: %s" % (ci, line.rstrip()))
            else: #pragma: unreachable
                lines.append("   %-4d:" % ci)
    return lines
