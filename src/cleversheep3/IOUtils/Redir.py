#!/usr/bin/env python
"""Utilities to help with common (and not so common) redirection tasks.

<+Detailed multiline documentation+>
"""
__docformat__ = "restructuredtext"


class BitSink:
    """A python version of ``/dev/null``.

    Useful when you want to have a file, but simply junk the output.
    """
    def write(self, *args):
        pass

    def writelines(self, *args):
        pass

    def flush(self, *args):
        pass

    def close(self, *args):
        pass

    def isatty(self, *args):
        return False

