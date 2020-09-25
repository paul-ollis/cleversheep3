#!/usr/bin/env python
"""Provides an efficient queue of ordered items.

This provides the class SortedQ, which maintains items in a sorted order.
Internally it just uses the standard *heapq* module. What this adds above a
heapq, is the ability to effectively delete arbitrary entries.

Normally a heapq does not easily support removal of anything but the head.
The approach this module takes is to keep a note of deleted items and this is
used to skip over 'deleted' entries when the head item is requested.
"""
from __future__ import print_function
__docformat__ = "restructuredtext"


from heapq import heappush, heappop, heapify


class SortedQ:
    """A queue of ordered items.

    This class is suitable for keeping a queue of things in sorted order.
    The interface is quite simple::

        q = SortedQ()                 # Create a queue
        q.add(0.2, "Second")          # Add some items
        q.add(0.1, "First")
        x = q.add(0.25, "Unused")
        q.add(0.3, "Third")

        print(q.head())               # (0.1, 1, 'First')
        print(q.pop())                # (0.1, 1, 'First')
        q.remove(x)
        print(q.pop())                # (0.2, 0, 'Second')
        print(q.pop())                # (0.3, 3, 'Third')

    The underlying implementation uses a heapq, which is very efficient for
    things like time ordered queues (which is what it was written for).

    """
    def __init__(self):
        self.q = []
        self._deleted = set()
        self._uid = 0
        self._inQueue = set()

    def copy(self):
        """Create a copy of this queue.

        """
        q = SortedQ()
        q.q = list(self.q)
        q._inQueue = self._inQueue.copy()
        q._deleted = self._deleted.copy()
        q._uid = self._uid
        return q

    def add(self, v, data):
        """Add a new item, using *v* to sort into position.

        :Param v:
            This is the value that determines where the item is placed in the
            queue. The queue's head will always contain the entry with the
            lowest value of *v*. When two items have the same value of *v*, the
            first item to be added comes first (but this rule breaks if `resort`
            is called).
        :Param data:
            Some arbitrary data to be stored in the queue.
        :Return:
            A unique ID (*uid*), which may be used to `remove` the item
            later.

        """
        uid = self._uid
        self._uid += 1
        assert uid not in self._inQueue
        heappush(self.q, (v, uid, data))
        self._inQueue.add(uid)
        return uid

    def getUID(self):
        return self._uid

    def setUID(self, uid):
        self._uid = uid

    def quickReAdd(self, v, uid, data):
        """Re-add an entry quickly by simply appending.

        This is useful when re-adding multiple entries. The `resort` method
        will need to be invoked before the queue will behave correctly.

        """
        if uid not in self._inQueue:
            self.q.append((v, uid, data))
            self._inQueue.add(uid)

    def reInsert(self, v, uid, data):
        """Used to re-insert an item.

        This allows you to remove an item, then re-insert it and guarantee that
        it gets the same position.

        :Param v:
            This is the value that determines where the item is placed in the
            queue (see `add`).
        :Param data:
            Some arbitrary data to be stored in the queue.
        :Param uid:
            A unique ID. This should be an ID that was returned by an earlier
            call to `add`. *Do not* use a *uid* that has been passed to `remove`.
        :Return:
            The `uid` that was passed in.
        """
        assert uid not in self._inQueue
        heappush(self.q, (v, uid, data))
        self._inQueue.add(uid)
        return uid

    def remove(self, uid):
        """Remove the entry with the *uid* from the queue.

        Removes an entry that is currently in the queue.

        (Implemenation detail. The entry will typically remain in the queue for
        a while, but gets tidied up as items are popped.)

        :Param uid:
            This should be an ID of an entry that is currently known to be in
            the list.
        """
        if uid in self._inQueue:
            self._deleted.add(uid)

    def head(self, pop=False):
        """Returns the head of the queue.

        :Return:
            A tuple of (v, uid, data). The *v* and *data* are as passed to the
            call to `add` or `reInsert`. The ``uid`` is the value returned from
            the same call.

            If the queue is empty then three *None* values are returned.
        """
        while self.q:
            t, uid, data = self.q[0]
            if uid not in self._deleted:
                if pop:
                    heappop(self.q)
                    self._inQueue.remove(uid)
                return t, uid, data

            heappop(self.q)
            self._deleted.remove(uid)
            self._inQueue.remove(uid)
        return None, None, None

    def pop(self):
        """As for `head` but the first entry is also deleted."""
        return self.head(pop=True)

    def resort(self, getKey=lambda v, d: v):
        """Re-sort the heap, cleaning out any deleted items.

        :Parameters:
          getKey
            An optional function used to extract the sort key from each entry's
            current sort value and data. It is invoked as ``getKey(v, data)``.
            If not supplied then the current ``v`` value is used.

        """
        q = [(getKey(v, data), uid, data) for v, uid, data in self.q
                if uid not in self._deleted]
        while self._deleted:
            self._inQueue.remove(self._deleted.pop())
        heapify(q)
        self.q = q

    def __len__(self):
        """Support for ``len(q)``."""
        return len(self.q) - len(self._deleted)

    def __bool__(self):
        """Support for ``while q:...``."""
        return self.__len__() > 0

    def __iter__(self):
        def it():
            lCopy = list(self.q)
            while lCopy:
                t, uid, data = heappop(lCopy)
                if uid not in self._deleted:
                    yield t, uid, data
        return it()
