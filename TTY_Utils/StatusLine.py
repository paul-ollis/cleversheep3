import sys
import time

from cleversheep3.TTY_Utils import RichTerm, registerForWinch


class Status:
    """A fairly general purpose status line for a simple terminal.

    """
    def __init__(self, startActive=True):
        self.setTerm(RichTerm.RichTerminal(sys.stdout))
        self.spinner = None
        self.prevLine = None
        self.leftFields = []
        self.leftFieldsByName = {}
        self.rightFields = []
        self.rightFieldsByName = {}
        self.prevTime = time.time()
        self.updateInterval = 0.1
        self.killed = True
        self.active = startActive
        registerForWinch(lambda: self.onWinch())

    def onWinch(self):
        h, self.w = self.term.getDims(force=1)

    def setTerm(self, term):
        self.term = term
        h, self.w = self.term.getDims()

    def stop(self):
        self.kill()
        self.active = False

    def start(self):
        self.active = True

    def addLeftField(self, name, w):
        if name not in self.leftFieldsByName:
            self.leftFieldsByName[name] = len(self.leftFields)
            self.leftFields.append((w, ""))
    addField = addLeftField

    def addRightField(self, name, w):
        if name not in self.rightFieldsByName:
            self.rightFieldsByName[name] = len(self.rightFields)
            self.rightFields.append((w, ""))

    def setField(self, name, text):
        if text:
            text = text.splitlines()[0]
        try:
            idx = self.leftFieldsByName[name]
            w, _ = self.leftFields[idx]
            self.leftFields[idx] = w, text
        except KeyError:
            idx = self.rightFieldsByName[name]
            w, _ = self.rightFields[idx]
            self.rightFields[idx] = w, text
        self.update()

    def addSpinner(self, seq=r'\|/-'):
        def chars():
            while True:
                for c in seq:
                    yield c

        def s():
            cc = chars()
            c = next(cc)
            t = time.time()
            while True:
                if time.time() - t > 0.1:
                    t = time.time()
                    c = next(cc)
                yield c
        self.spinner = s()

    def buildLine(self):
        ww = self.w - 2
        rline = ""
        lline = ""
        for w, text in self.rightFields:
            bar = ""
            if rline:
                bar = "|"
            rline = "%-*.*s%s%s" % (w, w, text, bar, rline)

        lline = ""
        if self.spinner:
            lline += "%s " % next(self.spinner)
        for w, text in self.leftFields:
            if lline:
                lline += "|"
            if w is not None:
                lline += "%-*.*s" % (w, w, text)
            else:
                lline += "%s" % (text,)

        l = len(lline) + len(rline)
        if l > ww:
            rline = rline.rstrip()
            l = len(lline) + len(rline)
        if l > ww:
            lline = lline.rstrip()
            l = len(lline) + len(rline)
        while len(lline) > len(rline) and l > ww:
            lline = lline[:-1]
            l = len(lline) + len(rline)
        while len(rline) > len(lline) and l > ww:
            rline = rline[1:]
            l = len(lline) + len(rline)
        while l > ww:
            lline = lline[:-1]
            rline = rline[1:]
            l = len(lline) + len(rline)

        if lline and rline:
            pad = " " * (ww - len(lline) - len(rline) - 1)
            line = "%s%s|%s" % (lline, pad, rline)
        elif rline:
            pad = " " * (ww - len(lline) - len(rline))
            line = "%s%s%s" % (lline, pad, rline)
        else:
            line = lline

        return line

    def update(self, force=False):
        if not (self.active and self.term.isatty()):
            return
        if not force and time.time() - self.prevTime < self.updateInterval:
            return
        self.prevTime = time.time()
        self.line = self.buildLine()
        if self.line != self.prevLine:
            self.term.write("\r%s" % self.line)
            self.term.flush()
            self.prevLine = self.line
            self.killed = False

    def kill(self):
        if not (self.active and self.term.isatty()):
            return
        if self.killed:
            return
        self.term.write("\r%s\r" % (" " * (self.w - 1)))
        self.term.flush()
        self.prevLine = None
        self.killed = True
