#!/usr/bin/env python
"""Various test utilities.

This package contains modules and packages that support various types of
testing. These include:

    - `ImpUtils`
    - `LogTracker`
    - `Mock`
    - `Net`
    - `PollManager`
    - `Tester`
    - `TestEventStore`

"""
__docformat__ = "restructuredtext"


def normaliseFileOrFd(fileOrFd):
    """Convert to a file descriptor.

    :Param fileOrFd:
        This can be a plain old integer FD or an object that provides
        a ``fileno`` method; such as a python ``file``.
    """
    if hasattr(fileOrFd, "fileno"):
        try:
            return fileOrFd.fileno()
        except:
            # This can only happen if the file object is no longer useable.
            # Best response is to return -1.
            return -1
    return fileOrFd
