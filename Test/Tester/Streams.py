#!/usr/bin/env python
"""Tester output streams.

The various streams that are used to log progress, etc.
"""
__docformat__ = "restructuredtext"

import sys

from cleversheep3.TTY_Utils import Colours


#: An output stream reserved for the Tester module. This is normally tied to the
#: console, but is sometimes duplicated to the log. This is the one stream that
#: does not necessarily go to the log file.
testerOut = sys.stdout


def _getStdout():
    return testerOut


sTestSummary = Colours.ColourStream(_getStdout, fg="magenta")
sFail = Colours.ColourStream(_getStdout, fg="red", bold=True)
sError = Colours.ColourStream(_getStdout, fg="yellow", bg="red")
sTitle = Colours.ColourStream(_getStdout, bold=True)
sNormal = Colours.ColourStream(_getStdout)
sFile = Colours.ColourStream(_getStdout, fg="blue", bold=True)
sLineNum = Colours.ColourStream(_getStdout, bold=True)
sFunc = Colours.ColourStream(_getStdout)
sCode = Colours.ColourStream(_getStdout, fg="magenta")
sEmphCode = Colours.ColourStream(_getStdout, fg="magenta", bold=True)
sPass = Colours.ColourStream(_getStdout, bold=True)
sEmph = Colours.ColourStream(_getStdout, fg="blue")
