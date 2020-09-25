"""A default test manager module.

The main thing this does is provide a `Manager` class, which is used as the
default (currently only) manager for the framework.

"""
__docformat__ = "restructuredtext"

import functools
import inspect
import linecache
import os
import random
import time
import traceback
import weakref

from multiprocessing import Process, Queue
from queue import Empty

from cleversheep3.Prog import Aspects
from cleversheep3.Prog import Files
from cleversheep3.Test.Tester import Core
from cleversheep3.Test.Tester import Context
from cleversheep3.Test.Tester import Collection
from cleversheep3.Test.Tester import Assertions
from cleversheep3.Test.Tester import WatchDog
from cleversheep3.Test.Tester import Errors
from cleversheep3.Test.Tester import Suites
from cleversheep3.Test.Tester import options
from cleversheep3.Test.Tester import SubProcess
from cleversheep3.Test.Tester import Coordinator
from cleversheep3.Test.Tester import Journal
from cleversheep3.Test.Tester import sphinx


# A list of functions supplied by the user to select which tests to run.
_testFilterFunctions = []


_infoPath = os.path.abspath(".csdata/info")


# Exit code values. These can be bitwise combined to indicate more than one
# problem.
TEST_FAIL = 0x01
SETUP_FAIL = 0x02
TEARDOWN_FAIL = 0x04


class Struct:
    pass


def loadInfo():
    global info
    info = {}
    try:
        f = open(_infoPath)
    except IOError:
        return info
    s = f.read()
    try:
        info = eval(s)
    except:
        pass
    return info


def saveInfo():
    Files.mkParentDir(_infoPath)
    try:
        f = open(_infoPath, "w")
    except IOError:
        return
    f.write(repr(info))


def storeTimeInfo(test, elapsed):
    timeInfo = info.setdefault("timeData", {})
    uid = test.uid
    if uid not in timeInfo:
        timeInfo[uid] = (None, [])
    avg, values = timeInfo[uid]
    values.append(elapsed)
    while len(values) > 10:
        values.pop(0)
    avg = sum(values) / len(values)
    timeInfo[uid] = (avg, values)


def getExecTimes(test):
    timeInfo = info.setdefault("timeData", {})
    uid = test.uid
    if uid not in timeInfo:
        return None, []
    avg, values = timeInfo[uid]
    return avg, values


def addTestFilter(func):
    """Used to add a function that filters (out) tests.

    This is generally used along with test tags/annotations to allow you to
    write test scripts that modify the set of tests selected to be run
    (summarised, etc.) according to the environment in which the test scripts
    are being run.

    When the test framework **performs** its test discovery phase, it will invoke
    all regstered filter functions for each test function/method as
    :<py>:

        func(testFunc, testInfo)

    Where the ``testInfo`` is the `TestInfo` that will be attached to the
    ``testFunc`` as the ``cs_test_info`` attribute.

    The function *must* return a ``True`` value if the test function/method
    should be included in its test suite. In order to do this, the filter
    function will typically examine the ``testInfo``. This instance allows
    details of the tags and flags that have been set for the ``testFunc`` - see
    `TestInfo` for more details.

    Note that for each test, all registered filter functions must return a
    ``True`` value in order for the test to be selected.

    :Param func:
        The function to be invoked to select whether a particular
        function//method should be selected as a test function/method.

    """
    if func not in _testFilterFunctions:
        _testFilterFunctions.append(func)


class _DefaultSelector:
    def matches(self, test):
        for func in _testFilterFunctions:
            if not func(test, test.info):
                return
        return True

    def testNumbers(self):
        return []


