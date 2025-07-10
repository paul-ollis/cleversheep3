"""Those things that are core to tests.

This module provides the most fundamental test entities, which include such
things as:

- Tests
- Suites
- Test states

"""
from __future__ import print_function
__docformat__ = "restructuredtext"

import os
import textwrap
import time
import weakref
import inspect

from cleversheep3.Prog.Aspects import intelliprop
from cleversheep3.Prog.Enum import Enum

from cleversheep3.Test.Tester import Context
from cleversheep3.Test.Tester import Coordinator
from cleversheep3.Test.Tester import options

State = Enum("State")

# Static test states.
NOT_RUN = State("NOT_RUN")
PASS = State("PASS")
FAIL = State("FAIL")
SKIPPED = State("SKIPPED")
BROKEN = State("BROKEN")
DISABLED = State("DISABLED")
BUG = State("BUG")
BUG_PASS = State("BUG_PASS")
TODO = State("TODO")

# Dynamic test states.
SET_UP = State("SET_UP")
TEAR_DOWN = State("TEAR_DOWN")
RUNNING = State("RUNNING")
FINISHED = State("FINISHED")    # TODO: To remove!

# Suite specific states.
CHILD_FAIL = State("CHILD_FAIL")
PART_RUN = State("PART_RUN")

# Reason codes. Note that this list is those codes that are only used as
# reasons, some states are also used as reason code.
NONE = State("NONE")
ERROR = State("ERROR")
BAD_SETUP = State("BAD_SETUP")
BAD_SUITE_SETUP = State("BAD_SUITE_SETUP")
EXIT_SUITE = State("EXIT_SUITE")
EXIT_ALL = State("EXIT_ALL")
USER_STOPPED = State("USER_STOPPED")

def dedentLines(lines):
     return textwrap.dedent("\n".join(lines)).splitlines()


class TestInfo:
    """Information about a test function.

    This class supports the ``@test(...)`` decorator that is used by
    cleversheep3 to mark test functions. All such marked functions are given
    an attribute called ``cs_test_info``, which is in an instance of this
    class.

    This is most commonly used in test filter functions, as registered by
    `addTestFilter`. When tests are marked using the ``@test`` decorator
    they can be given one or more tags and/or flags.

    Currently this is little more than a struct, except that it provides
    a `__getattr__` that returns ``None`` by default.

    """
    def __init__(self, *args, **kwargs):
        """Constructor:

        :Parameters:
          args
            Non-keyword arguments are interpreted by the test framework.
            Each argument is a string. The supported forms are:

              plat:<platformType>
                The test will only be executed if ``<platformType>`` matches
                `Sys.Platform.platformType`. For example: ``"plat:windows"``.

          kwargs
            Any keyword arguments are simply stored as attributes. So, if
            you decorate a ``test_x`` with ``test(xyz=123)`` then
            ``test_x.cs_test_info.xyz`` will be ``123``.
        """
        self.reserved_cs_flags = {}
        self.cs_flags = {}
        self.cs_tags = {}
        for arg in args:
            if ":" in arg:
                name, value = arg.split(":", 1)
                self.cs_flags[name] = value
            else:
                self.cs_flags[arg] = True

        for name in kwargs:
            if name.startswith("cs_"):
                self.reserved_cs_flags[name[3:]] = kwargs[name]
            else:
                self.cs_tags[name] = kwargs[name]
        self.reserved_cs_flags['defined_in_base'] = None

    def __getattr__(self, name):
        """Attribute access:

        Provides read access to test method tags. For example, if you mark a
        test:<py>:

            @test(abc="Hello")

        Then, if ``info`` is the test's `TestInfo` object, ``info.abc`` will
        be ``"Hello"``. If the test does not have ``abc`` set then the result
        is ``None``.
        """
        if name in self.__dict__:
            return self.__dict__.get(name)
        return self.cs_tags.get(name, None)


class Result:
    """Full result details for a test."""
    def __init__(self, state, reason):
        self.state, self.reason = state, reason

    @property
    def reportCode(self):
        if self.reason is NONE:
            return self.state
        return self.reason


class StepRecord:
    """A single record used to store informmation about the success or
    otherwise of a test phase.

    A test phase is one of:

    - A suite set-up/tear-down.
    - A test set-up/tear-down.
    - The execution of the test-method itself.

    :Ivariables:
      result
        TODO
      reason
        TODO

    """
    def __init__(self, result=NOT_RUN, reason=NONE, details=None):
        self.result, self.reason = result, reason
        self.exc = None
        self.reported = False

    def setResult(self, state, reason=NONE, details=None):
        self._state, self._reason = state, reason
        self._details = details

    # TODO: Just transitional.
    @property
    def state(self):
        return self.result

    @property
    def hasFailed(self):
        return self.result in (FAIL, BAD_SETUP)

    def __str__(self):
        return "StepRecord: %s/%s" % (self.state, self.reason)


