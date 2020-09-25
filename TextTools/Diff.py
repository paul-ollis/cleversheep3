"""Extended differencing tools.

"""


import difflib


class DiffContext:
    """Wrapper to supply lines involved in a diff with some context.

    """
    def __init__(self, lines, a, b, context=2):
        """Constructor:

        :Parameters:
          lines
            The full set of lines in the source.
          a, b
            The range of the lines that have been identified as different.
          context
            How many lines of context to provide before and after the lines in
            the range ``(a, b)``.

        """
        self.lines = lines
        self.a = a
        self.b = b
        self.context = context

    def __iter__(self):
        def it():
            c = self.context
            for i in range(self.a - c, self.b + c):
                if i < 0:
                    continue
                try:
                    l = self.lines[i]
                except IndexError:
                    continue
                if self.a <= i < self.b:
                    yield 1, i, l
                else:
                    yield 0, i, l

        return it()


def diffTwoLines(sa, sb):
    m = difflib.SequenceMatcher(None, sa, sb)
    ma = ""
    mb = ""
    for op, a, b, c, d in m.get_opcodes():
        if op == "equal":
            ma += " " * (b - a)
            mb += " " * (d - c)
        elif op == "insert":
            mb += "^" * (d - c)
        elif op == "delete":
            ma += "^" * (b - a)
        elif op == "replace":
            ma += "^" * (b - a)
            mb += "^" * (d - c)
    return ma, mb


def diffTextIter(lhs, rhs, ignoreTrailingSpace=True, context=2,
        lineWrapper=None):
    lineWrapper = lineWrapper or (lambda l: l)
    lines_a = [lineWrapper(el) for el in lhs]
    lines_b = [lineWrapper(el) for el in rhs]

    m = difflib.SequenceMatcher(None, lines_a, lines_b)
    for op, a, b, c, d in m.get_opcodes():
        if op == "equal":
            continue
        aa  = DiffContext(lines_a, a, b, context=context)
        bb  = DiffContext(lines_b, c, d, context=context)
        before = []
        after = []

        if op == "replace":
            if b - a == d - c:
                # Try a line-by-comparison
                for x, i, l in aa:
                    ma = mb = marks = ""
                    if x:
                        lhl = lines_a[i]
                        lhr = lines_b[i - a + c]
                        ma, mb = diffTwoLines(lhl, lhr)
                    before.append((i, " >"[x], l, ma.rstrip()))

                for x, i, l in bb:
                    ma = mb = marks = ""
                    if x:
                        lhl = lines_a[i - c + a]
                        lhr = lines_b[i]
                        ma, mb = diffTwoLines(lhl, lhr)
                    after.append((i, " >"[x], l, mb.rstrip()))
            else:
                # Just treat as delete then add.
                for x, i, l in aa:
                    if x:
                        before.append((i, "-", l, ""))
                    else:
                        before.append((i, " ", l, ""))
                for x, i, l in bb:
                    if x:
                        after.append((i, "+", l, ""))
                    else:
                        after.append((i, " ", l, ""))

            yield before, after

        elif op in ("delete", "insert"):
            for x, i, l in aa:
                before.append((i, " -"[x], l, ""))
            for x, i, l in bb:
                after.append((i, " +"[x], l, ""))
            yield before, after