class Manager:
    """A test manager.

    This class defines the basic abstraction of a test manager. Various tester
    functions need access to a manager, for example the `collectModule`
    function.

    TODO: Make the above correct.

    Within a GUI, the manager would be something akin to the 'controller'. And
    the ``ui`` passed to the constructor is something akin to the 'view'.

    """
    def __init__(self):
        self._tests = None
        self.selectors = [_DefaultSelector()]
        self.executingTest = None
        self.context = None
        self.mustStop = False
        self.exitCode = 0

    def loadJournal(self):
        self.journal = Journal.getJournal()

    def _contextMatches(self, test):
        if not self.context:
            return True
        return self.context.testFilter(test)

    def getSelectionByNumber(self):
        tests = []
        for sel in self.selectors:
            for n in sel.testNumbers():
                for test in self._collection:
                    if test.number == n:
                        tests.append(test)
        return tests

    def selectedTests(self):
        def rnd():
            src = random.Random()
            seed = options.random
            if seed < 0:
                seed = int(time.time())
            src.seed(seed)
            reportMan = Coordinator.getServiceProvider("report_manager")
            reportMan.info("Test order randomised using seed %d", seed)
            tests = list(self._collection)
            while tests:
                t = src.choice(tests)
                yield t
                tests.remove(t)

        for suite in self._collection.suites:
            suite.skipTests = False

        group = [Core.NullTest()]
        if options.random == 0:
            if options.unsorted:
                collection = self.getSelectionByNumber()
            else:
                collection = self._collection
        else:
            collection = rnd()

        for test in collection:
            if options.skip_passed and test.state is Core.PASS:
                continue
            if not self._contextMatches(test):
                continue
            for selector in self.selectors:
                ok = True
                if not selector.matches(test):
                    break
            else:
                group.append(test)
                if len(group) == 3:
                    yield tuple(group)
                    group.pop(0)

        if len(group) != 1:
            # make sure the last test is processed.
            group.append(Core.NullTest())
            yield tuple(group)

    def setField(self, name, s):
        reportMan = Coordinator.getServiceProvider("report_manager")
        reportMan.setField(name, s)

    def setDelayLeft(self, s):
        reportMan = Coordinator.getServiceProvider("report_manager")
        reportMan.setField("delay", "T:%5.1f" % s)

    def _processTest(self, reportMan, env, prevTest, test, nextTest):
        status = Coordinator.getServiceProvider("status")
        linecache.clearcache()
        status.setField("commentary", "")
        self.executingTest = test
        if self.mustStop:
            result = env.skipTest(prevTest, test, nextTest)
        else:
            result = env.executeTest(prevTest, test, nextTest)
            if env.exitAll:
                self.mustStop = True
        reportMan.execFunc(self.journal.record, test)
        self.executingTest = None
        if test.hasFailed:
            if test.stopAll or (not options.keep_going
                    and not test.state is Core.EXIT_SUITE):
                for suite in self._collection.suites:
                    suite.skipTests = True
            return False
        reportMan.leaveTest(test)
        return True

    def _execute(self, reportMan, env):
        """Execute all selected tests in order.

        TODO: This is not necessarily execution. A **much** better name is
        required.

        :Parameters:
          reportMan
            The testr reporting manager instance.
          env
            The test execution environment.

        """
        #if options.patch_subprocess:
        #    SubProcess.egregiouslyMonkeyPatch()
        loadInfo()
        reportMan.setMode("EXECUTION")

        allPassed = True
        status = Coordinator.getServiceProvider("status")
        for prevTest, test, nextTest in self.selectedTests():
            Suites.control().poll.clearCallbacks()
            if options.max_exec_time > 0:
                avg = getExecTime(test)
                if avg is not None and avg > options.max_exec_time:
                    continue
            if not self._processTest(reportMan, env, prevTest, test, nextTest):
                allPassed = False
        reportMan.finish()
        saveInfo()
        if not allPassed:
            self.exitCode |= TEST_FAIL

    def _summariseAll(self, reportMan, env):
        if not reportMan.setMode("RUN-SUMMARY"):
            return
        env = TestResultSummariser(self._collection)
        env.start("\nSummary of the entire run\n")
        for prevTest, test, nextTest in self.selectedTests():
            env.executeTest(prevTest, test, nextTest)
        #env.executeTest(nullTest)

    def _summariseFailures(self, reportMan, env):
        if self._collection.hasFailures():
            reportMan = Coordinator.getServiceProvider("report_manager")
            if not reportMan.setMode("FAIL-SUMMARY"):
                return
            self.context = env = TestFailureSummariser(self._collection)
            started = False
            for prevTest, test, nextTest in self.selectedTests():
                if not started:
                    env.start("\nSummary of the failures\n")
                    started = True
                env.executeTest(prevTest, test, nextTest)
            #env.executeTest(nullTest)

    def run(self, wibble=""):
        """Run a set of (selected) tests.

        This is invoked to run a set of tests.

        """
        Core.RunRecord.startNewRun()
        status = Coordinator.getServiceProvider("status")
        status.setField("commentary", "")
        reportMan = Coordinator.getServiceProvider("report_manager")
        env = TestExecEnvironment(self._collection)
        logging = Coordinator.getServiceProvider("logging")
        tty = Coordinator.getServiceProvider("tty")
        tty.stdout.setLog(reportMan.debug)
        tty.stderr.setLog(reportMan.error)

        reportMan.startTestRun()
        status.start()
        try:
            self._execute(reportMan, env)
            self._collection.resetSuites()
            self._summariseAll(reportMan, env)
            self._collection.resetSuites()
            self._summariseFailures(reportMan, env)
            Core.RunRecord.finishRun()

        finally:
            #if options.patch_subprocess:
            #    SubProcess.unPatch()
            self.context = None
            self.mustStop = False
            reportMan.stopTestRun()
            # TODO: This code breaks something.
            if 0:
                tty.stdout.setLog(None)
                tty.stderr.setLog(None)

        # TODO: Is this a sensible thing to return?
        self.exitCode |= env.exitCode
        return self.exitCode

    def addSelector(self, selector):
        self.selectors.append(selector)

    def setSelector(self, selector):
        self.selectors = [selector]

    def setCollection(self, collection):
        """Set the test collection.

        :Parameters:
          collection
            The collection of tests.

        """
        self._collection = collection
        #self.journal.fix(self._collection)
        self.loadJournal()
        self.journal.load(self._collection)

    def summarise(self):
        reportMan = Coordinator.getServiceProvider("report_manager")
        env = _TestSummariser(self._collection)
        nullTest = Core.NullTest()
        for prevTest, test, nextTest in self.selectedTests():
            env.executeTest(prevTest, test, nextTest)

    def null_action(self):
        reportMan = Coordinator.getServiceProvider("report_manager")
        env = _TestNullAction(self._collection)
        nullTest = Core.NullTest()
        for prevTest, test, nextTest in self.selectedTests():
            env.executeTest(prevTest, test, nextTest)

    def listTimes(self):
        reportMan = Coordinator.getServiceProvider("report_manager")
        env = _TestSummariser(self._collection)
        nullTest = Core.NullTest()
        for prevTest, test, nextTest in self.selectedTests():
            env.executeTest(prevTest, test, nextTest)

    def listIDs(self, no_ids=False):
        if no_ids:
            reportMan = Coordinator.getServiceProvider("report_manager")
            env = _TestSummariser(self._collection, no_ids=True)
            nullTest = Core.NullTest()
            for prevTest, test, nextTest in self.selectedTests():
                env.executeTest(prevTest, test, nextTest)
            return

        ids = []
        for prevTest, test, nextTest in self.selectedTests():
            if test.testID is not None:
                ids.append(test.testID)
        for uid in sorted(ids):
            print(uid)

    def listModules(self):
        ids = set()
        for prevTest, test, nextTest in self.selectedTests():
            (d, m), c, f = test.uid
            ids.add(m)
        for uid in sorted(ids):
            print(uid)

    def detail(self):
        nullTest = Core.NullTest()
        reportMan = Coordinator.getServiceProvider("report_manager")
        env = _TestDetailer(self._collection)
        for prevTest, test, nextTest in self.selectedTests():
            env.executeTest(prevTest, test, nextTest)
        #env.executeTest(nullTest)

    def sphinx(self):
        env = _TestSphinxer(self._collection)
        for prevTest, test, nextTest in self.selectedTests():
            env.executeTest(prevTest, test, nextTest)
        env.end()

    def show_ids(self):
        nullTest = Core.NullTest()
        reportMan = Coordinator.getServiceProvider("report_manager")
        env = _TestIdLister(self._collection)
        for prevTest, test, nextTest in self.selectedTests():
            env.executeTest(prevTest, test, nextTest)
        #env.executeTest(nullTest)

    # TODO: This is temporary.
    @property
    def Result(self):
        return Core.Result