class StepRecordList:
    def __init__(self):
        self.entries = []


class RunRecord:
    """A set of records containing all information about a single test's run.

    This stores multiple `StepRecord` instances. The records are stored in a
    dictionary keyed by the following names:

    setUp, tearDown, prevTearDown, rn
        Each maps to a single `StepRecord`.

    suiteSetUp, suiteTearDown, prevSuiteTearDown
        Each mapping to a list of `StepRecord` instances, in execution order.

    """
    _simpleNames = """setUp tearDown prevTearDown run postCheck""".split()
    _listNames = """suiteSetUp suiteTearDown prevSuiteTearDown""".split()
    _recordNames = _simpleNames + _listNames
    _runTime = None

    def __init__(self):
        #assert RunRecord._runTime is not None
        self.runTime = RunRecord._runTime
        self.invalid = False
        self._records = {}
        self.extraInfo = {}

    def __setstate__(self, state):
        self.invalid = False
        self.__dict__.update(state)

    @classmethod
    def startNewRun(cls):
        cls._runTime = time.time()

    @classmethod
    def finishRun(cls):
        cls._runTime = None

    def addStepRecord(self, name):
        """Add a new phase record to this run record.

        Adds a new `StepRecord` for a test phase, which must be one of those
        defined for a `RunRecord`.

        :Parameters:
          name
            The name for the record. It must be the name of a defined test
            phase.

        :Return:
            The newly added `StepRecord` instance. This will always be a newly
            created instance.

        """
        assert name in RunRecord._recordNames
        record = StepRecord()
        if name in RunRecord._simpleNames:
            assert name not in self._records
            self._records[name] = record
        else:
            if name not in self._records:
                self._records[name] = StepRecordList()
            self._records[name].entries.append(record)
        return record

    def getResult(self, name):
        pass

    @property
    def result(self):
        # Is set-up failed then we report that as bad setup.
        try:
            rec = self._records["setUp"]
        except KeyError:
            pass
        else:
            if rec.state is not PASS:
                result = Result(BAD_SETUP, BAD_SETUP)
                return result

        # See if the test was actually executed.
        try:
            rec = self._records["run"]
        except KeyError:
            pass
        else:
            result = Result(rec.state, rec.reason)
            return result

        # Test was not run, so we need to find out why. A suite set-up
        # failure means we consider the test not-run.
        for rec in self._records.get("suiteSetUp", []):
            if rec.state is not PASS:
                return Result(NOT_RUN, BAD_SUITE_SETUP)

        try:
            rec = self._records["setUp"]
        except KeyError:
            pass
        else:
            if rec.state is not PASS:
                return Result(NOT_RUN, BAD_SETUP)

        return Result(NOT_RUN, NONE)

    @property
    def state(self):
        # If set-up failed then we report that as bad setup.
        try:
            rec = self._records["setUp"]
        except KeyError:
            pass
        else:
            if rec.state is NOT_RUN:
                return NOT_RUN
            if rec.state not in (PASS, BUG, BUG_PASS):
                return BAD_SETUP

        # If the test has a 'run' entry then that defines the state.
        try:
            rec = self._records["run"]
            #if rec.state is NOT_RUN:
            #    return RUNNING
            return rec.state
        except KeyError:
            pass

        # Otherwise the state is not-run.
        return NOT_RUN

    @property
    def isRunnable(self):
        for name in ("suiteTearDown", "tearDown", "suiteSetUp", "setUp"):
            try:
                if self._records[name].state not in (PASS, SKIPPED, NOT_RUN):
                    return True
            except KeyError:
                pass

        return False

    @property
    def hasRunProblem(self):
        for name in ("tearDown", "suiteTearDown", "suiteSetUp", "setUp",
                "run", "postCheck"):
            try:
                record = self._records[name]
            except KeyError:
                continue

            if name in ("tearDown", "setUp", "run", "postCheck"):
                if record.state not in (PASS, SKIPPED, NOT_RUN,
                        TODO, BUG, BUG_PASS):
                    return True
            else:
                for rec in record.entries:
                    if rec.state not in (PASS, SKIPPED, NOT_RUN,
                            TODO, BUG, BUG_PASS):
                        return True

        return False

    @property
    def hasFailed(self):
        for name in ("suiteSetUp", "setUp", "run"):
            try:
                record = self._records[name]
            except KeyError:
                continue
            if name in ("setUp", "run"):
                if record.state not in (PASS, SKIPPED, NOT_RUN, TODO, BUG,
                        BUG_PASS):
                    return True
            else:
                for rec in record.entries:
                    if rec.state not in (PASS, SKIPPED, NOT_RUN,
                        TODO, BUG, BUG_PASS):
                        return True

        return False

    @property
    def phaseRecord(self):
        """Get the most recent phaseRecord.

        This is used to get the most pertinent record for this test; i.e. the
        one that provides the most useful result for the test.

        TODO: This is not yet well defined.

        """
        for name in ("tearDown", "run", "setUp"):
            try:
                return name, self._records[name]
            except KeyError:
                pass
        #return None, None
        seq = self._records.get("suiteSetUp", None)
        if seq is None:
            return None, None
        for ent in seq.entries:
            if ent.hasFailed:
                return "suiteSetUp", ent
        return "suiteSetUp", seq.entries[0]

    def getStepRecord(self, phase):
        """Get the record details for a test run phase."""
        ent = self._records.get(phase, None)
        if hasattr(ent, "append"): # Yurk!
            seq = ent
            for ent in seq:
                if ent.hasFailed:
                    return ent
            return seq.entries[0]
        if hasattr(ent, "entries"): # Double yurk!
            seq = ent.entries
            for ent in seq:
                if ent.hasFailed:
                    return ent
            if seq:
                return seq[0]
            return
        return ent


