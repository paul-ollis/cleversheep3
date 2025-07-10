"""Async I/O wrapped around Tornado.

"""
__docformat__ = "restructuredtext"

import functools
import select
import time

from tornado import ioloop

from cleversheep3.Test import normaliseFileOrFd


POLLIN = ioloop.IOLoop.READ
POLLOUT = ioloop.IOLoop.WRITE
POLLERR = ioloop.IOLoop.ERROR
POLLHUP = select.POLLHUP
POLLNVAL = select.POLLNVAL


class PollManagerImpl:
    def __init__(self, CallbackRef):
        self._repeaters = {}
        self._callbacks = set()
        self.active = False
        self.loop = ioloop.IOLoop()
        self.CallbackRef = CallbackRef

    def addCallback(self, cb_func, *args, **kwargs):
        ref = self.CallbackRef(cb_func)
        self.loop.add_callback(functools.partial(ref, *args, **kwargs))
        self._callbacks.add(ref)

    def clearCallbacks(self):
        for ref in self._callbacks:
            ref.kill()
        self._callbacks = set()

    def addTimeout(self, delta, cb_func, *args, **kwargs):
        now = time.time()
        tid =  self.loop.add_timeout(now + delta, functools.partial(
                        self.CallbackRef(cb_func), *args, **kwargs))
        return tid

    def addRepeatingTimeout(self, delta, cb_func, *args, **kwargs):
        def caller():
            # Execute the callback.
            ref(*args, **kwargs)

            # Possibly reschedule.
            if uid in self._repeaters:
                now = time.time()
                tid, when, delta = self._repeaters[uid]
                while when < now:
                    when += delta
                tid =  self.loop.add_timeout(when, caller)
                self._repeaters[uid] = tid, when, delta

        ref = self.CallbackRef(cb_func)
        when = time.time() + delta
        uid =  self.loop.add_timeout(when, caller)
        self._repeaters[uid] = uid, when, delta
        return uid

    def removeTimeout(self, uid):
        a = uid.callback
        if uid in self._repeaters:
            tid, when , delta = self._repeaters[uid]
            self.loop.remove_timeout(tid)
            self._repeaters.pop(uid)
        else:
            self.loop.remove_timeout(uid)

    def addFileCallback(self, fileOrFd, eventTypes, cb_func, *args, **kwargs):
        def caller(fd, ev):
            ret = ref(fd, ev, *args, **kwargs)
            if ev in (POLLERR, POLLHUP, POLLNVAL):
                self.loop.remove_handler(fileOrFd)
            return ret

        ref = self.CallbackRef(cb_func)
        h = normaliseFileOrFd(fileOrFd)
        if h < 0:
            return -1
        uid =  self.loop.add_handler(h, caller, eventTypes)
        if uid is None:
            uid = -1
        return uid

    def addInputCallback(self, fileOrFd, cb_func, *args, **kwargs):
        return self.addFileCallback(fileOrFd, POLLIN, cb_func, *args, **kwargs)

    def addOutputCallback(self, fileOrFd, cb_func, *args, **kwargs):
        return self.addFileCallback(fileOrFd, POLLOUT, cb_func, *args, **kwargs)

    def removeFileCallback(self, fileOrFd, eventTypes=POLLIN|POLLOUT|POLLERR):
        ret = self.loop.remove_handler(fileOrFd)
        return ret

    def removeInputCallback(self, fileOrFd):
        return self.removeFileCallback(fileOrFd, eventTypes=POLLIN)

    def removeOutputCallback(self, fileOrFd):
        return self.removeFileCallback(fileOrFd, eventTypes=POLLOUT)

    def run(self, cleanOnQuit=False):
        self.active = True
        self.loop.start()

    def quit(self):
        # TODO: This version can cause immediate exit for 'run'
        self.loop.stop()
        self.active = False
