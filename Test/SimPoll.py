#!/usr/bin/env python
"""A module to simulate ``select.poll`` functionality.

Because Windows does not provide ``poll``, but I prefer the interface.
This greatly simplifies the `PollManager` code.

This only supports POLLIN and POLLOUT because POLLPRI is only available
on platforms that provide a 'poll' system call. However, those are all that
generally required.

"""
__docformat__ = "restructuredtext"

import select
import time

# These are the values I get from ``select`` under LINUX.
POLLIN = 1
POLLOUT = 4

class poll:
    """Replacement for ``select.poll``.

    This class is intended to provide a compatable API, so in general
    you should look at the standard docs. The only real difference is that
    this only supports POLLIN and POLLOUT.
    """
    def __init__(self):
        self._inFiles = {}
        self._outFiles = {}

    def register(self, fd, eventmask = POLLIN | POLLOUT):
        """Register (or reregister) a file to be monitored."""
        for fds, bit in ((self._inFiles, POLLIN), (self._outFiles, POLLOUT)):
            if eventmask & bit:
                fds[fd] = None
            else:
                fds.pop(fd, None)

    def unregister(self, fd):
        """Unregister a file that was being monitored.

        Unlike ``select.poll``, this will not raise key error if the
        ``fd`` is not known.
        """
        for fds in (self._inFiles, self._outFiles):
            fds.pop(fd, None)

    def poll(self, timeout=None):
        """Wait for file activity or a timeout."""
        if timeout is not None:
            if timeout < 0:
                timeout = None

        if timeout is not None:
            secondsTimeout = timeout / 1000.0
        else:
            secondsTimeout = None
        if self._inFiles or self._outFiles:
            activeIn, activeOut, x = select.select(
                    self._inFiles, self._outFiles, [], secondsTimeout)
            ret = []
            for fds, bit in ((activeIn, POLLIN), (activeOut, POLLOUT)):
                for f in fds:
                    ret.append((f, bit))
            return ret

        time.sleep(secondsTimeout)
        return []