class TestItem:
    """Base class for `Test` and `Suite` classes.

    """
    def __init__(self, item, uid, parentUid, context, namespace=None):
        """Constructor:

        :Parameters:
          item
            The concrete test item. For a test function/method this is the
            function/method itself. For a `ClassSuite` this is the instance and
            for a `ModuleSuite` this is the the module instance.

          uid
            The unique ID for this item, which is a tuple of strings.

          parentUid
            The unique ID of the parent item or ``None``. Only the root `Suite`
            of a test tree has a parent of ``None``.

          namespace
            A dictionary that provides the containing namespace for the test
            item.

        """
        self.item = item
        self.uid = uid
        self.context = context
        self.parentUid = parentUid
        self.namespace = self._getNamespace(namespace)
        self._collection = None
        self._running = False
        self._marks = {}
        self.extraInfo = {}

    def setMark(self, mark):
        self._marks[mark] = None

    def clearMark(self, mark):
        if mark in self._marks:
            del self._marks[mark]

    def isMarked(self, mark):
        return mark in self._marks

    def setCollection(self, collection):
        self._collection = weakref.proxy(collection)

    # TODO: To remove.
    def setPhase(self, phase):
        self._phase = phase

    @intelliprop
    def state(self):
        """The current state of the test.

        """
        result = self.getResult()
        return result.state

    def setState(self, state):
        if state is PASS:
            pass

    @intelliprop
    def level(self):
        """This item's level in the test tree.

        This is the number of ancestors this item has. If zero then this is
        the 'root' item.

        """
        return len(self.ancestors)

    @intelliprop
    def parent(self):
        """The parent of this item, which may be ``None``.

        If this is ``None`` then this item is the root of a (possibly nested)
        suite of tests.

        """
        return self._collection.parent(self)

    @intelliprop
    def ancestors(self):
        """A list of all ancestors for this item.

        Each entry is a UID. The first entry is the oldest ancesctor and the
        last entry is the immediate parent's UID.

        """
        return self._collection.getAncestors(self)

    def hasFailingAncestor(self):
        """Check if any ancestor is considered to have failed.

        An ancestor suite has failed if, for example, its ``suiteSetup``
        failed.

        :Return:
            ``True`` if any ancestors has failed.

        """
        parent = self.parent
        if parent is None:
            return
        # TODO: Temporarily disabled.
        return
        return parent.hasFailed or parent.hasFailingAncestor()

    def _getNamespace(self, namespace=None):
        return namespace or dict([(n, getattr(self.item, n))
            for n in dir(self.item)])

    @intelliprop
    def rawDoc(self):
        """The raw docstring, no cleaning up performed at all."""
        return self.namespace["__doc__"]

    @intelliprop
    def docLines(self):
        """The docstring as lines.

        This is cleaned up to remove leading and trailing blank lines from
        the summary and details.

        :Return:
            A sequence of (non-nul terminated) lines for the docstring. The
            summary (if present) is separated from the details by a single
            empty line.

        """
        summary, description = self._getDocParts()
        if description:
            return summary + [""] + description
        return summary

    @intelliprop
    def doc(self):
        """The docstring after being cleaned up.

        :Return:
            The cleaned up docstrinc as a multiline string. Leading and
            trailing blank lines are removed and the summary is separated from
            any details by a single blakn line. Common leading whitspace is
            also removed from each line.

        """
        return "\n".join(self.docLines)

    def _getDocParts(self):
        # Lose leading blank lines.
        lines = self.rawDoc.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)

        # All lines up to next blank line are the summary.
        summary = []
        while lines and lines[0].strip():
            summary.append(lines.pop(0))

        # Strip leading and trailing blank lines from the remaining details.
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

        # Dedent the summary and details before returning them.
        summary = summary[:1] + dedentLines(summary[1:])
        details = dedentLines(lines)
        return summary, details

    @property
    def summary(self):
        summary, description = self._getDocParts()
        return " ".join(summary)

    @property
    def details(self):
        summary, description = self._getDocParts()
        return description

    @property
    def sourcesUnderTest(self):
        sources = []
        for p in self.namespace.get("sources_under_test", []):
            if not os.path.isabs(p):
                p = os.path.abspath(os.path.join(self.dirname, p))
            sources.append(p)
        p = self.parent
        if p is not None:
            sources.extend(p.sourcesUnderTest)
        return sources

    @property
    def klass(self):
        return None

    @property
    def path(self):
        p = self.namespace.get("__file__", None)
        if p is None:
            return self.parent.path
        if p.endswith(".pyc"):
            p = p[:-1]
        return p

    @property
    def dirname(self):
        f = self.path
        if f:
            return os.path.dirname(f)

    @property
    def isBug(self):
        return False


