"""Command line support for the Tester framework.

"""

import re
import sys

from cleversheep3.Test.Tester import options


class _TestRangeSet:
    def __init__(self):
        self.all_ranges = []

    def add(self, lower, upper):
        self.all_ranges.append((lower, upper))

    def testNumbers(self):
        for rng in self.all_ranges:
            for n in range(*rng):
                yield n

    def __contains__(self, v):
        for a, b in self.all_ranges:
            if a <= v < b:
                return True

    def __bool__(self):
        return bool(self.all_ranges)

    def __str__(self):
        return str(self.all_ranges)


class _TestChooser:
    def __init__(self):
        self.ranges = _TestRangeSet()
        self.summaryText = []
        self.descriptionText = []
        self.summaryPatterns = []
        self.descriptionPatterns = []
        self.uids = []
        self.modules = []

    def addUid(self, uid):
        self.uids.append(uid)

    def addModule(self, module):
        self.modules.append(module)

    def addRange(self, lower, upper):
        self.ranges.add(lower, upper)

    def testNumbers(self):
        return self.ranges.testNumbers()

    def matches(self, test):
        def ms(s):
            if options.ignore_case:
                return s.lower()
            return s

        if not self.hasSelections():
            return True
        if test.number in self.ranges:
            return True
        for s in self.summaryText:
            if s in ms(test.summary):
                return True
            if test.testID is not None:
                if s in ms(test.testID):
                    return True
        for s in self.descriptionText:
            if s in ms(test.doc):
                return True
        for s in self.summaryPatterns:
            if s.search(test.summary):
                return True
        for s in self.descriptionPatterns:
            if s.search(test.doc):
                return True
        for uid in self.uids:
            if test.testID == uid:
                return True
        for module in self.modules:
            (d, m), c, f = test.uid
            if module in m:
                return True

    def addPattern(self, text):
        """Adds a test match pattern.

        The syntax of a pattern is::

          [<T>:][~]<text>

        Where T can be any of:

          - ``s`` To just check the test's summary.
          - ``d`` To  check the test's entire description.

        Omitting ``<T>`` is the same as using ``s``.

        If the tilde character is present then ``<text>`` is treated as a
        regular expression.

        """
        def ms(s):
            if options.ignore_case:
                return s.lower()
            return s

        flags = 0
        if options.ignore_case:
            flags = re.I
        t = "s"
        isRegExp = False
        if text.startswith("d:"):
            t = "d"
            text = text[2:]
        if text.startswith("s:"):
            text = text[2:]
        if text.startswith("~"):
            text = text[1:]
            isRegExp = True
        if isRegExp:
            try:
                p = re.compile(text, flags)
            except re.error as exc:
                sys.stderr.write("%r is not a valid regular expression\n" % text)
                sys.stderr.write("  %s\n" % exc)
                sys.exit(1)
            if t == "d":
                self.descriptionPatterns.append(p)
            else:
                self.summaryPatterns.append(p)
        else:
            if t == "d":
                self.descriptionText.append(ms(text))
            else:
                self.summaryText.append(ms(text))

    def hasSelections(self):
        return bool(self.ranges or self.summaryText or self.descriptionText
                or self.summaryPatterns or self.descriptionPatterns
                or self.uids or self.modules)


def parseTestSelections(args):
    def _int(s):
        if s == "":
            return ""
        try:
            return int(s)
        except ValueError:
            return None

    chooser = _TestChooser()
    for sel in args:
        a = b = None
        if "-" in sel:
            a, b = [_int(s) for s in sel.split("-", 1)]
        else:
            a, b = _int(sel), ""
        if None in (a, b):
            chooser.addPattern(sel)
            isPattern = True
            continue

        if a == "":
            a = 1
        if b == "":
            if "-" in sel:
                b = a + 1000000
            else:
                b = a
        assert a <= b
        chooser.addRange(a, b+1)

    options.select = chooser
    for uids in options.uids:
        for uid in uids.split(","):
            chooser.addUid(uid)
    for modules in options.modules:
        for module in modules.split(","):
            chooser.addModule(module)
