#!/usr/bin/env python
"""A least recently used cache.

I know, why write one, surely there is something out there already? Well,
actually, not when I looked. I found a cookbook recipe that appeared dodgy and
freashmeat package at version 0.2, which looked complicated and not as
efficient as I wanted. Hence this module.

So, this module provides support for LRU caching.
"""
from __future__ import print_function
__docformat__ = "restructuredtext"

# TODO: I am pretty sure that the LruCache could be built on the SortedQ.


from heapq import heappush, heappop, heapreplace, heapify
import time

class LruNode:
    """A node representing an element within the LruCache.

    This class exists to provide correct sorting behaviour. Comparison of nodes
    depend only on the `t` member. This is important because these nodes get
    stored in a heapq, but we wish to change the contents of `data` without
    needing to re-sort the heap. If we used a simple list where each entry was
    a simple tuple of the form ``(t, data)``, then the heap's invariant would
    not be correctly maintained.

    :Ivar t:
        This represents time in some way, in that smaller values of ``t`` are
        older then larger values of ``t``.
    :Ivar data:
        This holds the node's data. It is treated as opaque and may be any
        python object.
    """
    def __init__(self, t):
        self.t = t

    def __lt__(self, rhs):
        return self.t <  rhs.t

    def __gt__(self, rhs):
        return self.t >  rhs.t

    def __eq__(self, rhs):
        return self.t ==  rhs.t


class LruCache:
    """A class implementing a general LRU Cache container.

    :Ivar delCB:
        A function that will be invoked as ``delCB(key, value)`` for any
        node that is automatically purged from the cache.

    Implementation details

    The actual content is stored in a dictionary of dataNodes. For each such
    dataNode there is corresonding lruNode. These are linked in a simple
    one-to-one relationship::

        dataNode <---> lruNode

    The lru heapq, has the oldest (least recently used) lruNode at the
    head of the queue.

    When a dataNode is looked up, a new lruNode is created to replace the
    existing one. Hence::

                       oldlruNode [defunct]
        dataNode <---> newLruNode

    The old lruNode, is simply marked as defunct so that we do not need to
    immediately re-sort the heap. The queue remains in LRU order, but some
    entries do not map to data items.

    When we decide to remove the oldest items, we simply pop entries
    the heapq. Any dead entries are simply discarded and live entries, point
    to the dataNode that can be discarded.

    """
    def __init__(self, maxSize=None, delCB=None):
        self.lru = []               #: List managed by heapq
        self.contents = {}          #: Entries we know about.
        self.size = 0
        self.maxSize = maxSize
        self.delCB = delCB
        self.maxDeadLinks = 0

    def getState(self):
        return self.lru, self.contents, self.size

    def setState(self, state):
        self.lru, self.contents, self.size = state

    def manip(self, key, value=None, size=1, peek=False):
        """Perform LRU manipulations for `get` and `add`.

        Both `add` and `get` are aliases for this method. If only `key` is
        provided then the operation is `get` otherwise the operation is `add`.

        :Param key:
            The key for the item in the LRU cache.
        :Param value:
            The value to add, if None then this is a `get` operation.
        :Return:
            A tuple of (value, size). The value can be ``None`` for a `get`
            operation, indicating that the entry is (no longer) in the cache.
        """
        oldValue, oldLruNode, oldSize = self.contents.get(key,
                (None, None, None))
        if oldLruNode is not None:
            # The key matched a possibly live entry.
            oldLruNode.dataNode = None
            oldLruNode.key = None
            self.size -= oldSize

        elif value is None:
            # Not an 'add' operation and the node was not found. So the 'get'
            # failed.
            return None, 0

        if value is None:
            # This is an insertion.
            value = oldValue
            size = oldSize

        t = time.time()
        lruNode = LruNode(t)
        lruNode.dataNode = [value, lruNode, size]
        lruNode.key = key
        self.size += size

        self.contents[key] = lruNode.dataNode
        if not peek:
            heappush(self.lru, lruNode)

        if self.maxSize is not None:
            self.trim()
        self.tidy()
        return value, size

    get = manip
    add = manip

    def remove(self, key):
        """Remove the entry with the given `key`.

        If the LRU contains a matching entry then it is is removed. The `delCB`
        is **not** invoked.

        :Param key:
            Identifies the entry to remove.
        """
        if key in self.contents:
            oldValue, oldLruNode, oldSize = self.contents.get(key,
                    (None, None, None))
            oldLruNode.dataNode = None
            oldLruNode.key = None
            self.size -= oldSize
            del self.contents[key]

    def __len__(self):
        return len(self.contents)
        # return len(self.lru) - len(self.contents)

    def trim(self):
        "Remove oldest items until the cache is small enough"
        while self.size > self.maxSize and self.lru:
            node = heappop(self.lru)
            if node.dataNode is None:
                continue
            value, thisNode, size = node.dataNode
            del self.contents[node.key]
            self.size -= size
            if self.delCB:
                self.delCB(node.key, value)

    def tidy(self):
        dead = len(self)
        deadLinkFraction = float(dead) / len(self.contents)
        self.maxDeadLinks = max(self.maxDeadLinks, deadLinkFraction)
        if len(self.lru) >= len(self.contents) * 2:
            self.lru = [l for l in self.lru
                if l.dataNode is not None]
            heapify(self.lru)

    def __iter__(self):
        def heapIter():
            for node in sorted(self.lru):
                if node.dataNode:
                    yield node.dataNode[0]

        return heapIter()

    def iterDataTimeSize(self):
        def heapIter():
            for node in sorted(self.lru):
                if node.dataNode:
                    yield node.dataNode[0], node.t, node.dataNode[2]

        return heapIter()


if __name__ == "__main__":  #pragma: no cover
    import random

    def counter():
        i = 0
        while True:
            yield i
            i += 1
    count = counter()
    count2 = counter()

    cache = LruCache(maxSize=100000)
    items = []

    for i in range(1000):
        item = [i, next(count)]
        cache.add (i, item, i)
        items.append(i)
        next(count2)

    seq = [random.randrange(len(items)) for i in range(40000)]
    a = time.time()
    for key in seq:
        if key % 30 == 0:
            i = next(count2)
            item = [i, next(count)]
            cache.add (i, item, i)
            items.append(i)

        item = cache.get(key)
        if item is not None:
            item[1] = next(count)
    print(time.time() - a)
    print("Size", cache.size, len(cache.contents), )
    print(   len(cache.lru) - len(cache.contents))
    print("Max dead links", cache.maxDeadLinks)

    prev = None
    indices = {}
    for el in cache:
        assert el[0] not in indices
        indices[el[0]] = None
        if prev:
            assert prev[1] < el[1]
        prev = el
