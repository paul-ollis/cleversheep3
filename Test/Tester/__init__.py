#!/usr/bin/env python
"""A general test framework for unit and similar testing.

This is my take on how a test framework should be.
"""
__docformat__ = "restructuredtext"

import os
from io import StringIO


#: The directory of the top of the test tree. This is the current working
#: directory at the time this package gets imported.
execDir = os.getcwd()

# We need the TermDisplay module to be imported early. This ensures that
# terminal output and redirection works in a consistent fashion.
from cleversheep3.Test.Tester import Tty

class _Log:
    _log = None
    @property
    def log(self):
        return Coordinator.getServiceProvider("report_manager")

    def __getattr__(self, name):
        return getattr(self.log, name)


# Now import the Coordinator. Later imports will register with it as service
# providers.
from cleversheep3.Test.Tester import Coordinator


#: The test framework log.
#:
#: This is used to write to the test log file (``test.log`` by default). This
#: is implemented using the standard ``logging`` library. Hence it has the
#: normal methods ``debug``, ``warning``, ``error``, etc.
#:
#: Note output to ``sys.stdout`` and ``sys.stderr`` is redirected to
#: ``log.debug`` and ``log.error``, during test execution. So you can
#: conveniently put, for example, ``print`` statements in your tests whenever
#: you want extra debug information logged.
log = _Log()


from cleversheep3.App import Config


#: Multiple parts of the framework can be affected by command line options
#: and configuration. So it is made globally available here.
options = Config.Options("cstest")

# Import the main package modules. Not all are directly used here, but they
# make registrations with the Coordinator.
from cleversheep3.Test.Tester import Logging
from cleversheep3.Test.Tester import TermDisplay
from cleversheep3.Test.Tester import Discovery
from cleversheep3.Test.Tester import Execution
from cleversheep3.Test.Tester import ReportMan
from cleversheep3.Test.Tester import Collection

from cleversheep3.Prog.Aspects import exportedFunction, public
from cleversheep3.TTY_Utils import Indent
from cleversheep3.Prog.Curry import Curry

# Import the supporting modules.
from cleversheep3.Test.Tester.Errors import *
from cleversheep3.Test.Tester.Assertions import *
from cleversheep3.Test.Tester.Streams import *
from cleversheep3.Test.Tester.Suites import Suite


# Pull in test environment fixup file, if present.
Collection.loadFixup()

# Names exported to support ``from Tester import *``. Note that this list is
# agumented by the ``exportedFunction`` decorator and other manipulations.
__all__ = ["Suite", "test", "log", "console", "exit_suite", "exit_all",
           "runModule", "runTree", "cs_procedural", "cs_inline", "cs_fork_all",
           "cs_enter_pdb"]
__public_functions__ = ["add_option"]

for name in locals().copy():
    if name.startswith("fail"):
        __all__.append(name)


def cs_procedural(f):
    f._cs_isProcedural = True
    return f


def cs_inline(f):
    f._cs_inline = True
    return f


def cs_fork_all(s):
    s.cs_attrs = s.cs_attrs.copy()
    s.cs_attrs.fork_all = True
    return s


def exit_suite():
    raise Errors.ExitSuite()


def exit_all():
    raise Errors.ExitAll()


def currentTestInfo():
    """Get the information about the current test.

    :Return:
        A `TestInfo` object that provides information about the curently
        executing test. This can be used during the test function itself
        and also by the `Test.Tester.Suite.setUp` and
        `Test.Tester.Suite.tearDown` methods.

    """
    try:
        return Execution.currentTestInfo()
    except AttributeError:
        return None


def currentTest():
    """Get the current test.

    :Return:
        The currently executing `Test` instance or ``None``.

    """
    manager = Coordinator.getServiceProvider("manager")
    try:
        test = manager.executingTest
    except (AttributeError, NameError):
        test = None
    return test


def setCommentary(s):
    """Set the commentary field of the status line.

    Use this to update the status line displayed during a running test. The
    text may not not immediately appear, or appear at all, if the test does not
    take a significant amount of time to run.

    :Parameters:
      s
        The text to display. This will be truncated as necessary.

    """
    manager = Coordinator.getServiceProvider("manager")
    manager.setField("commentary", s)


