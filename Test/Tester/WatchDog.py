#!/usr/bin/env python
"""A watchdog for running tests.

<+Detailed multiline documentation+>
"""
__docformat__ = "restructuredtext"

import sys
import time
import signal
import os
import inspect
import threading

from cleversheep3.Test.Tester import Errors


class Timeout(Exception):
    """Raised if a watchdog timeout occurs."""
    def __init__(self, period, stack):
        Exception.__init__(self)
        self.period = period
        self.stack = stack


class WatchDog:
    def __init__(self):
        self.done = False

    def __call__(self, maxTime, func,  *args, **kwargs):
        # If no watchdog is active, just invoke the function.
        if not maxTime:
            return func( *args, **kwargs)

        # Use SIGINT to indicate watchdog expiration. Set up the handler
        # before the watchdog thread is started to be sure that the signal is
        # seen and propgated to this (main) thread.
        def handle(sig, frame):
            stack = inspect.getframeinfo(frame)
            raise Timeout(None, stack)
        saved = signal.signal(signal.SIGINT, handle)

        # Start the watchdog thread.
        self.maxTime = maxTime
        self.watcher = threading.Thread(target=self.watch)
        self.watcher.start()

        try:
            try:
                return func( *args, **kwargs)
            except Timeout as exc:
                (type, value, traceback) = sys.exc_info()
                stack = inspect.getinnerframes(traceback)
                stack = Errors.saveStack(stack, 7)
                raise Timeout(maxTime, stack)
        finally:
            signal.signal(signal.SIGINT, saved)
            self.done = True
            self.watcher.join()

    def watch(self):
        end = time.time() + self.maxTime
        while time.time() < end and not self.done:
            time.sleep(0.02)
        if not self.done:
            os.kill(os.getpid(), signal.SIGINT)


runUnderWatchDog = WatchDog()
