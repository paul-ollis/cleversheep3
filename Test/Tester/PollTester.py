#!/usr/bin/env python
"""Support for writing tests that must cooperate with the PollManager.

See `PollSuite` for the main details.
"""
__docformat__ = "restructuredtext"

import sys
import time
import types
import inspect

from cleversheep3.Test import Tester
from cleversheep3.Test import PollManager
from cleversheep3.Prog.Aspects import decorMethods, decorator


__all__ = ["pollAware", "PollSuite"]


@decorator
def pollAware(func, self, *args, **kwargs):
    """This is a function decorator that runs a generator based test/helper.

    This decorator is designed to decorate methods that are specific to classes
    derived from `PollSuite` class. In addition the methods to be decorated
    are normally generators, see `PollSuite` for more details. The decorated
    method is modified to do the following:

      1. The method is invoked and the returned generator added to the
         PollSuite's stack of actors.

      2. A single `wait` action with a zero timeout is added to the
         actions set. This is to arrange for the test generator to be
         immediately used.

      3. If there were no actors previously, a 0.1 second repeating timeout
         is set up to invoke the `PollSuite._sched` method.

    If the decorated method is not, in fact, a generator then this decorator
    essentially has not effect.
    """
    # Invoke the function. If the returned value is not a generator, then our
    # work is done.
    generator = func(self, *args, **kwargs)
    if not isinstance(generator, types.GeneratorType):
        # For a non-generator function, the returned value is actually,
        # well, the return value; so we return it!
        return generator

    # The function is written as a generator. So we push it onto the actors
    # stack.
    self._actors.append(generator)
    self._actions = {"Delay": time.time()}
    self.pollMan.addTimeout(0.0, self._sched)

    # If this is the only actor set up the timer and kick off the PollManager.
    if len(self._actors) == 1:
        try:
            id = self.pollMan.addRepeatingTimeout(0.1, self._sched)
            self.pollMan.run()
        finally:
            self.pollMan.removeTimeout(id)
    else:
        if not self.pollMan.active:
            self.pollMan.run()


class MetaPollTest(Tester.MetaSuite):
    """The meta class for the PollSuite class.

    All this actually does is decorate the ``test_`` methods with the ``pollAware``
    decorator. This is a nice approach because the decoration magically works
    for all classes derived from the PollSuite class.
    """
    def __new__(cls, name, bases, d):
        klass = super(MetaPollTest, cls).__new__(cls, name, bases, d)
        decorMethods(klass, Tester._isTest, pollAware)
        return klass


thePollMan = None


class PollSuite(Tester.Suite, metaclass=MetaPollTest):
    """A class for tests that run within an event driven framework.

    Introduction

    Well, the event driven framework is the `cleversheep3.Test.PollManager`, but
    one day I might make things a bit more abstract. Anyway, this only requires
    the repeating time-out feature.

    The important feature is that this provides support for writing tests that
    'look' sequential but actually run in some non-sequential (i.e., at time of
    writing, event driven) framework.

    The rules are:

    - You use this class as the base of classes that implement tests.
      Although this module uses the `cleversheep3.Test.Tester` module, you need
      this class's infrastructure if you need event driven features.

    - The ``test_...`` methods that are the test need to be written in a
      stylised generator form.


    How it Works

    A unit test is relatively simple. You write something of the form::

      Set things up
      Do thing 1
      Check thing 1
      Do thing 2
      Check thing 2
      ...
      Tear things down

    Everything above is sequential and single threaded. For tests at higher
    level, such as a component that runs as a separate process, things are
    not so simple. The complications are:

    - The component under test runs asynchronously.
    - You may need to emulate one or more other components, which may also
      need to appear to run and interact asynchronously.
    - The test, however, needs to go through a fixed set of steps in order
      and in a repeatable fashion.

    When things happen asynchronously, it is often possible to manage this
    using an event driven framework. In most test scenarios, the harness does
    not need to do much in response to a given event, so latency is not a big
    issue. This allows us to avoid the complexity of multi-threaded or
    multi-process solutions. The emulated componentes may then 'simply' tied
    into the event driven framework.

    However, the test 'script' TODO

    :Todo:
        I have got in a mess here with the over-loading of 'event'. The
        PollManager is an event driven framework, but the test framework has
        events as well.
    """
    def __init__(self):
        global thePollMan
        if thePollMan is None: #pragma: unreachable (happens pre-coverage)
            thePollMan = PollManager.PollManager()
        self.pollMan = thePollMan
        self._actions = {}   # A dictionary of outstanding actions.
        self._actors = []    # A stack of active test generators.

    def delay(self, t):
        """Arrange to wait for t seconds.

        The smallest sensible value for t is 0.1 because that is the interval
        used by the scheduler.
        """
        t = time.time() + t
        self._actions["Delay"] = t


    def _sched_Delay(self, now, t):
        self.didSomething = t <= now

    def _sched_Expect(self, now, data):
        t, checker, makeMsg, stack, args, kwargs = data
        if t <= now:
            # The check timeout has expired; i.e. failed.
            self.didSomething = True
            Tester.fail(makeMsg(*args, **kwargs), altStack=stack)
        else:
            if checker(*args, **kwargs):
                self.didSomething = True

    def _sched_DontExpect(self, now, data):
        t, checker, makeMsg, stack, args, kwargs = data
        if t <= now:
            # The check timeout has expired; i.e. the (negative) test has
            # passed
            self.didSomething = True
        else:
            if checker(*args, **kwargs):
                self.didSomething = True
                Tester.fail(makeMsg(*args, **kwargs), altStack=stack)

    def step(self, act):
        """Invoke the nest step of the test.

        This is invoked by `_sched` to essentially inokve `next` on the current
        test actor; which may be the test itself or a `pollAware` helper
        function.

        If the the actor is finished then any paused actor is stepped and if that
        one is finished then the next pause actor is stepped, and so on.
        """
        if not self.didSomething:
            return
        del self._actions[act]
        while self._actors:
            try:
                next(self._actors[-1])
                break
            except StopIteration:
                self._actors.pop()
                if not self._actors:
                    self.pollMan.quit()

    def _sched(self):
        """The polled test scheduler.

        It is this timer callback routine that is responsible for essentially
        executing the current test function.
        This is invoked once every 0.1 seconds to see whether any pending
        actions have completed.
        """
        self.stackDepth = len(inspect.stack())
        now = time.time()
        self.didSomething = False
        for act, value in self._actions.items():
            funcName = "_sched_%s" % act
            method = getattr(self, funcName, None)
            if method is None:
                fail("Invalid action name %s\n", act) #pragma: unreachable

            try:
                method(now, value)
                self.step(act)
            except:
                # Any exception means we need to empty the actors stack and
                # stop the PollManager.
                self.pollMan.quit()
                self._actors[:] = []
                self._actions = {}
                raise

            if self.didSomething:
                return

# For backward compatability
PollTester = PollSuite
