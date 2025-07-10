#!/usr/bin/env python
"""An asynchronous I/O implementation.

This module provides a single class called `PollManager`. This provides a nice
interface for writing simple event driven programs.

This avoid dependencies on third party packages, such as Tornado.

"""
__docformat__ = "restructuredtext"

import select
import time
import errno
import queue

from cleversheep3.Prog.SortedQ import SortedQ
from cleversheep3.Test import normaliseFileOrFd

# Make some standard select module names visible within this module.
try:
    poll = select.poll
    POLLIN = select.POLLIN
    POLLPRI = select.POLLPRI
    POLLOUT = select.POLLOUT
    POLLERR = select.POLLERR
    POLLHUP = select.POLLHUP
    POLLNVAL = select.POLLNVAL

except AttributeError: #pragma: unless sys.platform.startswith("linux")
    # Ah! Good old Windows, which does not support ``poll``. The
    # ``SimPoll`` module does a good enough job, using ``select``.
    from SimPoll import *


class Callback:
    """A general callback.

    """
    def __init__(self, activeLevel, ref, args, kwargs):
        if activeLevel == 0:
            activeLevel = 1
        self.activeLevel = activeLevel
        self.ref = ref
        self.args = args
        self.kwargs = kwargs

    def invoke(self, overrides=None):
        overrides = overrides or {}
        args = list(self.args)
        for i, v in overrides.items():
            args[i] = v
        return self.ref(*args, **self.kwargs)


class Timer(Callback):
    """A timer.

    """
    def __init__(self, activeLevel, when, delta, ref, args, kwargs):
        super(Timer, self).__init__(activeLevel, ref, args, kwargs)
        self.when = when
        self.delta = delta


class _Context:
    def __init__(self, timers, registrations):
        self.timers = timers
        self.registrations = registrations
        self.active = True


