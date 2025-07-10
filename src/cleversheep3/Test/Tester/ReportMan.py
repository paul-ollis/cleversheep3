"""Managment of test reporting.

A test manager does not directly implement test reporting. Instead it
sends reporting information to one or more report managers.

TODO: This is wrong. A manager actually expects to interact with a user
      interface.

"""
__docformat__ = "restructuredtext"

from cleversheep3.Test.Tester import Coordinator


# This class is deprecated. The cability for custom reporting is much better
# now.
class Reporter:
    """Abstract base class for test reporter hook.

    """
    def enter_suite(self, has_tests, title, doc_lines):
        """Invoked when a suite starts.

        :Parameters:
          has_tests
            This is ``True`` if this suite contains tests. It is a ``False``
            value if the suite only contains other suites.
          title
            The title string of the suite, which is the leading part of the
            doc_lines.
          doc_lines
            The full set of lines for the suite's documentation string.

        """

    def leave_suite(self, has_tests, state):
        """Invoked when a suite ends.

        :Parameters:
          has_tests
            This is ``True`` if this suite contains tests. It is a ``False``
            value if the suite only contains other suites.
          state
            This is the suite state code. Conversion to a string will give a meaningful
            piece of text.

        """

    def start_test(self, number, title, doc_lines):
        """Invoked when a test is about to start.

        :Parameters:
          number
            The ordinal number of the test.
          title
            The title string of the test, which is the leading part of the
            doc_lines.
          doc_lines
            The full set of lines for the test's documentation string.
          doc_lines
            The sequence of lines for the test's documentation.

        """

    def end_test(self, number, title, doc_lines, state, error):
        """Invoked when a test has completed.

        :Parameters:
          number
            The ordinal number of the test.
          title
            The title string of the test, which is the leading part of the
            doc_lines.
          doc_lines
            The full set of lines for the test's documentation string.
          state
            This is the test state code. Conversion to a string will give a meaningful
            piece of text.
          error
            ``None`` for a passing test. Otherwise A multi-line string
            describing the error in detail.

        """

    def finish(self):
        """Invoked all the tests have completed."""

_reporter = Reporter()


def registerReporter(reporter):
    """Set the test reporter object.

    :Parameters:
      reporter
        This is typically a instance of a class derived from `Reporter`, although
        any object providing the appropriate methods is OK.

    """
    global _reporter
    _reporter = reporter


class ReporterIF:
    """The reporter interface definition.

    """
    def __init__(self, *reporters):
        pass

    def setMode(self, mode):
        pass

    def switchToTest(self, test):
        pass

    def leaveTest(self, test):
        pass

    def enterSuite(self, suite, result=None):
        pass

    def leaveSuite(self, suite):
        pass

    def prepareToRunTest(self, test, number=None, result=None):
        pass

    def announceTestStart(self, test, number=None, eol=None, result=None):
        pass

    def updateTestState(self, test):
        pass

    def putResult(self, test, itemType="None"):
        pass

    def logStage(self, test, op, msg):
        pass

    def logFailure(self, test, level="Test", ignore=()):
        pass

    def summariseSuiteResult(self, suite):
        pass

    def summariseResult(self, test):
        pass

    def write(self, s):
        pass

    def setField(self, name, s):
        pass

    def startTestRun(self):
        pass

    def stopTestRun(self):
        pass

    def critical(self, fmt, *args):
        pass

    def error(self, fmt, *args):
        pass

    def warn(self, fmt, *args):
        pass

    def info(self, fmt, *args):
        pass

    def debug(self, fmt, *args):
        pass

    # Deprecated
    def finish(self):
        pass