Coordinator.registerProvider("cscore", ("manager",), Manager())


# TODO: This, and or derived classes, should probably become a defined
#       abstraction or part of the API for manager writers.
class _TestProcessor:
    _doDump = False
    def __init__(self, collection):
        nullTest = Core.NullTest()
        self.reportMan = Coordinator.getServiceProvider("report_manager")
        self._collection = collection
        self._prevTest = nullTest
        self._setDefaultMode()
        self.exitAll = False
        self._initialCwd = os.getcwd()
        self.stop = False
        self.exitCode = 0

    def testFilter(self, test):
        return True

    def start(self):
        pass

    def end(self):
        pass

    def _setDefaultMode(self):
        self.mode = None

    def _isRunnable(self, test):
        if test is None:
            return True # This is the final clean-up phase.
        if self.exitAll:
            return False
        return test.isRunnable

    @Aspects.protectCwd
    def executeTest(self, prevTest, test, nextTest):
        if not self._isRunnable(test):
            return
        collection = self._collection
        enterSuites = collection.diffAncestors(test, prevTest)
        exitSuites = list(reversed(collection.diffAncestors(test, nextTest)))
        testLevel = collection.getLevel(test)

        self._test = test

        # TODO: Explain the chdir.
        os.chdir(self._initialCwd)

        # Perform any necessary suite(s) set up phases
        #if test.parent:
        ##    print("CHDIR PARENT", test.parent.myDir)
        os.chdir(test.parent.myDir)
        self._prepare(enterSuites, test)

        #self.setTestPhase(test, Core.RUNNING)               # TODO: Possibly nolonger required.

        # Execute the test itself, now that everything has (probably) been
        # set-up for it.
        # TODO: Not quite true - setUp is invoked in _execute().
        if test.parent.skipTests or (test.isBroken and not
                options.run_broken):
            test.startNewRun()
            rec = test.addStepRecord("run")
            rec.setResult(Core.SKIPPED)
        else:
            self._execute(test, testLevel)

        # Perform any necessary suite(s) clean up phases
        self._cleanUp(exitSuites)

        # Prepare for the next test.
        self._prevTest = test

    def setTestPhase(self, test, phase):
        if test is not None:
            test.setPhase(phase)
            self.reportMan.updateTestState(test)

    def _doSetUp(self):
        return True

    def _doTearDown(self):
        return True

    def _execute(self, test, level):
        status = Coordinator.getServiceProvider("status")
        runnable = test is None or not test.hasFailingAncestor()
        if runnable:
            self.runner = None
            runnable = self._doSetUp()
            self._doTest(level, runnable)
            self._doTearDown()
        status.update()

    def _cleanUp(self, popSuites):
        status = Coordinator.getServiceProvider("status")
        for lev, suite in popSuites:
            self.reportMan.leaveSuite(suite)
        status.update()


