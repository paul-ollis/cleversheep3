#!/usr/bin/env python
"""The Test Suite Class.

Although you do not need to package test functions as methods of a class,
for any non-trivial test scripts, it makes sense to do so, using the `Suite`
class provided by this module.

Normally, it is not necessary to import this module directly, just do the
normal
:<py>:

    from cleversheep3.Test.Tester import *

and use ``Suite`` directly.

"""
__docformat__ = "restructuredtext"

import os
import time
import inspect

from cleversheep3.Test import PollManager
from cleversheep3.App import Config
from cleversheep3.Test.Tester import Assertions
from cleversheep3.Test.Tester import Coordinator
from cleversheep3.Test.Tester import log
from cleversheep3.Prog.Aspects import decorator, intelliprop

__all__ = ["Suite", "Controller"]

options = Config.Options("cstest")


def _untraced(func):
    """Method decorator to run without tracing."""
    def call(self, *args, **kwargs):
        tracingDisabled = getattr(self._spec, 'tracingDisabled', None)
        if tracingDisabled is not None:
            with tracingDisabled():
                return func(self, *args, **kwargs)
        else:
            return func(self, *args, **kwargs)

    return call


class _Struct:
    def __init__(self):
        self.found = False
        self.data = None


class MetaSuite(type):
    """The metaclass for a `Suite`.

    This over-rides the ``__new__`` class method in order to give each class
    derived from `Suite` a sequence number. This then allows the test
    discovery to keep the suites in the order they appear within a script.
    """
    seq = 0
    testSeqMin, testSeqMax = 0, -1

    def __new__(cls, name, bases, klassDict):
        childDict = klassDict.copy()
        toDel = []

        tests = [(tName, value) for tName, value in klassDict.items()
                 if getattr(value, 'cs_test_info', None) is not None]

        theKlass = type.__new__(cls, name, bases, childDict)
        for tName, value in tests:
            info = value.cs_test_info
            if info.reserved_cs_flags['defined_in_base'] is None:
                info.reserved_cs_flags['defined_in_base'] = theKlass
        if name != "Suite":
            theKlass._cs_suite_seq_ = MetaSuite.seq
            MetaSuite.seq += 1
        return theKlass


class _CSAttrs:
    def __init__(self, fork_all=False):
        self.fork_all = False

    def copy(self):
        copied = _CSAttrs()
        copied.__dict__.update(self.__dict__)
        return copied


class Suite(metaclass=MetaSuite):
    """Base class for all test suites.

    For non-trivial test suite, it is recommended that you create them using
    this class. This class provides a single property called `control`, which
    is an instance of the `Controller` class. This provides access to the
    various test support methods, such as `Controller.delay` and
    `Controller.expect`.

    """
    cs_attrs = _CSAttrs()

    def __init__(self, *args, **kwargs): #pragma: untraceable
        pass

    def setUp(self):
        """This is invoked before each test method is invoked.

        This is the place to perform common per-test actions, which are
        necessary to ensure that the test is running in the correct
        environment.

        This is typically over-ridden when required. The default setUp
        method does nothing.
        """

    def postSetUp(self):
        """This is invoked immediately after successful setUp.

        This is the place to perform common per-setUp actions, which
        need (for example) to act on changes made by one or more base
        class setUp invocations.

        This is typically over-ridden when required. The default postSetUp
        method does nothing.
        """

    def tearDown(self):
        """This is invoked after each test method has finished.

        This is the place to perform common per-test actions, which are
        necessary to ensure that anything left by the test gets cleaned up.
        The framework assures that this will get run even if the test fails
        or raises an unexpected exception.

        This is typically over-ridden when required. The default tearDown
        method does nothing.
        """

    def suiteSetUp(self):
        """This is invoked before the first test method is invoked.

        This is the place to perform common per-suite actions, which are
        necessary to ensure that all the tests in the suite are running in the
        correct environment.

        This is typically over-ridden when required. The default suiteSetUp
        method does nothing.
        """

    def suiteTearDown(self):
        """This is invoked after the last test method has finished.

        This is the place to perform common per-suite actions, which are
        necessary to ensure that anything left by the suite's test gets cleaned
        up. The framework assures that this will get run even if any test fails
        or raises an unexpected exception.

        This is typically over-ridden when required. The default suiteTearDown
        method does nothing.
        """

    @intelliprop
    def control(self):
        """Provides the test control services.

        This is a `Controller` instance, which is shared by all loaded test
        suites.
        """
        return control()

_control = None


def control():
    global _control
    if _control is None:
        _control = Controller()
    return _control


