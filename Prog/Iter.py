#!/usr/bin/env python
"""Some useful iteration tools.

This module provides various tools that can prove helpful for tasks that
involve iteration.
"""
from __future__ import print_function
__docformat__ = "restructuredtext"


class PushBackIterator:
    """An iterator that supports pushing items back.

    This was written to support simple text parsing, in which you need some
    amount of look-ahead and back-tracking. Whilst back-tracking may be
    considered harmful in parsers, for many simple tasks it is actually
    a perfectly adequate approach.
    """
    def __init__(self, it):
        """Constructor:

        :Param it:
            An iterable object.
        """
        self._it = iter(it)
        self._ungotten = []

    def __next__(self):
        """Iterator protocol: get next element

        If any items have been pushed back, then the most recently pushed item
        is returned. Otherwise we try to get the next new item.
        """
        if self._ungotten:
            return self._ungotten.pop()
        return next(self._it)
    next = __next__

    def peek(self):
        """Peek the next element

        If any items have been pushed back, then the most recently pushed item
        is returned. Otherwise we try to get the next new item.

        """
        if not self._ungotten:
            try:
                self.pushBack(next(self._it))
            except StopIteration:
                return
        return self._ungotten[-1]

    def pushBack(self, v):
        """Push `v` back into the iterator.

        :Param v:
            This can be anything, although it would normally be an item
            previously returned by `next`.
        """
        self._ungotten.append(v)

    #: An alias for pushBack
    unget = pushBack

    def __iter__(self):
        """A PushBackIterator is its own iterator."""
        return self


class FileReader(PushBackIterator):
    def __init__(self, srcFile, srcPath="<TEXT>"):
        PushBackIterator.__init__(self, enumerate(srcFile))
        self.srcPath = srcPath


def groups(it, size=2, partial=True):
    """Generator: Yields groups of items from an iterable.

    I have often found I want groups of values from a sequence. This does the
    job.

    :Param it:
        An iterable object.
    :Param size:
        The max size of each group. This defaults to 2 because that is the most
        common value in my experience.
    :Param partial:
        Over-ride this to False if you do not want any trailing partial groups.
    """
    g = []
    for el in it:
        g.append(el)
        if len(g) == size:
            yield g
            g = []

    if g and partial:
        yield g

pairs = groups


if __name__ == "__main__": #pragma: no cover
    s = [1, 2, 3, 4, 5]
    pb = PushBackIterator(s)

    for i in range(2):
        print(next(pb))

    a = next(pb)
    b = next(pb)
    pb.unget(b)
    pb.unget(a)

    for n in pb:
        print(n)


    print(list(pairs(s)))
    print(list(groups(s, 3)))
    print(list(groups(s, partial=0)))
