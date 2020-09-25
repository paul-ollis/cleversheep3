#!/usr/bin/env python
"""Colour support for terminals.

This module provides generalised support for displaying coloured output on
terminals. It uses the curses library to determine the correct codes for
setting colours and other attributes and so is reasonably portable.

This module provides a general function for setting colours and other
atttributes; `colourSeq`.

However, these are not mormally the most convenient way to produce colour
output. More convenient are the `ColourStream` class and the `Xstream.write`
function. These are also more efficient.

:Note:
    The `Xstream` class should be considered unstable. You can use it, but do
    not complain if the API changes.
"""
from __future__ import print_function
__docformat__ = "restructuredtext"

import io
import sys

from cleversheep3.TTY_Utils import RichTerm

try:
    import curses
except ImportError: #pragma: unless sys.platform.startswith("linux")
    # This gets us enough functionality under Windows, if pyreadline is
    # available.
    curses = RichTerm.SimCurses()

_querySet = ( #pragma: untraceable
    ("fg", "setaf"),
    ("bg", "setab"),
    ("standout", "smso"),
    ("bold", "bold"),
    ("blink", "blink"),
    ("dim", "dim"),
    ("rev", "rev"),
    ("uline", "smul"),
    ("italics", "itm"),
    ("max_colors", "colors"),
    ("end", "sgr0"),
)


def _tobytes(s):
    return getattr(s, 'encode', lambda x: s)('latin-1')


def _getTermCap():
    """This queries the terminal capabilities using the curses module.

    @Returns:
        A dictionary mapping capability names to the terminfo
        strings.
    """
    cap = {}
    for name, terminfoName in _querySet:
        cap[name] = ""

    try:
        if not sys.stdout.isatty():
            return cap
    except AttributeError:
        global curses
        curses = RichTerm.SimCurses()

    curses.setupterm()
    for name, terminfoName in _querySet:
        cap[name] = curses.tigetstr(terminfoName) or ""

    if 0: #pragma: debug
        for c in cap:
            print("%-8s: %r" % (c, cap[c]))

    return cap


def _init():
    """Initialise the various lookup tables."""
    global cap, colourNames, colourCode
    cap = _getTermCap()
    colourNames = ( #pragma: untraceable
            "black", "red", "green", "yellow",
            "blue", "magenta", "cyan", "white",
            "c8", "c9")
    colourCode = dict([(n, i) for i, n in enumerate(colourNames)])


_init()


def colourSeq(**kwargs):
    """Return the escape sequence for colour/attributes."""
    fgs, bgs = cap["fg"], cap["bg"]
    fg = kwargs.pop("fg", None)
    bg = kwargs.pop("bg", None)

    s = bytes()
    if fg is not None and fgs:
        s += curses.tparm(fgs, colourCode[fg])
    if bg is not None and bgs:
        s += curses.tparm(bgs, colourCode[bg])
    for kw in kwargs:
        if kwargs[kw] and kw in cap:
            s += _tobytes(cap[kw])

    return s.decode()


class ColourStream:
    """A wrapper for a file, that colours the output.

    You would normally use more than one of these. For example,
    you might have one for errors and one for warnings. Each
    configured to use different colours/attributes, but all using
    the same underlying file stream.
    """
    def __init__(self, f, **kwargs):
        """Constructor:

        Here is where you select the text attributes for output using
        this stream.

        :Note:
            There is a good chance that 'dim' has no effect. The 'standout' and
            'rev' attributes are often the same. The 'blink' attribute is
            generally annoying; use sparingly.

        :Param f:
            The file stream to wrap. Alternatively, this may  be a function
            that returns the stream; in which case it is invoked each time the
            `ColourStream` needs to access the underlying stream.
        :Param kwargs:
            The various colour, bold, etc. selections are made using the
            following keyword arguments.
        :Keyword fg, bg:
            The forground and background colours to use. The valid names are:
            ``black red green yellow blue magenta cyan white``
        :Keyword bold:
            Set to make text bold.
        :Keyword dim:
            Set to make text dim.
        :Keyword rev:
            Set to use reversed text.
        :Keyword standout:
            Set to use standout mode.
        :Keyword uline:
            Set to underline text.
        :Keyword blink:
            Set to make text blink.
        """
        if hasattr(f, "__call__"):
            self.getF = f
        else:
            self.getF = lambda: f
        try:
            self.istty = self.getF().isatty()
        except AttributeError:
            self.istty = 0
        self.start = colourSeq(**kwargs)
        self.end = cap["end"]
        self.scheme = kwargs.copy()

    @property
    def columns(self):
        try:
            return self.getF().columns
        except Exception as exc:
            return 80

    @property
    def terminal(self):
        return self.getF()

    def setScheme(self, **kwargs):
        """Change the colour/attr scheme.

        See `__init__` for details of the arguments.
        """
        self.scheme = kwargs.copy()

    def write(self, s):
        f = self.getF()
        rich = True
        if not hasattr(f, "setStyle"):
            rich = False
        for line in s.splitlines(1):
            if rich:
                f.setStyle(**self.scheme)
            eol = 0
            if line and line[-1] == "\n":
                line = line[:-1]
                eol = 1
            f.write(line)
            if rich: f.resetStyle()
            if eol:
                f.write("\n")
        if rich: f.resetStyle()
        try:
            f.flush()
        except IOError: #pragma: unreachable
            # Sometimes we can get EAGAIN!
            pass

    def writelines(self, lines):
        for l in lines:
            self.write(l)

    def reset(self):
        f = self.getF()
        if hasattr(f, "setStyle"):
            f.resetStyle()


class Xstream:
    def __init__(self, f=None):
        self.f = f or sys.stdout

    def write(self, seq):
        """Write a sequence of strings, using several streams,

        The arguments should be a sequence of strings and streams.
        When a stream is encountered, subsequent strings are written to
        that stream.

        A stream is anything based on `ColourStream` or ``file``.
        """
        f = self.f
        if isinstance(seq, str):
            seq = [seq]
        for arg in seq:
            if isinstance(arg, (io.IOBase, ColourStream)):
                f = arg
                continue
            f.write(arg)

        _coreStream.reset()


# Arrange to switch back to normal mode at exit.
_coreStream = ColourStream(sys.stdout)
def _tidy():
    s = ColourStream(sys.stdout)
    s.write("")

import atexit
atexit.register(_tidy)


def demo(): #pragma: debug
    import sys
    f = RichTerm.RichTerminal(sys.stdout)
    normal = ColourStream(f)
    for bold in (False, True):
        for flag in (False, True):
            for bg in colourNames[:8]:
                normal.write("UL=%-5s Bold=%-5s BG=%-7s: " % (flag, bold, bg))
                for fg in colourNames[:8]:
                    if fg == bg:
                        continue
                    s = ColourStream(f, fg=fg, bg=bg, bold=bold,
                            standout=flag)
                    s.write("%-7s " % fg)
                normal.write("\n")


if __name__ == "__main__": #pragma: debug
    demo()