class AutoConfigFile(Config.ConfigFile):
    def __init__(self, name):
        """Initialisation.

        :Parameters:
          name
            The base name of the configuration file.

        """
        super(AutoConfigFile, self).__init__()
        self.reactor = "cs"
        self.load(name)

    def load(self, name):
        """Load in files with the given name from standard locations.

        :Parameters:
          name
            The base name of the configuration file.

        """
        for dirPath in [os.path.expanduser("~"), "."]:
            path = os.path.join(dirPath, name)
            try:
                f = open(path, "rt")
            except IOError:
                continue

            d = {}
            exec(f.read(), d, d)
            self.__dict__.update(d)


options.addConfigFileValues(".cstestrc", AutoConfigFile(".cstestrc"))


class Controller:
    """Provides access to test control functions.

    Each `Suite` provides a reference to the singleton instance of this
    class. It provides the special control functions used to manage the way a
    test executes.

    In particular, the methods provided here allow test scripts that can
    interact with other components in an asynchronous manner.

    """
    def __init__(self):
        self._poll = None
        self._update_tid = None
        self._end = 0
        self._testDepth = None
        self._spec = None

    def _update(self):
        status = Coordinator.getServiceProvider("status")
        rem = max(0.0, self._end - time.time())
        status.setField("delay", "T:%5.1f" % rem)
        status.update()

    def _prepare_update(self, t):
        self._update_tid = None
        if t > 0.5:
            self._end = time.time() + t
            self._update_tid = self.poll.addRepeatingTimeout(0.1,
                    self._update)

    def _kill_update(self):
        status = Coordinator.getServiceProvider("status")
        if self._update_tid is not None:
            self.poll.removeTimeout(self._update_tid)
        return
        status.setField("delay", "")

    def setTestStackDepth(self, depth):
        self._testDepth = depth

    def setSpec(self, spec):
        self._spec = spec

    @property
    def poll(self):
        """The `Test.PollMan.Poller` instance used by this controller."""

        if self._poll is None:
            self._poll = PollManager.PollManager()
        return self._poll

    @_untraced
    def delay(self, t):
        """Effectively pause the execution of the currently executing script
        for a period of time.

        It is important that you use this rather than ``time.sleep``. This
        method allows the test framework to continue to interact with other
        components.

        :Parameters:
          t
            The time in seconds to pause for. This can be a float, for example
            1.5 will cause a 1.5 second delay.

        """
        def wakeUp():
            self.poll.quit()

        self._prepare_update(t)
        self.poll.prepareToNest()
        tid = self.poll.addTimeout(t, wakeUp)
        try:
            self.poll.run()
        finally:
            self._kill_update()
            self.poll.removeTimeout(tid)

    @_untraced
    def expect(self, maxWait, checker, makeMsg, commentary=None,
                    *args, **kwargs):
        """Wait some maximum time for an expected event.

        This effectively stops the flow of the currently executing script.
        While the main flow is paused, the ``checker`` function will be
        periodically invoked. The ``checker`` function is responsible for
        checking whether the event has occurred; returning ``True`` if it has.
        Often this checking involves querying the `TestEventStore`.

        If ``maxWait`` seconds expire before the ``checker`` function returns
        ``True`` then the current test fails.

        Although this pauses the main flow of a test, the framework will
        continue to interact with other components.

        Parameters:
          maxWait
            The nominal maximum time to wait for the event to occur. If the
            event does occur within this time then the check passes. This is
            not an accurately timed period; in practice the function will wait
            slightly longer. However, it will never wait for a shorter period.
            The precise interval will depend on a number of factors including
            the platform and other activity.
          checker
            A function that is responsible for checking whether the event has
            occurred. It is invoked as ``checker(*args, **kwargs)`` and should
            return a True value if the event is deemed to have happened.
          makeMsg
            A function to create an explanatory message if the check does not
            pass within the `maxWait` period. It is invoked simply as
            ``makeMsg()`` and should return a string, which may span more than
            one line.
          args, kwargs
            Additional arguments to be passed to the `checker` function.
          checkInterval
            The time between calls to the ``checker`` function. This defaults
            to 0.1 seconds. You can use a smaller value if the checker function
            is slow or reduce for more responsive tests.

        """
        checkInterval = kwargs.pop("checkInterval", 0.1)
        self._prepare_update(maxWait)
        status = Coordinator.getServiceProvider("status")
        if commentary is not None:
            status.setField("commentary", commentary)
        try:
            s = self._waitFor(maxWait, checker, args, kwargs,
                    checkInterval=checkInterval)
            if not s.found:
                Assertions.fail(makeMessage=makeMsg)
            return s.data
        finally:
            self._kill_update()

    @_untraced
    def dontExpect(self, maxWait, checker, makeMsg,
                *args, **kwargs):
        """Wait checking that an event does not occur.

        This is the inverse of `expect`; the tested event must not occur for
        the test to pass.

        Parameters:
          maxWait
            The time to wait checking for the event. If the
            event does occur within this time then the check fails.
          checker
            A function that is responsible for checking whether the event has
            occurred. It is invoked as ``checker(*args, **kwargs)`` and should
            return a True value if the event is deemed to have happened.
          makeMsg
            A function to create an explanatory message in the event of
            failure. It is invoked simply as ``makeMsg()`` and should return a
            string, which may span more than one line.
          checkInterval
            The time between calls to the ``checker`` function. This defaults
            to 0.1 seconds. You can use a smaller value if the checker function
            is slow or reduce for more responsive tests.
          args, kwargs
            Additional arguments to be passed to the `checker` function.

        """
        checkInterval = kwargs.pop("checkInterval", 0.1)
        self._prepare_update(maxWait)
        try:
            s = self._waitFor(maxWait, checker, args, kwargs,
                    checkInterval=checkInterval)
            if s.found:
                Assertions.fail(makeMessage=makeMsg)
        finally:
            self._kill_update()

    def _waitFor(self, maxWait, checker, args, kwargs, checkInterval=0.1):
        s = _Struct()

        def check():
            v = checker(*args, **kwargs)
            if v:
                s.found = True
                s.data = v
                self.poll.quit()
        self.poll.prepareToNest()
        self.poll.addTimeout(0, check)
        tid1 = self.poll.addRepeatingTimeout(checkInterval, check)
        tid2 = self.poll.addTimeout(maxWait, self.poll.quit)
        try:
            self.poll.run()
            return s
        finally:
            self.poll.removeTimeout(tid1)
            self.poll.removeTimeout(tid2)

    def addCallback(self, cb_func, *args, **kwargs):
        """Add a callback to be invoked on the next iteration of the main loop.

        This can safely be invoked from any thread. The function will be
        invoked in the Test's thread.

        :Param cb_func, args, kwargs:
            The function to be invoked. The function is invoked as: ``cb_func
            (*args, **kwargs)``.

        """
        self.poll.addCallback(cb_func, *args, **kwargs)

    @_untraced
    def addTimeout(self, delta, cb_func, *args, **kwargs):
        """Add a one-shot timeout to invoke `cb_func`.

        :Param delta:
            When to invoke the `cb_func`. It is a floating point number in
            seconds. Values of less than 0.01 are likely to result in an
            almost immediate callback.
        :Param cb_func, args, kwargs:
            The function to be invoked when the timer expires. The function is
            invoked as: ``cb_func (*args, **kwargs)``.

        :Return:
            A unique ID that may be passed to `removeTimeout`.

        """
        return self.poll.addTimeout(delta, cb_func, *args, **kwargs)

    @_untraced
    def addRepeatingTimeout(self, delta, cb_func, *args, **kwargs):
        """Add a repeating timeout to invoke `cb_func`.

        As for `addTimeout`, but the *&cb_func* is invoked repeatedly
        approximately every *delta* seconds.

        :Return:
            A unique ID that may be passed to `removeTimeout`.

        """
        return self.poll.addRepeatingTimeout(delta, cb_func, *args, **kwargs)

    # TODO: This and the PollManager funciton should take *args, **kwargs.
    @_untraced
    def addWorkFunction(self, cb_func):
        """Add function to be invoked when some work has been done.

        """
        return self.poll.addWorkFunction(cb_func)

    @_untraced
    def removeWorkFunction(self, cb_func):
        """Remove a function from the list of work functions.

        """
        self.poll.removeWorkFunction(cb_func)

    @_untraced
    def removeTimeout(self, uid):
        """Remove the timer with the given id.

        The timer is effectively deleted and will not 'fire', even if it is
        over due.

        :Param uid:
            An unique ID as returned from `addTimeout` or
            `addRepeatingTimeout`. If the ID is unknown then this it is
            silently ignored.
        """
        self.poll.removeTimeout(uid)

    @_untraced
    def prompt(self, message, ok="OK", notOk=""):
        """Prompt the user to do something before the test continues.

        :Parameters:
          message
            A message to display to the user.
          ok
            The label for the 'ok' button/response.
          notOk
            The label for the 'notOk'/'cancel' button/response.
            By default this is an epmty string, in which case no notOk/cancel
            response is possible.

        :Return:
          The label string for the selected response.

        """
        res = []
        def resultCallback(result):
            res.append(result)

        prompter = Coordinator.getServiceProvider("prompter")
        prompter.prompt(message, ok=ok, notOk=notOk, resultCB=resultCallback)
        while not res:
            self.delay(0.60)
        return res[0]