class _TestNullAction(_TestProcessor):
    def __init__(self, *args, **kwargs):
        super(_TestNullAction, self).__init__(*args, **kwargs)
        loadInfo()

    def _setDefaultMode(self):
        self.reportMan.setMode("NO_ACTION")

    def _doTest(self, level, runnable):
        if self._test:
            self.reportMan.prepareToRunTest(self._test,
                                            number=self._test.number)

    def _prepare(self, pushSuites, test):
        for lev, suite in pushSuites:
            self.reportMan.enterSuite(suite)


class _TestSummariser(_TestProcessor):
    def __init__(self, *args, **kwargs):
        self.no_ids = kwargs.pop("no_ids", False)
        super(_TestSummariser, self).__init__(*args, **kwargs)
        loadInfo()

    def _setDefaultMode(self):
        self.reportMan.setMode("SUMMARY")

    # TODO: Is this and the next method repeated in following 2 classes?
    def _doTest(self, level, runnable):
        if self._test:
            if self.no_ids and self._test.testID is not None:
                return
            if options.times or options.all_times:
                avg, times = getExecTimes(self._test)
                if avg is None:
                    self._test.execTime = " no data "
                elif options.all_times:
                    self._test.execTime = ",".join("%7.3f" % t for t in times) + " "
                else:
                    self._test.execTime = "%7.3f " % avg
            self.reportMan.prepareToRunTest(self._test,
                    number=self._test.number)

    def _prepare(self, pushSuites, test):
        for lev, suite in pushSuites:
            self.reportMan.enterSuite(suite)


class _TestDetailer(_TestProcessor):
    def _setDefaultMode(self):
        self.reportMan.setMode("DETAILS")

    def _doTest(self, level, runnable):
        if self._test:
            self.reportMan.prepareToRunTest(self._test, number=self._test.number)

    def _prepare(self, pushSuites, test):
        for lev, suite in pushSuites:
            self.reportMan.enterSuite(suite)


def addHang(lines, hangText):
    res = []
    pad = " " * len(hangText)
    for i, line in enumerate(lines):
        if i:
            res.append(pad + line)
        else:
            res.append(hangText + line)
    return res


class SphinxBase:
    """Base class for SPhinxy things.

    """
    def __init__(self, title):
        self.title = title
        self.label = None
        self.toc = []
        self.contents = []
        self.sections = []
        self.parent = None

    def addSection(self, title):
        section = SphinxSection(title)
        self.sections.append(section)
        section.parent = weakref.proxy(self)
        return section

    @property
    def level(self):
        if self.parent is None:
            return 0
        return 1 + self.parent.level

    def write(self, f):
        ulc = "==-~.@:_#"[self.level]
        uLine = ulc * len(self.title)
        if self.label:
            f.write(".. _%s:\n\n" % self.label)

        if self.level == 0:
            f.write("%s\n" % uLine)
        f.write("%s\n" % self.title)
        f.write("%s\n\n" % uLine)

        if self.toc:
            f.write(".. toctree::\n")
            f.write("   :maxdepth: 2\n\n")
            for line in self.toc:
                f.write("   %s\n" % line)
            f.write("\n\n")

        for line in self.contents:
            f.write("%s\n" % line)
        f.write("\n")


class SphinxSection(SphinxBase):
    """Holds contents of a Sphinx section.

    """


