#!/usr/bin/env python
"""Support for writing indented text.

This module provides one main class `IndentStream`, which behaves like a ``file``
object, but will indent all lines.
"""
__docformat__ = "restructuredtext"


import textwrap

maxIndent = None

class _Writer: #pragma: unsupported
    def __init__(self, f, indSize):
        self.f = f
        self.needIndent = 1
        self.doneEol = 0
        self.charCount = 0
        self.indSize = indSize

    def write(self, ind, s, prefix=""):
        lines = s.splitlines(1)
        for i, line in enumerate(lines):
            if self.needIndent:
                pad = " " * (ind * self.indSize)
                self.f.write(pad)
                if prefix:
                    self.f.write(prefix)
                    self.charCount += len(prefix)
                self.needIndent = 0
            self.f.write(line)
            self.charCount += len(line)

            if line.endswith("\n"):
                self.needIndent = 1
                self.doneEol = 1
                self.charCount = 0
            else:
                self.doneEol = 0

    def pad(self, ind, text, char):
        l = 79 - (ind * self.indSize + len(text) + self.charCount)
        if l > 0:
            self.write(ind, char * l)

    def wrap(self, ind, text, rhs=0):
        """Wrap text within the available width."""
        l = 79 - ind * self.indSize - rhs
        return textwrap.wrap(text, l)

    def newline(self):
        if not self.needIndent:
            self.f.write("\n")
            self.needIndent = 1

    def __getattr__(self, name):
        return getattr(self.f, name)


class Indent: #pragma: unsupported
    def __init__(self, f, prefix="", indSize=2):
        self.prefix = prefix
        self.indSize = indSize
        if isinstance(f, Indent):
            self.ind = f.ind + 1
            self.f = f.f
            self.parent = f
        else:
            self.ind = 0
            self.f = _Writer(f, self.indSize)
            self.parent = f
        self.needIndent = 1

    def setInd(self, ind):
        self.ind = ind

    def getPadlen(self):
        return self.indSize * self.ind

    def getPadding(self):
        return " " * (self.ind * self.indSize)

    def wrap(self, text, rhs=0):
        """Wrap text within the available width."""
        return self.f.wrap(self.ind, text, rhs=rhs)

    def pad(self, text, char="."):
        self.f.pad(self.ind, text, char)

    def write(self, s):
        if maxIndent is not None and self.ind > maxIndent:
            return
        self.f.write(self.ind, s, prefix=self.prefix)

    def __getattr__(self, name):
        return getattr(self.f, name)

    def __del__(self):
        if hasattr(self.f, "newline"):
            self.f.newline()


class IndentStream:
    """A file like stream than indents the output.

    This should be used in preference to the older ``Indent`` class.

    """
    def __init__(self, f, ind=0):
        """Constructor:

        :Param f:
            The underlying file like object.
        :Param ind:
            The number of spaces to put before each line.

        """
        if isinstance(f, IndentStream):
            self.f = f.f
            self._ind = f._ind + ind
        else:
            self.f = f
            self._ind = ind
        self._atEol = False

    def write(self, s):
        """The equivalend of ``file.write``.

        However, this splits the string into lines and applies the indent to
        each line.
        """
        ind = " " * self._ind
        l = None
        for l in s.splitlines(True):
            if not self._atEol:
                self.f.write(ind)
            self.f.write(l)
            self._atEol = False
        self._atEol = l and l[-1] != "\n"

    def indent(self, n):
        """Increase the indent.

        This is used to increase or redue the level of indentation. The
        indentatin cannot be reduced to a negative number using this method.

        :Param n:
            The number of spaces by which to increase the indentation level.
            Anegative number can be used to reduce the level.
        """
        self._ind = max(0, self._ind + n)

    def getvalue(self):
        """Returns the text representation of the underlying file's contents.

        This will only work of the underlying file like object provides a
        ``getvalue`` method.

        """
        lines = [l.rstrip() for l in self.f.getvalue().splitlines()]
        return "\n".join(lines)


if __name__ == "__main__": #pragma: debug
    import sys

    def a(f):
        f = Indent(f)
        f.write("Hello\n")
        b(f)
        f.write("Paul\n")

    def b(f):
        f = Indent(f)
        f.write("There")

    a(sys.stdout)