def setDelayLeft(seconds):
    """Set the delay field of the status line, to show time left to run.

     This is for slightly specialised use.

    :Parameters:
      seconds
        The number of seconds left.

    """
    manager = Coordinator.getServiceProvider("manager")
    manager.setDelayLeft(seconds)


# Expose certain sub-module functions and data members.
#importModuleUnderTest = exportedFunction(Collection.importModuleUnderTest)
addTestFilter = public(Manager.addTestFilter)
add_preTestFilterCallback = public(Execution.add_preTestFilterCallback)
add_postCollectionCallback = public(Execution.add_postCollectionCallback)
parse_command_line_options = public(Execution.parseCommandLineOptions)
parseCommandLineOptions = public(Execution.parseCommandLineOptions)
addModulesUnderTest = public(Discovery.addModulesUnderTest)
coverageIsEnabled = public(Execution.coverageIsEnabled)
getArgs = public(Execution.getArgs)
cs_enter_pdb = Core.enter_pdb

#add_testStateChangeCallback = Fixture.add_testStateChangeCallback

setDefaultTimeout = public(Execution.setDefaultTimeout)

#Unsupported = public(Fixture.Unsupported)

def setLogPath(path):
    """Start logging to go a specific file.

    :Parameters:
      path
        The path of the new log file. This may be ``None`` to start redirecting
        to ``sys.stderr``.

    """
    logging = Coordinator.getServiceProvider("logging").setLogPath(path)


class ServiceProxy:
    def __init__(self, service):
        self._service = service

    def __getattr__(self, name):
        obj = Coordinator.getServiceProvider(self._service)
        return getattr(obj, name)


#: Provides access to the console where the test runner shows test
#: progress.
#:
#: This can be used if you *really* need to write to the console rather
#: than the log. This can be useful for ad-hoc debugging of tests. This acts
#: as a simple ``file``, so you can simply use ``console.write``, but)
#: it is recommended that you use ``console.write(...)``.
console = ServiceProxy("status")

# TODO: This nolonger exists!
# executeTest = public(Execution.executeTest)

#: Used to add user-defined options.
#:
#: See `Execution.add_option` for details.
add_option = public(Execution.add_option)

#: A (deprecated) alias for `registerReporter`.
set_reporter = public(ReportMan.registerReporter)

registerReporter = public(ReportMan.registerReporter)
Reporter = public(ReportMan.Reporter)
currentTestHasFailed = exportedFunction(Execution.currentTestHasFailed)
add_testRunEndCallback = public(Execution.add_testRunEndCallback)
add_optionsParsedCallback = public(Execution.add_optionsParsedCallback)
add_test_exit_callback = public(Execution.add_test_exit_callback)

parseUserOptions = public(Execution.parseUserOptions)
failOn = public(Assertion.failOn)
userOptions = Execution.userParser.get_default_values()

# The test states are exposed for expert use.
NOT_RUN = public(Core.NOT_RUN)
PASS = public(Core.PASS)
FAIL = public(Core.FAIL)
ERROR = public(Core.ERROR)
BAD_SETUP = public(Core.BAD_SETUP)
#BAD_TEARDOWN = public(Core.BAD_TEARDOWN)
CHILD_FAIL = public(Core.CHILD_FAIL)
#INCOMPLETE = public(Core.INCOMPLETE)
SKIPPED = public(Core.SKIPPED)
DISABLED = public(Core.DISABLED)
BROKEN = public(Core.BROKEN)
BAD_SUITE_SETUP = public(Core.BAD_SUITE_SETUP)
#BAD_SUITE_TEARDOWN = public(Core.BAD_SUITE_TEARDOWN)
#SUITE_RUNNING = public(Core.SUITE_RUNNING)
#SUITE_CRASH = public(Core.SUITE_CRASH)


# Some old names. Should not be used for new tests.
#registerForTestStateChanged = public(Fixture.add_testStateChangeCallback)
registerOnTestEnd = public(Execution.add_testRunEndCallback)

# Preferred names start here.
addExitCallback = public(Execution.add_test_exit_callback)
addPrepareCallback = public(Execution.add_test_prepare_callback)