class SphinxDoc(SphinxBase):
    """Holds the content that can create a Sphinx reStructuredText file.

    """
    _pathToDocMap = {}

    def __init__(self, path):
        super(SphinxDoc, self).__init__("Title")
        self.path = path

    @classmethod
    def getDoc(cls, path):
        if path not in cls._pathToDocMap:
            d = SphinxDoc(path)
            cls._pathToDocMap[path] = d
        return cls._pathToDocMap[path]


class _TestSphinxer(_TestProcessor):
    def __init__(self, *args, **kwargs):
        super(_TestSphinxer, self).__init__(*args, **kwargs)
        Files.mkDir(options.sphinx)
        self.suiteDocs = {}
        self.docList = []
        self.allDoc = None
        self.tree = []
        self.sdoc = sphinx.SphinxDoc()

    def end(self):
        self.sdoc.generate()

    def _doTest(self, level, runnable):
        if self._test is not None:
            self.sdoc.addTest(self._test)

    def _initSuiteDoc(self, suite):
        pathParts, klass, _ = suite.uid
        path  = os.path.join(*pathParts)
        if klass is not None:
            self.doc.title = klass
        else:
            if path.endswith("all_tests.py"):
                path = os.path.basename(path)
            path = path.replace(".py", "")
            path = path.replace(".pyc", "")
            self.doc.title = path

        self.doc.contents.append("%s" % suite.summary)
        self.doc.contents.append("")
        for line in suite.details:
            self.doc.contents.append(line)
        self.doc.contents.append("")
        self.doc.contents.append("")

    def _initSuite(self, suite):
        path, klass, _ = suite.uid
        section = self.doc.addSection(klass)
        section.contents.append("%s" % suite.summary)
        section.contents.append("")
        for line in suite.details:
            section.contents.append(line)
        section.contents.append("")
        section.contents.append("")

    def _prepare(self, pushSuites, test):
        from cleversheep3.Test import Tester
        self.sdoc.prepareTest(pushSuites, test)

        if not pushSuites:
            return

        self.doc = None
        for lev, suite in pushSuites:
            pathParts, klass, _ = suite.uid
            path = os.path.join(*pathParts)
            path = Files.relName(path, cwd=Tester.execDir)
            #print "USE", path
            #fileSuite = sphinx.SphinxFileSuite.getSuite(path)
            #sphinxSuite = sphinx.SphinxSuite.getSuite(path, klass)

            # This is a hack.
            isAll = False
            pathParts, klass, _ = suite.uid
            path = os.path.join(*pathParts)
            q = path
            path = Files.relName(path, cwd=Tester.execDir)
            if path.endswith("all_tests.py"):
                path = path[:-12] + "index"
                isAll = True

            path = path.replace(".py", "")
            path = path.replace(".pyc", "")
            path += ".rst"
            if path.startswith("__"):
                path = path[2:]
            relPath = path
            path = os.path.join(options.sphinx, path)
            if path not in self.suiteDocs:
                self.suiteDoc = self.doc = SphinxDoc.getDoc(path)
                self.suiteDocs[path] = self.doc
                self.docList.append(self.doc)
                self._initSuiteDoc(suite)
                if self.allDoc:
                    self.allDoc.toc.append(relPath)
                if isAll:
                    self.allDoc = self.doc
            else:
                self.suiteDoc = self.doc = self.suiteDocs[path]
                if klass is not None:
                    self._initSuite(suite)


class _TestIdLister(_TestProcessor):
    def _setDefaultMode(self):
        self.reportMan.setMode("IDS-SUMMARY")

    def _doTest(self, level, runnable):
        if self._test:
            self.reportMan.prepareToRunTest(self._test, number=self._test.number)

    def _prepare(self, pushSuites, test):
        for lev, suite in pushSuites:
            self.reportMan.enterSuite(suite)


class TestResultSummariser(_TestProcessor):
    def start(self, title=""):
        self.reportMan.write("\n")
        self.reportMan.write(title)

    def _execute(self, test, level):
        phase, phaseRecord = test.phaseRecord
        if None not in (phase, phaseRecord):
            self.reportMan.summariseResult(test)

    def _prepare(self, enterSuites, test):
        for lev, suite in enterSuites:
            self.reportMan.summariseSuiteResult(suite)

    def _cleanUp(self, exitSuites):
        for lev, suite in exitSuites:
            self.reportMan.leaveSuite(suite)

    # TODO: Can, I think, delete this!
    def x__doTest(self, level, runnable):
        if self._test.amNull:
            return
        phase, phaseRecord = self._test.phaseRecord
        self.reportMan.prepareToRunTest(self._test, number=self._test.number,
                result=phaseRecord)


class TestFailureSummariser(TestResultSummariser):
    def testFilter(self, test):
        return test.hasFailed

    def executeTest(self, prevTest, test, nextTest):
        assert test.hasFailed
        super(TestFailureSummariser, self).executeTest(prevTest, test, nextTest)