class PollManagerImpl:
    """An event based asynchonous I/O (reactor).

    """
    POLLIN = globals().get("POLLIN")
    POLLPRI = globals().get("POLLPRI")
    POLLOUT = globals().get("POLLOUT")
    POLLERR = globals().get("POLLERR")
    POLLHUP = globals().get("POLLHUP")
    POLLNVAL = globals().get("POLLNVAL")

    #{ Construction
    def __init__(self, CallbackRef):
        """Constructor"""
        self.poller = poll()
        self._stack = [_Context(SortedQ(), {})]
        self.workFunctions = []
        self._quitting = False
        self.toReinsert = []
        self._excToRaise = None
        self.queue = queue.Queue()
        self.CallbackRef = CallbackRef
        self._nestAdd = 0
        self.registrations = {}

    @property
    def timers(self):
        return self._stack[-1].timers

    @property
    def xregistrations(self):
        return self._stack[-1].registrations

    #{ Setting up call back functions.
    def addCallback(self, cb_func, *args, **kwargs):
        """Add a callback to be invoked on the next iteration of the main loop.

        This can safely be invoked from any thread. The function will be
        invoked in the PollManager's thread.

        :Param cb_func, args, kwargs:
            The function to be invoked. The function is invoked as: ``cb_func
            (*args, **kwargs)``.

        """
        self.queue.put((self.CallbackRef(cb_func), args, kwargs))

    def clearCallbacks(self):
        """Discard and queued callbacks.

        """
        while True:
            try:
                self.queue.get(False)
            except queue.Empty:
                break

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
        return self._doAddTimeout(delta, None, cb_func, args, kwargs)

    def addRepeatingTimeout(self, delta, cb_func, *args, **kwargs):
        """Add a repeating timeout to invoke `cb_func`.

        As for `addTimeout`, but the *&cb_func* is invoked repeatedly
        approximately every *delta* seconds.
        """
        return self._doAddTimeout(delta, delta, cb_func, args, kwargs)

    def _doAddTimeout(self, firstDelta, delta, cb_func, args, kwargs):
        now = time.time()
        when = now + firstDelta
        tid = self.timers.add(when,
                Timer(self.active + self._nestAdd, when, delta,
                      self.CallbackRef(cb_func), args, kwargs))
        return tid

    def addFileCallback(self, fileOrFd, eventTypes, cb_func, *args, **kwargs):
        """Register for callbacks when file is active.

        Registers for a specific handler to be called when there is activity
        on the specified file. See the standard select module for the valid
        eventType values.

        :Param fileOrFd:
            The file or file descriptor to be monitored.
        :Param eventTypes:
            The types of event to monitor for. This is a bitmask, which may
            contain any combination of ``POLLIN`` and ``POLLOUT`` or ``POLLERR``.
        :Param cb_func, args, kwargs:
            The function to be invoked when file activity occurs. The function
            is invoked as: ``cb_func (*args, **kwargs)``.
        """
        fd = normaliseFileOrFd(fileOrFd)
        if fd < 0:
            return -1
        reg = self.registrations.setdefault(fd, {})
        modified = False
        for evType in (POLLIN, POLLOUT, POLLERR):
            if eventTypes & evType:
                reg[evType] = Callback(self.active + self._nestAdd,
                                       self.CallbackRef(cb_func),
                                       (fd, evType) + args, kwargs)
                modified = True
        if not reg:
            self.registrations.pop(fd)
            return -1
        if modified:
            self._updateRegistration(fd)

    def removeFileCallback(self, fileOrFd, eventTypes=POLLIN|POLLOUT|POLLERR):
        """Stop monitoring a file for activity.

        This stops all monitoring for a particular file and event type(s)
        combination.

        :Param fileOrFd:
            The file or file descriptor to be monitored.
        :Param eventTypes:
            The types of event to stop monitoring for. This is a bitmask, which
            may contain any combination of ``POLLIN`` or ``POLLOUT``. Simply
            omit this, it you wish to stop moitoring for *all* activity on this
            file.
        """
        fd = normaliseFileOrFd(fileOrFd)
        if fd < 0:
            return -1
        if fd not in self.registrations:
            return
        reg = self.registrations[fd]
        modified = False
        for evType in (POLLIN, POLLOUT, POLLERR):
            if eventTypes & evType:
                reg.pop(evType, None)
                modified = True
        if not reg:
            self.registrations.pop(fd)
        if modified:
            self._updateRegistration(fd)

    def addInputCallback(self, fileOrFd, cb_func, *args, **kwargs):
        """Convenience func for: addFileCallback(fileOrFd, POLLIN, ...)"""
        return self.addFileCallback(fileOrFd, POLLIN, cb_func,
                *args, **kwargs)

    def addOutputCallback(self, fileOrFd, cb_func, *args, **kwargs):
        """Convenience func for: addFileCallback(fileOrFd, POLLOUT, ...)"""
        return self.addFileCallback(fileOrFd, POLLOUT, cb_func,
                *args, **kwargs)

    def addWorkFunction(self, cb):
        """Add function to be invoked when some work has been done.

        """
        self.workFunctions.append(self.CallbackRef(cb))

    #{ Removing up call back functions.
    def removeWorkFunction(self, cb):
        """Remove a function from the list of work functions.

        """
        for f in self.workFunctions:
            if f.isFunc(cb):
                break
        else:
            return
        self.workFunctions.remove(f)

    def removeTimeout(self, uid):
        """Remove the timer with the given id.

        The timer is effectively deleted and will not 'fire', even if it is
        over due.

        :Param uid:
            An unique ID as returned from `addTimeout` or
            `addRepeatingTimeout`. If the ID is unknown then this it is
            silently ignored.
        """
        for ent in self._stack:
            ent.timers.remove(uid)
        if self.toReinsert:
            self.toReinsert[:] = [(w, u, a) for w, u, a in self.toReinsert
                    if u != uid]

    def fixBadFile(self): #pragma: unreachable
        bad = []
        for fd in self.registrations:
            try:
                select.select([fd], [], [], 0)
            except select.error as details:
                if details.args[0] == errno.EINTR:
                    continue
                if details.args[0] == errno.ENOTSOCK:
                    bad.append(fd)
                    continue
                raise
        for fd in bad:
            self.removeInputCallback(fd)

    def removeInputCallback(self, fileOrFd):
        """Convenience func for: removeFileCallback(fileOrFd, POLLIN, ...)"""
        return self.removeFileCallback(fileOrFd, POLLIN)

    def removeOutputCallback(self, fileOrFd):
        """Convenience func for: removeFileCallback(fileOrFd, POLLOUT, ...)"""
        return self.removeFileCallback(fileOrFd, POLLOUT)

    #{ Starting and stopping the PollManager
    def quit(self, allLevels=False, top=False):
        """Used to stop running.

        The manager will stop processing events shortly after this. Some
        pending events and timeouts can still get processed.

        :Parameters:
          allLevels
            If set to a true value then all nested all nested calls to run
            are exited.

        """
        if top:
            self._stack[-1].active = False
        else:
            self._stack[self._invokeLevel].active = False
        if allLevels:
            for ent in self._stack:
                ent.active = False

    def processPlainCallbacks(self):
        didWork = False
        while True:
            try:
                func, args, kwargs = self.queue.get(False)
            except queue.Empty:
                break
            didWork = True
            func(*args, **kwargs)

        return didWork

    def processTimers(self):
        """Invoke functions for all timers that have expired.

        :Return:
            True if at least one timer function was invoked.

        """
        didWork = False
        while self.timers:
            tod, uid, timer = self.timers.head()
            now = time.time()
            if tod <= time.time():
                self.timers.pop()
                if timer.ref.isDead():
                    continue
                toKill = False
                if timer.delta is not None:
                    # A repeating timer. Work out when it is next expected to
                    # expire, based on when it should have expired. And add to
                    # the list of timers that should be reinserted.
                    new_tod = tod + timer.delta
                    timer.when = new_tod
                    self.toReinsert.append((new_tod, uid, timer))
                else:
                    for ent in self._stack:
                        ent.timers.remove(uid)
                    toKill = True

                # Invoke the callback, which may remove the entry from the
                # reinsert list.
                savedLevel, self._invokeLevel = self._invokeLevel, timer.activeLevel
                try:
                    timer.invoke()
                finally:
                    self._invokeLevel = savedLevel
                if toKill:
                    timer.ref.kill()
                didWork = True
                self._retrigger(timer.delta, uid)
            else:
                break

        for when, uid, timer in self.toReinsert:
            self.timers.reInsert(when, uid, timer)
        self.toReinsert = []

        return didWork

    def _retrigger(self, delta, uid):
        # Choose a pragmatic retrigger time for a repeating timeout.
        if delta is None:
            return

        try:
            new_tod, top_uid, timer = self.toReinsert[-1]
        except IndexError:
            top_uid = None

        # If the timer is still there and the new time has been
        # missed then choose the next firing time in the future.
        if top_uid == uid:
            self.toReinsert.pop()
            now = time.time()
            while new_tod < now:
                new_tod += timer.delta
                timer.when = new_tod
            self.toReinsert.append((new_tod, uid, timer))

    def raiseError(self, exc):
        self._excToRaise = exc

    @property
    def active(self):
        return len(self._stack) - 1

    def prepareToNest(self):
        """Prepare to for a nested invocation of the `run` method.

        Any calls to add timeouts or file handler, before the call to `run`
        will arrange for the callbacks to run at the level of the nested
        invocation.

        """
        self._nestAdd = 1

    def run(self):
        """The main loop of the PollManager.

        This method loops until the `quit` method is called. It uses the
        select module to detect file activity and perform timeout processing,
        calling the handler functions as necessary.

        """
        newReg = dict((fd, grp.copy())
                        for fd, grp in self.registrations.items())
        self._stack.append(_Context(self.timers.copy(), newReg))
        self._invokeLevel = self.active
        self._nestAdd = 0
        while self._excToRaise is None and self._stack[-1].active:
            # Handle any queued plain callbacks.
            if self.processPlainCallbacks():
                continue

            # Get number of milliseconds until the first timer (if any)
            # expires.
            didWork = False
            delay = None
            if self.timers:
                tod, uid, timer = self.timers.head()
                delay = max(0, int((timer.when - time.time()) * 1000.0))

            # Poll for events or until a timer is due.
            try:
                a = time.time()
                pollEvents = self.poller.poll(delay)

            except select.error as details: #pragma: unreachable
                if details.args[0] not in (errno.EINTR, errno.ENOTSOCK):
                    # Something bad and unexpected happened.
                    raise

                if details.args[0] == errno.ENOTSOCK:
                    # A file has closed under us or we are on Windows and
                    # the FD is not for a socket. Either way we silently
                    # deal with the problem.
                    self.fixBadFile()
                pollEvents = []

            # Invoke the callbacks for all file events.
            for fd, ev in pollEvents:
                self._handleFileActivity(fd, ev)
                didWork = True

            # Invoke callbacks for all expired timers and then any queued
            # callbacks.
            if self.timers:
                if self.processTimers():
                    didWork = True
            if self.processPlainCallbacks():
                didWork = True

            # Invoke any work functions, provided that some work was done.
            if didWork:
                for func in self.workFunctions:
                    func()

        uid = self.timers.getUID()
        ctx = self._stack.pop()
        self.timers.setUID(uid)
        if len(self._stack) == 1:
            # Exit from a non-nested run, so preserve the timers.
            for tod, uid, timer in ctx.timers:
                self.timers.quickReAdd(tod, uid, timer)
            self.timers.resort(lambda v, t: t.when)

        if self._excToRaise:
            exc = self._excToRaise
            self._excToRaise = None
            raise exc

    #{ Internals
    def _handleFileActivity(self, fd, eventTypes):
        reg = self.registrations.get(fd)
        if not reg:
            return ##pragma: unreachable

        # Handle POLLIN and POLLOUT *before* checking 'error' conditions. The
        # eventTypes mask can contain both and, in that case, the client can
        # (for exaample) still perform a successful read.
        for evType in (POLLIN, POLLOUT):
            if (evType & eventTypes) == 0:
                continue
            if evType in reg:
                callback = reg[evType]
                savedLevel, self._invokeLevel = self._invokeLevel, callback.activeLevel
                try:
                    callback.invoke()
                finally:
                    self._invokeLevel = savedLevel

        # Any 'error' condition causes all handlers for the file to be removed.
        # The calback is not invoked.
        for errType in (POLLHUP, POLLERR, POLLNVAL):
            if errType & eventTypes:
                try:
                    del self.registrations[fd]
                except KeyError:
                    # A callback has already removed this FD. This is not an error.
                    pass
                else:
                    self._updateRegistration(fd)
                return

        # FUTURE: Should allow addFileCallback to request that error conditions
        #         are propagated to the callback.
        if 0:
            # Any error condition is passed to the best handler and then all
            # handlers for the file removed. The POLLIN handler is chosen in
            # preference to the POLLOUT handler.
            for errType in (POLLHUP, POLLERR, POLLNVAL):
                if errType & eventTypes:
                    for evType in (POLLIN, POLLOUT):
                        if evType in reg:
                            callback = reg[evType]
                            savedLevel, self._invokeLevel = (self._invokeLevel,
                                                             callback.activeLevel)
                            try:
                                callback.invoke({1: errType})
                            finally:
                                self._invokeLevel = savedLevel
                            break

                    # Following a hang up, closed file or error, we need to
                    # unregister the file descriptor.
                    try:
                        del self.registrations[fd]
                    except KeyError:
                        # A callback has already removed this FD. This is not an error.
                        pass
                    else:
                        self._updateRegistration(fd)
                    return

    def _updateRegistration(self, fd):
        reg = self.registrations.get(fd)
        if reg:
            eventTypes = 0
            for evType in (POLLIN, POLLOUT, POLLERR):
                if evType in reg:
                    eventTypes |= evType
            self.poller.register(fd, eventTypes)
        else:
            self.poller.unregister(fd)
