#!/usr/bin/env python
"""Various utilities that are useful in logging.

<+Detailed multiline documentation+>
"""
__docformat__ = "restructuredtext"

import time
import sys

from cleversheep3.Prog import Files


def openFullPublicLog(path, mode="w"):
    """Open log file that is totally public.

    """
    f = open(path, mode)
    Files.chmod(path, "a+rw")
    return f

class HangStream:
    r"""Wraps an output stream to provide hanging prefixes.

    You can use this to wrap a file like object. Blocks of text are reformatted
    to have a hanging prefix, such as a time stamp. For example::

        10:30:22 Started
        10:30:24 This is a long,
                 multi-line
                 message
        10:30:59 Finished.

    You can use this like a normal stream. It tracks new lines so the following
    code will produce outlike like the above example:<py>:

        hs.write("Start")
        hs.write("ed\n")
        hs.write("This is a long,\nmulti-line\nmessage\n")
        hs.write("Finished\n")

    """
    def __init__(self, f=sys.stdout, getPrefix=lambda: ""):
        self.f = f
        self._newLine = True
        self._getPrefix = getPrefix
        self._prefix = self._getPrefix()

    def write(self, s):
        return self.writelines(s.splitlines(1))

    def writelines(self, lines):
        if not lines: #pragma: needs testing
            return

        prefix = ""
        if self._newLine: #pragma: needs testing
            self._prefix = prefix = self._getPrefix()
        for line in lines:
            self.f.write("%s%s" % (prefix, line))
            prefix = " " * len(self._prefix)

        if lines[-1][-1] == "\n":
            self._newLine = True
        else: #pragma: needs testing
            self._newLine = False

    def flush(self):
        if self.f:
            self.f.flush()