class TestExecEnvironment(_TestProcessor):
    _doDump = False

    def _startResultRecording(self):
        self.runRecord = Core.RunRecord()
        if self._test is not None:
            self._test.addRunRecord(self.runRecord)

    def _doTearDown(self, tearDown=None):
        suite = self._test.parent
        if not suite:
            return None

        phaseRecord = None
        if tearDown is None:
            tearDown = Executor(suite.tearDown, self._test, "tearDown")
        phaseRecord = tearDown()

        if self._test.hasRunProblem:
            self.reportMan.logFailure(self._test)
        return phaseRecord

    def _doSetUp(self, setUp=None):
        suite = self._test.parent
        if not suite:
            return None

        # TODO: Always creating an Executor seems pointless.
        if setUp is None:
            setUp = Executor(suite.setUp, self._test, "setUp",
                             postFunc=suite.postSetUp)
        setUp()
        if self._test.hasFailed:
            self.reportMan.logFailure(self._test)
            pass
        return not self._test.hasFailed

    def _doTest(self, level, runnable, case=None, postCheck=None):
        if not self._test:
            # This is for clean-up after the last selected test.
            return

        self.reportMan.prepareToRunTest(self._test, number=self._test.number)
        if self._test.isTodo:
            phaseRecord = self._test.addStepRecord("run")
            phaseRecord.result = Core.TODO
            self.reportMan.putResult(self._test, "Test")
            return

        if case is None:
            case = Executor(self._test.func, self._test, "run",
                            trace=self._collection.spec)
            postCheck = ContinueExecutor(self._test.postCheck, self._test, "run")
        if runnable:
            self.reportMan.updateTestState(self._test)
            a = time.time()
            case()
            if not self._test.hasRunProblem:
                if not (self._test.isBug or self._test.isTodo):
                    postCheck()
            b = time.time()
            self.reportMan.putResult(self._test, "Test")
            storeTimeInfo(self._test, b - a)
        else:
            phaseRecord = self._test.addStepRecord("run")
            phaseRecord.result = Core.SKIPPED
            self.reportMan.putResult(self._test, "Test")

        if self._test.hasRunProblem:
            self.reportMan.logFailure(self._test)

    def _cleanUp(self, popSuites):
        for lev, suite in popSuites:
            if not suite.entered:
                continue
            suite.entered = False
            self.reportMan.leaveSuite(suite)
            suiteTearDown = Executor(suite.suiteTearDown, None,
                                        "suiteTearDown")
            phaseRecord = suiteTearDown()
            if phaseRecord.hasFailed:
                self.reportMan.logFailure(suiteTearDown.test)
                pass

    def _prepare(self, pushSuites, test):
        status = Coordinator.getServiceProvider("status")
        pushSuites = iter(pushSuites)
        for lev, suite in pushSuites:
            if suite.skipTests:
                continue
            suite.entered = True
            self.reportMan.enterSuite(suite)
            suiteSetUp = Executor(suite.suiteSetUp, test, "suiteSetUp")
            phaseRecord = suiteSetUp()
            status.update()
            if phaseRecord.hasFailed:
                self.exitCode |= SETUP_FAIL
                self.reportMan.logFailure(test)
                suite.skipTests = True
                break

        for lev, suite in pushSuites:
            suite.skipTests = True

    def executeTest(self, prevTest, test, nextTest):
        """Execute a specified test.

        This is only invoked if the manager has decided that the test should be
        executed; i.e. not skipped in any way.

        """
        # Make preparations to record the test's result information.
        test.startNewRun()
        try:
            abortRun = not self.reportMan.switchToTest(test,
                    test.parent.skipTests)
        except TypeError:
            abortRun = False
        if abortRun:
            self.exitAll = True
            return
            self.reportMan.switchToTest(test)
        Assertions.Assertion.reset()
        super(TestExecEnvironment, self).executeTest(prevTest, test, nextTest)
        if abortRun:
            test.abortRun()

    def _runForked(self, level):
        self.runner = runner = SubRunner(self)
        suite = self._test.parent
        setUp = Executor(suite.setUp, self._test, "setUp",
                         postFunc=suite.postSetUp)
        tearDown = Executor(suite.tearDown, self._test, "tearDown")
        case = Executor(self._test.func, self._test, "run",
                        trace=self._collection.spec)
        postCheck = ContinueExecutor(self._test.postCheck, self._test, "run")
        self.runner.addClient(setUp)
        self.runner.addClient(tearDown)
        self.runner.addClient(case)
        self.runner.addClient(postCheck)

        runner.start()
        runnable = self._doSetUp(setUp)
        self._doTest(level, runnable, case, postCheck)
        self._doTearDown(tearDown)

        runner.commandQ.put(("Q", ()))
        runner.join()

    def _runUnforked(self, level):
        self.runner = None
        runnable = self._doSetUp()
        self._doTest(level, runnable)
        self._doTearDown()

    def _execute(self, test, level):
        status = Coordinator.getServiceProvider("status")
        runnable = test is None or not test.hasFailingAncestor()
        if runnable:
            if test.shouldFork:
                self._runForked(level)
            else:
                self._runUnforked(level)
        status.update()

    def skipTest(self, prevTest, test, nextTest):
        """Skip the specified test.

        This is only invoked if the manager has decided that the test should be
        skipped.

        """
        return
        rec = test.addStepRecord("run")
        rec.setResult(Core.SKIPPED)
        test.startNewRun()