class Test(TestItem):
    typeName = "Test"
    isSuite = False
    amNull = False

    def __init__(self, *args, **kwargs):
        super(Test, self).__init__(*args, **kwargs)
        self._runHistory = []
        self.stopAll = False
        if self.func:
            self.func.cs_test_info.test = weakref.proxy(self)

    def getHistory(self):
        return self._runHistory

    def dumpHist(self):
        return self._runHistory[-1].dump()

    def startNewRun(self):
        rec = RunRecord()
        self._runHistory.append(rec)

    def abortRun(self):
        self._runHistory.pop()

    def addStepRecord(self, name):
        runRecord = self._runHistory[-1]
        return runRecord.addStepRecord(name)

    @property
    def postCheck(self):
        return self.parent.postCheck

    @intelliprop
    def hasFailed(self):
        """Check if this test has properly failed.

        :Return:
            ``True`` if the test has failed to run for any reason.

        """
        record = self.getRunRecord().getRecord("run")
        return record.state is FAIL

    @property
    def klass(self):
        return self.parent.klass

    @property
    def funcName(self):
        return self.item.__name__

    @property
    def func(self):
        return self.item

    @property
    def info(self):
        return self.func.cs_test_info

    @property
    def isBroken(self):
        if not hasattr(self, "info"):
            raise PropertyError("%r has no attribute %r" % (
                self.__class__.__name__, "info"))
        flag = self.info.reserved_cs_flags.get("broken", None)
        if flag is None:
            flag = self.info.cs_flags.get("broken", False) # deprecated
        return flag

    @property
    def isTodo(self):
        if not hasattr(self, "info"):
            raise PropertyError("%r has no attribute %r" % (
                self.__class__.__name__, "info"))
        return self.info.cs_flags.get("todo", False)

    @property
    def isBug(self):
        if not hasattr(self, "info"):
            raise PropertyError("%r has no attribute %r" % (
                self.__class__.__name__, "info"))
        flag = self.info.reserved_cs_flags.get("bug", None)
        if flag is None:
            flag = self.info.cs_flags.get("bug", False) # deprecated
        return flag

    @property
    def shouldFork(self):
        if not hasattr(self, "info"):
            raise PropertyError("%r has no attribute %r" % (
                self.__class__.__name__, "info"))
        if self.info.reserved_cs_flags.get("fork", False):
            return True
        parent = self.parent
        try:
            return parent.suite.cs_attrs.fork_all
        except AttributeError:
            return False

    @property
    def testID(self):
        return self.info.cs_tags.get("testID", None)

    @property
    def title(self):
        return self.info.cs_flags.get("title", None)

    @property
    def isRunnable(self):
        #if self.isBroken and not options.no_disabled:
        #    return False
        if self.parent.exited:
            return False
        return True

    @property
    def state(self):
        rec = self.runRecord
        if rec:
            return rec.state
        return NOT_RUN

    @property
    def result(self):
        rec = self.runRecord
        if rec:
            return rec.result
        return NOT_RUN

    @property
    def hasRunProblem(self):
        rec = self.runRecord
        if rec:
            return rec.hasRunProblem
        return False

    @property
    def hasFailed(self):
        rec = self.runRecord
        if rec:
            return rec.hasFailed
        return False

    def addRunRecord(self, record):
        self._runHistory.append(record)
        if len(self._runHistory) > 5:
            self._runHistory[:] = self._runHistory[-5:]

    @property
    def runRecord(self):
        """The XXX TODO"""
        if self._runHistory:
            for rec in reversed(self._runHistory):
                if not rec.invalid:
                    return rec

    # TODO: Should now be StepRecord.
    @property
    def phaseRecord(self):
        """The XXX TODO"""
        if not self._runHistory:
            return None, None
        return self._runHistory[-1].phaseRecord

    def getStepRecord(self, phase):
        return self._runHistory[-1].getStepRecord(phase)

    def getTestProcedure(self):
        return self._collection.spec.getThing(self)


