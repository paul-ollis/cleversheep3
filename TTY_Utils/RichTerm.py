#!/usr/bin/env python
"""A rich features terminal layer.

<+Detailed multiline documentation+>
"""
from __future__ import print_function
__docformat__ = "restructuredtext"

import six

import sys
import os
import subprocess

import cleversheep3
from cleversheep3.Sys import Platform


# Under windows we need pyreadline to be able to support pretty console output.
# So we try to import it, but handle failure gracefully.
try:
    from pyreadline import console
except ImportError:
    console = None


def _tostr(s):
    return getattr(s, 'decode', lambda x: s)('latin-1')


def _tobytes(s):
    return getattr(s, 'encode', lambda x: s)('latin-1')


def getoutput(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        return ""


if console is None:
    # We have no pyreadline, so we will try to use UNIX style facilities.

    def getTerminalSize():
        """Try to get the terminal dimensions, using the ``stty`` command.

        This is used Unix type platforms. On most moderm platforms of this type
        you can query the TTY settings using ``stty``. This is slightly crude,
        but easily portable.

        Note that the environment variables``$COLUMNS`` and ``$ROWS`` are use
        in preference if set and sane; both > 2.

        :Return:
            The terminal dimensions as a tuple of ``(rows, columns)``. If the
            dimensions cannot be determined then a default of ``(24, 80)`` is
            returned.
        """
        # First try ``$COLUMNS`` and ``$ROWS``.
        rows, columns = -1, -1
        d = {}
        for v, e in (("e_rows", "ROWS"), ("e_columns", "COLUMNS")):
            try:
                exec(
                    "%s = int(os.environ.get('%s', 0))" % (v, e), globals(), d)
            except ValueError:
                exec("%s = -1" % (v), globals(), d)
        try:
            text = getoutput("stty size")
            rows, columns = [int(s) for s in text.split()]
        except ValueError as exc: #pragma: unreachable
            rows, columns = 24, 80

        if d['e_rows'] > 2:
            rows = d['e_rows']
        if d['e_columns'] > 2:
            columns = d['e_columns']
        if rows <= 0 or columns <= 0: #pragma: unreachable
            rows, columns = 24, 80
        return rows, columns


class MetaRichTerminal(type):
    """Meta-class for the Rich Terminal.

    This exists to tweak the creation of the `RichTerminal` class according to
    the execution platform and available support packages/modules.
    """
    if console is not None: #pragma: unless sys.platform.startswith("linux")
        # When the pyreadline package is available we can provide pretty
        # rich support under Windows.
        _console = console.Console()

        def initConsole(self):
            self.cons = MetaRichTerminal._console

        def write(self, s):
            self.cons.write_color(s)

        def setStyle(self, **kwargs):
            s = colourSeq(**kwargs)
            self.cons.write_color(s)

        def resetStyle(self):
            pass

        def getDims(self):
            """Get the Windows console dims.

            We cannot simple do ``return self.cons.size()`` because that returns
            the number of buffer lines, not the visible terminal size; hoh hum.
            """
            info = console.CONSOLE_SCREEN_BUFFER_INFO()
            status = self.cons.GetConsoleScreenBufferInfo(self.cons.hout,
                    console.byref(info))
            if not status:
                if self._columns is not None:
                    return 24, self._columns
                else:
                    return 24, 80
            wmin = info.srWindow.Right - info.srWindow.Left + 1
            hmin = info.srWindow.Bottom - info.srWindow.Top + 1
            if self._columns is not None:
                wmin = self._columns
            return hmin, wmin

        def getDims(self):
            return self.cons.size()

        def up(self, n=1):
            x, y = self.cons.pos()
            y -= 1
            self.cons.pos(x, y)

        def right(self, *args):
            x, y = self.cons.pos()
            x += 1
            self.cons.pos(x, y)

    else:
        def initConsole(self):
            pass

        def up(self, n=1):
            if self.realTerm.isatty():
                s = tigetstr("cuu1")
                self.realTerm.write(s * n)

        def right(self, n=1):
            if self.realTerm.isatty():
                s = tigetstr("cuf1")
                self.realTerm.write(s * n)

        def getDims(self, force=False):
            if force or self._columns is None:
                self._rows, self._columns = getTerminalSize()
            return self._rows, self._columns

        def setStyle(self, **kwargs):
            if self.realTerm.isatty():
                s = colourSeq(**kwargs)
                self.realTerm.write(s)

        def resetStyle(self):
            if self.realTerm.isatty():
                s = cap["end"]
                self.realTerm.write(s)

    def __new__(klass, klassName, bases, klassDict):
        for attrName in ("initConsole", "write", "getDims",
                "setStyle", "resetStyle", "up", "right"):
            attr = getattr(MetaRichTerminal, attrName, None)
            if attr is not None:
                klassDict[attrName] = six.get_unbound_function(attr)
        return type.__new__(klass, klassName, bases, klassDict)


class RichTerminal(metaclass=MetaRichTerminal):
    """Provides a thin, but rich wrapper around sys.stdout/sys.stderr.

    This is intended to be used something like this::

        sys.stdout == RichTerminal(sys.stdout)
        sys.stderr == RichTerminal(sys.stderr)

    The resulting stdout/stderr behave pretty much as normal, but with extra
    features. These include:

        - Ability to query the terminal size.
        - A better chance of having colour support (for example in a Windows
          console).

    """
    def __init__(self, realTerm):
        """Constructor:

        :Param stream:
            The file for the real, underlying console/tty.

        """
        self.realTerm = realTerm
        self.initConsole()
        self._columns, self._rows = None, None

    def sol(self):
        if self.realTerm.isatty():
            self.realTerm.write("\r")

    def nl(self, count=1):
        if self.realTerm.isatty():
            self.realTerm.write("\n" * count)

    def set_width(self, columns):
        self._columns = columns

    @property
    def columns(self):
        h, w = self.getDims()
        return w

    @property
    def lines(self):
        h, w = self.getDims()
        return h

    def __getattr__(self, attr):
        return getattr(self.realTerm, attr)


class NullCurses:
    """A null-effect curses look-alike.

    This class provides just enough functionality for an instance to be used
    in place of the standard ``curses`` module in situations where ``curses`` is
    not available; such as under Windows. By "just enough functionality", I
    mean it does all the things that are required to support other parts of
    `cleversheep3`.

    """
    def tigetstr(self, a):
        return bytes()
    def setupterm(self):
        return bytes()
    def tparm(self, cap, code):
        return bytes()


if console is not None: #pragma: unless sys.platform.startswith("linux")
    #: This set of sequences is good enough to provide some minimal colour,
    #: bold, etc. support under Windows, provided we have pyreadline available.
    _ttySequences = {
        "dim":    '',
        "setab":  '\x1b[4%dm',
        "smso":   '\x1b[7m',
        "bold":   '\x1b[1m',
        "sgr0":   '\x1b[0m',
        "rev":    '\x1b[7m',
        "blink":  '\x1b[5m',
        "setaf":  '\x1b[3%dm',
        "sitm":   '',
        "smul":   '\x1b[4m',
        "colors": '',
        "cuu1":   '',
        "cuf1":   '',
    }
    class SimCurses(NullCurses):
        """A simple class that simulates part of the Python curses API.

        An instance of this class is good enough (for our purposes) of acting
        as a replacement of the Python curses module.
        """
        def tigetstr(self, a):
            return _tobytes(_ttySequences.get(a, ""))
        def tparm(self, cap, code):
            return _tobytes(cap % code)

else:
    SimCurses = NullCurses


# Once we have all the support classes and functions defined we try to import
# the curses module. If that fails then we use a SimCurses instance in its
# place.
try:
    import curses
except ImportError: #pragma: unless sys.platform.startswith("linux")
    curses = SimCurses()

_querySet = ( #pragma: unreachable
    ("fg", "setaf"),
    ("bg", "setab"),
    ("bold", "bold"),
    ("blink", "blink"),
    ("rev", "rev"),
    ("uline", "smul"),
    ("max_colors", "colors"),
    ("end", "sgr0"),
    ("cuu1", "cuu1"),
    ("cuf1", "cuf1"),
)


def _getTermCap():
    """This queries the terminal capabilities using the curses module.

    :Returns:
        A dictionary mapping capability names to the terminfo strings.
    """
    cap = {}
    for name, terminfoName in _querySet:
        cap[name] = ""
    try:
        saved, sys.stdout = sys.stdout, sys.__stdout__
        try:
            curses.setupterm()
        finally:
            sys.stdout = saved
    except TypeError:
        # Happens when using epydoc
        return cap

    for name, terminfoName in _querySet:
        cap[name] = _tostr(curses.tigetstr(terminfoName) or "")

    if 0: #pragma: no cover
        for c in cap:
            print("%-8s: %r" % (c, cap[c]))

    return cap


def tigetstr(cap):
    return _tostr(curses.tigetstr(cap))


def tparm(cap, code):
    return _tostr(curses.tparm(_tobytes(cap), code))


# Initialise the various lookup tables.
try:
    cap = _getTermCap()
except curses.error:
    # This can happen if, for example, the terminfo database is not available
    # or the terminal is of an unknown type. We simply fall back to the
    # non-functional curses simulation class.
    curses = SimCurses()
    cap = _getTermCap()


colourNames = ( #pragma: unreachable
        "black", "red", "green", "yellow",
        "blue", "magenta", "cyan", "white")
colourCode = dict([(n, i) for i, n in enumerate(colourNames)])


def colourSeq(**kwargs):
    """Return the escape sequence for colour/attributes."""
    fgs, bgs = cap["fg"], cap["bg"]
    fg = kwargs.pop("fg", None)
    bg = kwargs.pop("bg", None)

    s = ""
    if fg is not None and fgs:
        s += tparm(fgs, colourCode[fg])
    if bg is not None and bgs:
        s += tparm(bgs, colourCode[bg])
    for kw in kwargs:
        if kwargs[kw] and kw in cap:
            s += cap[kw]

    return s


init = False

def wrapStdxxx(columns=None):
    """Wrap sys.stdout and sys.stderr as rich terminals."""
    sys.stdout = RichTerminal(sys.__stdout__)
    sys.stderr = RichTerminal(sys.__stderr__)
    global init
    if not init:
        sys.stdout = RichTerminal(sys.stdout)
        sys.stderr = RichTerminal(sys.stderr)
        init = True
    if columns is not None:
        sys.stdout.set_width(columns)
        sys.stderr.set_width(columns)


if __name__ == "__main__": #pragma: debug
    # Just some ad-hoc testing.
    wrapStdxxx()
    out = sys.stdout
    out.setStyle(fg="blue")
    print("Running in a %dx%d terminal" % out.getDims())
    out.setStyle(blink=True)
    print("Flash")
    out.resetStyle()
    print("Bye")