class ServiceProxy:
    def __init__(self, subRunner, proxied, group, services):
        self._subRunner = weakref.proxy(subRunner)
        self._proxied = proxied
        Coordinator.registerProvider(group, services, self)
        self._service = services[0]

    def __getattr__(self, name):
        attr = getattr(self._proxied, name)
        if not callable(attr):
            return attr
        return functools.partial(self._invoker, name)

    def _invoker(self, name, *args, **kwargs):
        self._subRunner.reportQ.put(("CS", (self._service, name, args, kwargs)))


class SubRunner(Process):
    def __init__(self, inst):
        super(SubRunner, self).__init__()
        self.commandQ = Queue()
        self.reportQ = Queue()
        self.retQ = Queue()
        self.inst = inst
        self._clients = {}
        self._proxies = []

    def run(self):
        self.f = open("hack.log", "w")
        self._reportMan = Coordinator.getServiceProvider("report_manager")
        self._status = Coordinator.getServiceProvider("status")
        self._proxies.append(ServiceProxy(self, self._reportMan,
                                          "cscore", ("report_manager",)))
        self._proxies.append(ServiceProxy(self, self._status,
                                          "cscore", ("status",)))

        while True:
            cmd, data = self.commandQ.get()
            if cmd == "Q":
                return

            elif cmd == "CF":
                try:
                    clientID, funcName, args, kwargs = data
                    attr = self._clients[clientID]
                    func = getattr(attr, funcName)
                    v = func(*args, **kwargs)
                    self.retQ.put((None, v))
                except Exception as exc:
                    stack = Errors.saveStack(inspect.trace(7), "MAN")
                    self.retQ.put((exc, stack))

    def _getThing(self, name):
        self.f.write("_getThing %r\n" % (name, ))
        self.f.flush()
        try:
            return "_reportMan", getattr(self._reportMan, name)
        except AttributeError:
            try:
                return "_status", getattr(self._status, name)
            except AttributeError:
                return "stdout", getattr(self._stdout, name)

    def __getattr__(self, funcName):
        attrName, _ = self._getThing(funcName)
        return functools.partial(self._invoker, attrName, funcName)

    def callFunc(self, clientID, funcName, *args, **kwargs):
        self.commandQ.put(("CF", (clientID, funcName, args, kwargs)))
        while True:
            try:
                exc, ret = self.retQ.get(False, 0.02)
            except Empty:
                pass
            else:
                if exc:
                    exc.procStack = ret
                    raise exc
                return ret

            try:
                cmd, data = self.reportQ.get(False)
            except Empty:
                pass
            else:
                service, name, args, kwargs = data
                provider = Coordinator.getServiceProvider(service)
                func = getattr(provider, name)
                func(*args, **kwargs)

    def _invoker(self, name, funcName, *args, **kwargs):
        self.commandQ.put(("F", (name, funcName, args, kwargs)))
        exc, ret = self.retQ.get()
        if exc:
            exc.procStack = ret
            raise exc
        return ret

    def addClient(self, client):
        self._clients[id(client)] = client
        client.setRunner(self)


