"""Async I/O wrapped around Twisted's reactor.

"""
__docformat__ = "restructuredtext"

import select
import weakref
import time

from cleversheep3.Test import normaliseFileOrFd


for klass, name in [("epollreactor", "EPollReactor"),
                    ("pollreactor", "PollReactor"),
                    ("selectreactor", "SelectReactor")]:
    try:
        d = globals()
        exec("from twisted.internet.%s import %s as reactor" % (
                klass, name), d, d)
        break
    except ImportError as exc:
        pass

from zope.interface import implements
from twisted.internet.interfaces import (ILoggingContext,
                                         IFileDescriptor,
                                         IReadDescriptor,
                                         IWriteDescriptor,
                                         )
from twisted.internet.error import AlreadyCalled


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


@implementer(ILoggingContext)
class LogContext:

    def __init__(self, prefix=''):
        self.prefix = prefix

    def logPrefix(self):
        return self.prefix


@implementer(IFileDescriptor)
class FileDescriptor(LogContext):

    def __init__(self, fd, ref, args, kwargs):
        self.ref = ref
        self.fd = fd
        self.args = args
        self.kwargs = kwargs
        super(FileDescriptor, self).__init__("")

    def fileno(self):
        return self.fd

    def connectionLost(self,reason):
        #self.closeDesciptor()
        pass


@implementer(IReadDescriptor)
class ReadDescriptor(FileDescriptor):
    flag = POLLIN

    def doRead(self):
        self.ref(self.fd, self.flag, *self.args, **self.kwargs)

    def connectionLost(self, reason):
        self.ref(self.fd, select.POLLHUP, *self.args, **self.kwargs)

    def closeDesciptor(self):
        pass


@implementer(IWriteDescriptor)
class WriteDescriptor(FileDescriptor):
    flag = POLLOUT

    def doWrite(self):
        self.ref(self.fd, self.flag, *self.args, **self.kwargs)

    def closeDesciptor(self):
        os.close(self.fd)


class PollManagerImpl:
    def __init__(self, CallbackRef):
        self._inputCallbacks = {}
        self._outputCallbacks = {}
        self._callbacks = set()
        self._timers = set()
        self.active = False
        self.loop = reactor()
        self.CallbackRef = CallbackRef

    def addCallback(self, cb_func, *args, **kwargs):
        ref = self.CallbackRef(cb_func)
        self.loop.callFromThread(ref, *args, **kwargs)
        self._callbacks.add(ref)

    def clearCallbacks(self):
        for ref in self._callbacks:
            ref.kill()
        self._callbacks = set()

    def addTimeout(self, delta, cb_func, *args, **kwargs):
        when = time.time() + delta
        def caller():
            # Execute the callback.
            caller.ref(*args, **kwargs)

        ref = self.CallbackRef(cb_func)
        caller.ref = ref
        return self._addCallLater(when, caller)

    def addRepeatingTimeout(self, delta, cb_func, *args, **kwargs):
        when = time.time() + delta
        def caller():
            # Execute the callback.
            caller.ref(*args, **kwargs)

            # Reschedule.
            now = time.time()
            when = caller.when + delta
            while when <= now:
                when += delta
            ref = self._addCallLater(when, caller)

        ref = self.CallbackRef(cb_func)
        caller.ref = ref
        return self._addCallLater(when, caller)

    def _addCallLater(self, when, func):
        delta = max(0, when - time.time())
        func.delayedCall = self.loop.callLater(delta, func)
        func.when = when
        func.ref.delayedCall = func.delayedCall
        func.delayedCall.cs_func = weakref.ref(func)
        return func.ref

    def removeTimeout(self, ref):
        ref.kill()
        try:
            ref.delayedCall.cancel()
        except AlreadyCalled:
            pass # Not an error for the PollManager.

    def addFileCallback(self, fileOrFd, eventTypes, cb_func, *args, **kwargs):
        ref = self.CallbackRef(cb_func)
        h = normaliseFileOrFd(fileOrFd)
        if h < 0:
            return -1
        if POLLIN & eventTypes:
            desc = ReadDescriptor(h, ref, args, kwargs)
            uid =  self.loop.addReader(desc)
            self._inputCallbacks[h] = desc
        elif POLLOUT & eventTypes:
            desc = WriteDescriptor(h, ref, args, kwargs)
            uid =  self.loop.addWriter(desc)
            self._outputCallbacks[h] = desc
        if uid is None:
            uid = -1
        return uid

    def addInputCallback(self, fileOrFd, cb_func, *args, **kwargs):
        return self.addFileCallback(fileOrFd, POLLIN, cb_func, *args, **kwargs)

    def addOutputCallback(self, fileOrFd, cb_func, *args, **kwargs):
        return self.addFileCallback(fileOrFd, POLLOUT, cb_func, *args, **kwargs)

    def removeFileCallback(self, fileOrFd, eventTypes=POLLIN|POLLOUT|POLLERR):
        h = normaliseFileOrFd(fileOrFd)
        desc = self._inputCallbacks.pop(h, None)
        if desc is None:
            desc = self._outputCallbacks.pop(h, None)
        if desc is not None:
            if desc.flag is POLLIN:
                ret = self.loop.removeReader(desc)
            else:
                ret = self.loop.removeWriter(desc)

    def removeInputCallback(self, fileOrFd):
        return self.removeFileCallback(fileOrFd, eventTypes=POLLIN)

    def removeOutputCallback(self, fileOrFd):
        return self.removeFileCallback(fileOrFd, eventTypes=POLLOUT)

    def run(self, cleanOnQuit=False):
        self.active = True
        self.loop.run()

    def quit(self):
        # TODO: This version can cause immediate exit for 'run'
        timers = self.loop.getDelayedCalls()
        self.loop.stop()
        self.active = False

        # The twisted reactor classes do not allow restarting. So create a new
        # one and copy active timers to it.
        self.loop = reactor()
        for delayedCall in timers:
            func = delayedCall.cs_func()
            now = time.time()
            when = func.when
            self._addCallLater(when, func)

        # Also copy active file handlers.
        for h, desc in self._inputCallbacks.items():
            self.loop.addReader(desc)
        for h, desc in self._outputCallbacks.items():
            self.loop.addWriter(desc)
