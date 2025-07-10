#!/usr/bin/env python
"""Special ``dict`` support.

Currently this module provides the following special dict classes.

`TrackerDict`
    Allows tracking of when keys get added and deleted.

`KeyCountDict`
    Allows tracking of how many instances have each defined key.
"""
__docformat__ = "restructuredtext"


class TrackerDict(dict):
    """A dictionary that allows you to track when keys are added or removed.

    This is a specialisation of the built-in ``dict``. It is intended to be
    used when you need to know when a key is fist added or deleted. Typical use
    involves subclassing and over-riding `onAdd` and `onDel`.

    Note that `onAdd` is called whenever an item is set and the key does not
    currently exist. So, for example:<py>:

        prefs = TrackerDict()

        prefs["stilton"] = "best"      # prefs.onAdd() is invoked
        prefs["stilton"] = "ok-ish"
        del prefs["stilton"]           # prefs.onDel() is invoked
        prefs["stilton"] = "runny"     # prefs.onAdd() is invoked again

    .. Warning::
       This class defines a ``__del__`` method, which can interfere with
       garbage collection. However, if your KeyCountDict instance froms part of
       a reference cycle then your counts will go wrong anyway.
    """
    def __init__(self, *args, **kwargs):
        d = dict(*args, **kwargs)
        dict.__init__(self)
        self.update(d)

    def onAdd(self, key):
        """Invoked when `key` is being added to the dict.

        This is invoked **before** the `key` is added, so ``self[key]`` will
        cause a ``KeyError`` exception.

        :Param key:
            The key being added.
        """

    def onDel(self, key):
        """Invoked when `key` is being deleted from the dict.

        This is invoked **after** the `key` has been removed, so ``self[key]``
        will cause a ``KeyError`` exception.

        :Param key:
            The key being deleted.
        """

    def _recordAdd(self, k):
        if k not in self:
            self.onAdd(k)
        dict.__setitem__(self, k, v)

    def __setitem__(self, k, v):
        self._recordAdd(k)
        super(TrackerDict, self).__setitem__(k, v)

    def __delitem__(self, k):
        dict.__delitem__(self, k)
        super(TrackerDict, self).__delitem__(k)
        self.onDel(k)

    def setdefault(self, k, v):
        self._recordAdd(k)
        super(TrackerDict, self).setdefault(k, v)

    def update(self, other):
        for k, v in six.iteritems(other):
            self.__setitem__(k, v)

    def copy(self):
        d = self.__class__()
        d.update(self)
        return d

    def __del__(self):
        for k in self:
            self.onDel(k)


class KeyCountDict(TrackerDict):
    """A `TrackerDict` that counts how many instnances have each key.

    An example:<py>:

        class CheeseCounter(KeyCountDict):
            keyCounts = {}
        prefs  = CheeseCounter()
        styles = CheeseCounter()

        prefs["stilton"] = "best"   # CheeseCounter.keyCounts["stilton"] == 1
        prefs["stilton"] = "ok-ish" # CheeseCounter.keyCounts["stilton"] == 1
        styles["stilton"] = "runny" # CheeseCounter.keyCounts["stilton"] == 2
        del prefs["stilton"]        # CheeseCounter.keyCounts["stilton"] == 1

    In normal use you need to sub-class and define keyCounts for the sub-class,
    unless you really want to use the keyCounts defined here.

    :Cvar keyCounts:
        A normal dictionary that maps keys to counts.
    """
    keyCounts = {}
    def onAdd(self, key):
        self.keyCounts.setdefault(key, 0)
        self.keyCounts[key] += 1

    def onDel(self, key):
        self.keyCounts[key] -= 1
        if self.keyCounts[key] <= 0:
            del self.keyCounts[key]
