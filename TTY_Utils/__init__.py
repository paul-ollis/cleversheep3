#!/usr/bin/env python
"""Various terminal utilities.

This package contains modules that support various terminal operations. The modules
include:

    - `Colours`

"""
__docformat__ = "restructuredtext"

import signal

_winchers = {}


def onWinch(sig, frame):
    toDel = []
    for wincher in _winchers:
        try:
            wincher()
        except Exception as exc:
            toDel.append(wincher)
    for wincher in toDel:
        del _winchers[wincher]


def registerForWinch(func):
    _winchers[func] = func


signal.signal(signal.SIGWINCH, onWinch)