class NullTest(Test):
    amNull = True

    def __init__(self):
        context = Context.getContext(dirPath=os.getcwd())
        super(NullTest, self).__init__(None, None, None, context)
        self.number = 0
        self.startNewRun()

    def startNewRun(self):
        rec = RunRecord()
        self._runHistory.append(rec)

    def abortRun(self):
        self._runHistory.pop()

    @property
    def isBug(self):
        return False

    def __bool__(self):
        return False


class Suite(TestItem):
    typeName = "Suite"
    isSuite = True

    def __init__(self, *args, **kwargs):
        self.myDir = kwargs.pop("myDir")
        super(Suite, self).__init__(*args, **kwargs)
        self.exited = False
        self.number = 0
        self.skipTests = False
        self.entered = False

    def reset(self):
        self.entered = False
        self.skipTests = False

    @intelliprop
    def children(self):
        """All the direct children of this item."""
        tests = [t for t in self._collection if t.parent is self]
        suites = [t for t in self._collection.suites if t.parent is self]
        return suites + tests

    @intelliprop
    def tests(self):
        """All the direct test children of this item."""
        return [t for t in self._collection if t.parent is self]

    @property
    def suite(self):
        return self.item

    @property
    def runAfter(self):
        """The _run_after for this source."""
        return self.namespace.get("_run_after", [])

    @property
    def postCheck(self):
        return self.namespace.get("postCheck", lambda: None)

    @property
    def setUp(self):
        return self.namespace.get("setUp", lambda: None)

    @property
    def postSetUp(self):
        return self.namespace.get("postSetUp", lambda: None)

    @property
    def tearDown(self):
        return self.namespace.get("tearDown", lambda: None)

    @property
    def suiteSetUp(self):
        return self.namespace.get("suiteSetUp", lambda: None)

    @property
    def suiteTearDown(self):
        return self.namespace.get("suiteTearDown", lambda: None)

    def getResult(self, name=None):
        runCount = 0
        childStates = {}
        result = Result(PASS, NONE)
        if not self.children:
            result.state = NOT_RUN
            return result

        for c in self.children:
            state = c.state
            runCount += state is not NOT_RUN
            childStates[state] = None

        if FAIL in childStates:
            result.state = CHILD_FAIL
        elif CHILD_FAIL in childStates:
            result.state = CHILD_FAIL
        elif BAD_SETUP in childStates:
            result.state = CHILD_FAIL
        elif PART_RUN in childStates:
            result.state = PART_RUN
        elif NOT_RUN in childStates:
            if runCount:
                result.state = PART_RUN
            else:
                result.state = NOT_RUN

        return result

    @property
    def result(self):
        return self.getResult()

    @property
    def state(self):
        result = self.getResult()
        return result.reportCode

    def hasTests(self):
        # Deprecated. Only used for old reporter support.
        for t in self._collection:
            if t.parent is self:
                return True


class ModuleSuite(Suite):
    pass


class ClassSuite(Suite):
    @property
    def klass(self):
        return self.item.__class__.__name__


def enter_pdb():
    """Enter the python debugger."""
    import sys, pdb
    sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
    pdb.set_trace()