class ReportManager:
    """A base class for test reporting and logging.


    """
    def __init__(self, *reporters):
        #self.reporters = list(reporters)
        self.mode = "EXECUTION"
        self.api = dir(ReporterIF)
        self._oldReporter = None
        self._extraReporters = []

    @property
    def reporters(self):
        reporter = Coordinator.getServiceProvider("reporter")
        logging = Coordinator.getServiceProvider("logging")
        return [reporter, logging] + self._extraReporters

    def addReporter(self, reporter):
        self._extraReporters.append(reporter)

    def execFunc(self, func, *args, **kwargs):
        func(*args, **kwargs)

    def _log(self, name, fmt, *args):
        try:
            msg = fmt % args
        except TypeError:
            # The test writer has messed up the format string and args.
            msg = "%s, %r" % (fmt, args)
        for r in self.reporters:
            func = getattr(r, name, None)
            if hasattr(func, "__call__"):
                func("%s", msg)

    def switchToTest(self, test, parentSkip=False):
        for r in self.reporters:
            r.switchToTest(test)
        return True

    def leaveTest(self, test):
        for r in self.reporters:
            r.leaveTest(test)

    def setField(self, name, s):
        for r in self.reporters:
            r.setField(name, s)

    def debug(self, *args): return self._log("debug", *args)
    def info(self, *args): return self._log("info", *args)
    def warn(self, *args): return self._log("warn", *args)
    def error(self, *args): return self._log("error", *args)
    def critical(self, *args): return self._log("critical", *args)

    def x__getattr__(self, name):
        if name in self.api:
            return getattr(self.display, name)

    def write(self, s):
        for r in self.reporters:
            r.write(s)

    def setMode(self, mode):
        self.mode = mode
        for r in self.reporters:
            r.setMode(mode)
        return True

    def enterSuite(self, suite, result=None):
        for r in self.reporters:
            r.enterSuite(suite, result=result)

        # Old reporter support
        if self.mode in ("EXECUTION",):
            _reporter.enter_suite(suite.hasTests(), suite.summary,
                    suite.docLines)

    def leaveSuite(self, suite):
        for r in self.reporters:
            r.leaveSuite(suite)

        # Old reporter support
        if self.mode in ("EXECUTION",):
            _reporter.leave_suite(suite.hasTests(), suite.result.state)

    def summariseResult(self, test):
        for r in self.reporters:
            r.summariseResult(test)

    def summariseSuiteResult(self, suite):
        for r in self.reporters:
            r.summariseSuiteResult(suite)

    def prepareToRunTest(self, test, number=None, result=None):
        from . import Core
        assert result is None or isinstance(result, Core.StepRecord)
        for r in self.reporters:
            r.announceTestStart(test, number=number, result=result)

        # Old reporter support
        # TODO: Fix
        if self.mode in ("EXECUTION",):
            _reporter.start_test(number, test.summary, test.docLines)

    def updateTestState(self, test):
        for r in self.reporters:
            try:
                r.updateTestState(test)
            except AttributeError:
                pass

    def putResult(self, test, itemType="None"):
        for r in self.reporters:
            r.putResult(test, itemType=itemType)

        # Old reporter support
        # TODO: Fix
        stepRecord = test.getStepRecord("run")
        errorText = None
        if stepRecord is not None:
            if hasattr(stepRecord, "exc"):
                if stepRecord.exc is not None:
                    errorText = self._fmtFailException(stepRecord.exc)

        _reporter.end_test(test.number, test.summary, test.docLines,
            test.result.state, errorText)

    def startTestRun(self):
        for r in self.reporters:
            r.startTestRun()

    def stopTestRun(self):
        for r in self.reporters:
            r.stopTestRun()

    # Old reporter support
    def finish(self):
        if self.mode in ("EXECUTION",):
            _reporter.finish()

    def logFailure(self, test, level="Test", ignore=()):
        # TODO: Too much of a cut-and-paste from cleversheep3.
        #self._logTeardown(test, "tearDown", ignore, level)
        #self._logTeardown(test, "suiteTearDown", ignore, level)
        self._logTeardown(test, "tearDown", "Tear down failed")
        self._logTeardown(test, "suiteTearDown", "Suite tear down failed")
        self._logStage(test, "suiteSetUp",
            "%s suite set up phase failed - test(s) abandoned\n" % level)
        self._logStage(test, "setUp", "Test setUp failed\n")
        self._logStage(test, "run", "Test failed\n")
        self._logStage(test, "postCheck", "Test failed\n")

    def _logStage(self, test, op, msg):
        # TODO: Too much of a cut-and-paste from cleversheep3.
        phaseRecord = test.getStepRecord(op)
        if phaseRecord is None or not phaseRecord.hasFailed:
            return
        if phaseRecord.reported:
            return
        for r in self.reporters:
            r.logStage(test, op, msg)
        phaseRecord.reported = True

    def _logTeardown(self, test, op, msg):
        phaseRecord = test.getStepRecord(op)
        if phaseRecord is None or not phaseRecord.hasFailed:
            return
        if phaseRecord.reported:
            return
        for r in self.reporters:
            r.logStage(test, op, msg)
        phaseRecord.reported = True

    # Old reporter support
    def _fmtFailException(self, exc):
        from cleversheep3.Prog import Files
        stack = exc.stack
        lines = []
        lines.append("%s" % exc)
        for i, x in enumerate(stack):
            try:
                path, lnum, funcName, context, lineIdx, meta = x
            except ValueError:
                path, lnum, funcName, context, lineIdx = x
                meta = ()
            lines.append("%s: %s" % (Files.relName(path),
                funcName))
            lines.extend(self._fmtStackFrame(path, lnum, funcName, context,
                    lineIdx, showContext=(i == 0) or (i == len(stack) - 1)))
        return "\n".join(lines)

    def _fmtStackFrame(self, path, lnum, funcName, context, lineIdx,
            showContext=False):
        self.ind = ""
        lines = []
        if not showContext or not context:
            if not context:
                lines.append("%s   %-4d: <no context>" % (self.ind, lnum,))
            else:
                l = context[lineIdx].rstrip()
                if l.strip():
                    lines.append("   %-4d: %s" % (lnum, l))
                else:
                    lines.append("   %-4d:" % (lnum, ))
            return []

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


Coordinator.registerProvider("cscore", ("report_manager",), ReportManager())