class Executor:
    def __init__(self, func, test, phase, item=None, timeout=None,
            record=None, postFunc=None, trace=None):
        self._func = func
        self._postFunc = postFunc
        self._timeout = timeout
        self._item = item
        self.record = record
        self.test = test or Core.NullTest()
        self._phase = phase
        self.origExc = None
        self.stop = False
        self.spec = trace
        self._runner = None

    def setRunner(self, runner):
        self._runner = weakref.proxy(runner)

    def _invoke(self):
        self.depth = len(inspect.stack())
        if Suites._control:
            Suites._control.setTestStackDepth(self.depth)
        if self._timeout is not None:
            WatchDog.runUnderWatchDog(self._timeout, self._func)
            if self._postFunc:
                WatchDog.runUnderWatchDog(self._timeout, self._postFunc)
        else:
            if self.spec is not None:
                if Suites._control:
                    Suites._control.setTestStackDepth(self.depth + 1)
                    Suites._control.setSpec(self.spec)
                # self.spec.runAndTrace(self._func)
                self._func()
            else:
                _cs_preamble_ = None  # TODO: Rename to _cs_test_invoker_marker_
                self._func()
            if self._postFunc:
                self._postFunc()

    def _handleFailure(self, phaseRecord, msg=None, args=None):
        if self.test.isBug and self._phase == "run":
            phaseRecord.result = Core.BUG
            return

        if args is None:
            args = [msg]
        phaseRecord.result = Core.FAIL
        phaseRecord.reason = Core.FAIL
        if self.origExc is not None:
            if self.origExc.__class__ is KeyboardInterrupt:
                phaseRecord.reason = Core.USER_STOPPED
                self.test.stopAll = True
            if msg is None:
                args = self.origExc.args
            if not args:
                if str(self.origExc):
                    args = [str(self.origExc)]
                else:
                    args = [self.origExc.__class__.__name__]
            if msg is None:
                msg = self.origExc.message
            exc = Errors.FailureCondition(
                    args=args, stack=self.origExc.stack,
                    message=msg)
        else:
            # TODO: Bug if this branch is taken - stack undefined.
            exc = Errors.FailureCondition(args=args, stack=self.origExc.stack)

        phaseRecord.exc = exc

    def _getPhaseRecord(self):
        return self.test.addStepRecord(self._phase)

    def __call__(self):
        Context.switchContext(self.test.context)
        self._mustStop = False
        phaseRecord = self._getPhaseRecord()

        # Perform a controlled invocation of the test method/function. We
        # handle pretty much all exceptions, but save the exception so we can
        # re-raise it later.
        try:
            temp = BaseException
            testKillers = (SystemExit, KeyboardInterrupt, Exception)
        except NameError:
            testKillers = (Exception,)
        try:
            if self._func is not None:
                _cs_preamble_ = None
                if self._runner:
                    ret = self._runner.callFunc(id(self), "_invoke")
                else:
                    ret = self._invoke()
            else:
                print("Do Nowt!!!!")
        except testKillers as exc:
            # Save the stack for later. Note that 'try ... AttributeError'
            # here will produce the wrong result.
            self.origExc = exc
            linecache.clearcache()
            if hasattr(self.origExc, "procStack"):
                stack = self.origExc.procStack
            else:
                stack = Errors.saveStack(inspect.trace(7), "MAN")
            self.origExc.stack = stack
            self.origExc.stack.reverse()

            ss = []
            try:
                testDir = getattr(self.test.parent, "myDir", "")
            except AttributeError:
                testDir = ""
            for data in self.origExc.stack:
                fileName, lineNum, funcName, context, ctxOffset, meta = data
                if not os.path.isabs(fileName):
                    fileName = os.path.join(testDir, fileName)
                ss.append((fileName, lineNum, funcName, context,
                    ctxOffset, meta))
            self.origExc.stack[:] = ss
        else:
            # Yippee! The test passed and we are done.
            phaseRecord.result = Core.PASS
            if self.test.isBug and self._phase == "run":
                phaseRecord.result = Core.BUG_PASS
            return phaseRecord

        # Something went wrong, so ``exc`` will be the exception.
        phaseRecord.exc = self.origExc
        try:
            raise self.origExc

        except Errors.ExitSuite:
            phaseRecord.result = Core.EXIT_SUITE
            self.test.parent.skipTests = True

        except Errors.ExitAll:
            phaseRecord.result = Core.EXIT_ALL

        # TODO: Should rename Problem -> AssertionFailure
        except Errors.Problem as origExc:
            self._handleFailure(phaseRecord) # DEL

        except KeyboardInterrupt as origExc:
            msg = "Interrupted by user: %s" % origExc
            self._handleFailure(phaseRecord, msg) # DEL

        except WatchDog.Timeout as origExc:
            msg = "Test timed out: %s" % origExc
            self._handleFailure(phaseRecord, msg) # DEL

        except SystemExit as origExc:
            if origExc.args:
                msg = "Unexpected sys.exit(%r)" % self.origExc.args[0]
            else:
                msg = "Unexpected sys.exit()"
            self._handleFailure(phaseRecord, msg) # DEL

        except Exception as origExc:
            msg = "Unhandled exception occurred:\n  %s:%s" % (
                    origExc.__class__.__name__, self.origExc)
            self._handleFailure(phaseRecord, msg) # DEL

        return phaseRecord # DEL


class ContinueExecutor(Executor):
    def _getPhaseRecord(self):
        return self.test.getStepRecord(self._phase)