class TestMarker:
    """A decorator maker, used to mark test functions.

    This provides the ``test`` decorator used to mark methods (and sometimes
    functions) as tests to be run by the framework.

    """
    def __init__(self):
        self.seq = 0

    def _mark(self, f, args=(), kwargs={}):
        kwargs["_test_seq"] = self.seq
        f.cs_test_info = Core.TestInfo(*args, **kwargs)
        f.cs_is_applicable = kwargs.pop("cs_is_applicable", lambda self, t: True)
        try:
            f.cs_test_info.cs_tags["cs_modPath"] = os.path.abspath(
                f.__globals__["__file__"])
        except AttributeError:
            # The function may be a callable class instance.
            f.cs_test_info.cs_tags["cs_modPath"] = os.path.abspath(
                f.__call__.__globals__["__file__"])
        self.seq += 1
        return f

    def __call__(self, *args, **kwargs):
        if args and hasattr(args[0], "__call__"):
            return self._mark(args[0], args[1:], kwargs)
        return Curry(self._mark, args=args, kwargs=kwargs)


_test = TestMarker()
_test.__name__ = "test"

def test(*args, **kwargs):
    """Decorator used to mark methods/functions as tests."""
    return _test(*args, **kwargs)


def assertion(func):
    """Decorator used to mark a function as an assertion function.

    When you decorate a function or method with this, any stack traceback
    written following a test failure will stop *before* entering the
    decorated function.
    """
    def _call(*args, **kwargs):
        _cs_assertion_ = None
        return func(*args, **kwargs)
    return _call


def setOption(name, value):
    setattr(options, name, value)


#: The trace stream is used when we wish to temporarily redirect the output
#: from something. Then we can insert it into the log as a single record.
trace = StringIO()


# TODO: Resurrect when time permits me to do this properly.
# def setGuiStreams(app):
#     Logging.setConsole(app.frame.tty, app.frame.tty)
#     Execution.testOut = Indent.Indent(Logging.ttyout)

# ============================================================================
#                        Logging and tracing support
# ============================================================================
def getTrace():
    """Get the trace stream.

    This allows test scripts to redirect output for a short period so that
    it appears as a single record in the log file.

    TODO: Explain what this gibberish means.
    """
    return trace


# ============================================================================
#                         Tests and suites.
# ============================================================================

import inspect

# TODO: Duplicated in Aspects and ImpUtils
def _getCallerDict(level=1):
    frame = None
    try:
        frame = inspect.stack()[level + 1][0]
        return frame.f_globals
    finally:
        del frame


def _setExecDir(namespace):
    global execDir

    if execDir is None:
        execDir = os.path.dirname(os.path.abspath(namespace.get("__file__")))


def runTree():
    """Execute an entire tree of tests.

    This is the function that normally appears in an all_test.py script, as in
    :<py>:

        if __name__ == "__main__":
            collectTree()

    And similarly, an individual test script ends:<py>:

        if __name__ == "__main__":
            collectModule()

    It instructs the framework to collect all the tests within the module and
    then deliver them to the test manager.

    """
    info = Info()
    general = Coordinator.getServiceProvider("general")
    exitCode = general.bootStrap("collectTree", info)
    sys.exit(exitCode)


class Info:
    def __init__(self):
        self.namespace = namespace = _getCallerDict(2)
        self.execFile = os.path.abspath(namespace["__file__"])
        self.execDir = os.path.dirname(self.execFile)
        _setExecDir(self)

    def __getitem__(self, name):
        return self.namespace[name]

    def items(self):
        return self.namespace.items()

    def __iter__(self):
        return iter(self.namespace)

    def get(self, name, default=__getitem__):
        try:
            return self.namespace[name]
        except KeyError:
            if default is Info.__getitem__:
                raise
        return default


def runModule():
    """Execute a single module of testss.

    See `collectTree` for details.

    """
    info = Info()
    general = Coordinator.getServiceProvider("general")
    exitCode = general.bootStrap("collectModule", info)
    sys.exit(exitCode)


class cst:
    """A neat namepsace for everything to do the Cs test.

    This provides an arguably cleaner alternative to:
    :<py>:

        from cleversheep3.Test.Tester import *
        from cleversheep3.Test import Tester

    The first form is namespace poluting, but not unreasonable within actual
    test scripts. The second form is recommended for test support modules. This
    class provides another option, namely:
    :<py>:

        from cleversheep3.Test.Tester import cst

    The all CS test names can be referenced as ``cst.xyz``.
    """
    @staticmethod
    def inherit_tests(cls):
        cls.cs_attrs.inherit_tests = True
        return cls


for name in __all__:
    setattr(cst, name, eval(name))
