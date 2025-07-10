#!/usr/bin/env python
"""Parsing of DocStrings and other Python documentation.

TODO: Add details.
"""
__docformat__ = "restructuredtext"


import re
from itertools import chain, takewhile, tee

rSpaces = re.compile(r' *')


isNotBlank = lambda s: bool(s and s.strip())
isBlank = lambda s: not isNotBlank(s)


def trimLines(lines):
    """Remove head/tail blanks lines and trailing spaces from lines"""
    lines = [l.rstrip() for l in lines]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def dedentLines(lines):
    """Remove common leading indent from lines.

    :Param lines:
        An iterable, yielding individual lines.
    """
    lines = list(lines)
    ind = None
    for l in lines:
        if not l.strip():
            continue
        m = rSpaces.match(l)
        if m:
            if ind is None:
                ind = 99999999
            ind = min(ind, m.end())
    if ind is not None:
        return [l[ind:] for l in lines]
    return lines


def tidyDocstringLines(lines):
    """Splits a docstring into parts and tides them up.

    :Return:
        A tuple of (summary, body). Each is a list of lines. The summary has
        all lines stripped and the body has dedented lines.
    """
    summary, lines = [], trimLines(lines)
    while lines and lines[0].strip():
        summary.append(lines.pop(0).strip())
    body = dedentLines(trimLines(lines))
    return summary, body


def prevCurrNext(it):
    a, b, c = tee(it, 3)
    group = zip(
            chain([None, None], a),
            chain([None], b, [None]),
            chain(c, [None, None]))
    next(group)
    return group


def paragraphs(lines):
    """Generator: Yields paragraphs from a list of lines.

    Paragraphs are separated by one or more blanks lines. Lines is assumed not
    to have any leading blanks lines.
    """
    para = []
    for p, c, n in prevCurrNext(lines):
        if not isBlank(c):
            para.append(c)
        if isBlank(n) and para:
            yield para
            para = []


def _paramBlocks(lines):
    """Generator: Yields param blocks from a DocString paragaph."""
    def isStart(l):
        return isBlank(l) or l.lower().startswith(":param ")

    block = []
    for p, c, n in prevCurrNext(lines):
        if not isBlank(c):
            block.append(c)
        if isStart(n) and block:
            yield block
            block = []


class Param:
    def __init__(self, lines):
        param, body = lines[0], lines[1:]
        a, param = param.split(None, 1)
        self.names = param.replace(":", "").strip().split(",")
        self.body = dedentLines(body)


class DocString:
    def __init__(self, lines):
        self.summary, fullBody = tidyDocstringLines(lines)
        self.body = body = []
        self.paramDescriptions = []
        for para in paragraphs(fullBody):
            if not para[0].lower().startswith(":param "):
                if body:
                    body.append("")
                body.extend(para)
                continue

            for p in _paramBlocks(para):
                self.paramDescriptions.append(Param(p))

