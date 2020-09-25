#!/usr/bin/env python
"""A simple buffer for storing events of interest during a test.

This module provides a formal way of keeping a buffer of recent 'events', which
can later be queried. It is useful in complex test programs, which need to be
able to react to a number of asynchronous sources of events, such as sockets
connected to different processes. In such a situation, important events (i.e.
ones you wish to check in order to verify correct operation) do not necessarily
occur in a well defined order.

So we use an `EventStore` to keep a windowed buffer of recent events. When
something of interest is detected, you add it to the store. Separately, the
main 'thread' of the test harness can query the store to verify that expected
events have occurred.

"""
from __future__ import print_function
__docformat__ = "restructuredtext"


import time


class TestEvent:
    """A base class for all events.

    This provided as a suitable base class for all storeable events. You do not
    have to use this; it is just to make things easier.

    :Ivariables:
      args
        An list of arbitrary event arguments. This holds the non-keyword
        argument passed to constructor. For example::

            evt = TestEvent(1, 99, a=3, b=6)

        would result in args of ``[1, 99]``.

      info
        An dictionary of arbitrary event information. This holds the keyword
        argument passed to constructor. For example::

            evt = TestEvent(1, 99, a=3, b=6)

        would result in info of ``{"a": 3,  "b": 6}``.

    """
    def __init__(self, *args, **kwargs):
        """Constructor:

        :Parameters:
          args, kwargs
            All positional and keyword arguments are simply copied to the
            instance, as the `args` and `info` attributes.

            Note that code is generally clearer if you only use keyword
            arguments.

        """
        self.t = time.time()
        self.args = list(args)
        self.info = kwargs.copy()
        self.t = time.time()

    def __eq__(self, rhs):
        """Default test for equality.

        This compares the `args` and `info` attributes of this and the `rhs`
        instance. For both to be considered identical, each set of `args` must
        test equal and all the entries in the `rhs` instance's `info` must
        match those of this instance. However, this instance may contain items
        in its `info` that are not in the `rhs`. In

        Param `rhs`:
            Another `TestEvent` instance to compare with this one.

        """
        if not (isinstance(rhs, type(self))
                or isinstance(self, type(rhs))):
            return False
        if not isinstance(rhs, TestEvent):
            return False
        if self.args != rhs.args:
            return False
        for k in self.info:
            if k not in rhs.info:
                return False
            if self.info[k] != rhs.info[k]:
                return False
        return True

    def __ne__(self, rhs):
        """Default test for inequality.

        This is simply ``not`` `__eq__`.

        """
        return not self.__eq__(rhs)

    def __getattr__(self, name):
        """Provides attribute like access for `info` entries."""
        return self.info.get(name)


class EventStore:
    """A store of recent events.

    This is a simple sequence, which normally holds `TestEvent` records. Each
    record that gets added is given time stamped and when it gets to old, it
    is removed from the store. Pruning of old entries occurs whenever you
    access the store, hence it guarantees that you will never 'find' an event
    that is 'too old'.

    Events are stored in the order they get added and you can use the `find`
    method to see if an event of interest is curretnly in the store.

    :Ivariables:
      maxAge
        The maximum permitted age of items in the store, in seconds. If
        this is ``None``, then no age limit is applied. You may modify this
        directly.

        Initially this is set to 10.0 seconds. It is reinitialised to
        this value by the `reset` method.

      maxLength
        The maximum permitted length store. If this is ``None``, then no
        length limit is applied. You may modify this directly.

        Initially this is set to 100 events. It is reinitialised to
        this value by the `reset` method.

    """
    def __init__(self):
        self.reset()

    def reset(self):
        """Reset to initialised, default state.

        This deletes all events and reset the `maxAge` and `maxLength`
        attributes to the default values of 10.0 and 100.

        """
        self.clear()
        self.maxAge = 10.0
        self.maxLength = 100

    def addEvent(self, evt):
        """Add a new event.

        :Parameters:
          evt
            The event to add. This would normally be a `TestEvent` instance, but
            the store places no interpretion on this parameter.
        """
        self.trim(self.maxAge, self.maxLength)
        t = time.time()
        self._store.append((t, evt))

    def clear(self):
        """Removes all items from the store."""
        self._store = []

    def getOldest(self):
        """Get the oldest event.

        :Return:
            The oldest event, or ``None`` if there are no events.

        """
        self.trim(self.maxAge, self.maxLength)
        if not self._store:
            return
        return self._store[0][1]

    def trim(self, maxAge=None, maxLength=None):
        """Remove old and excess items.

        This is used internally, but is may also be useful it you wish to
        make sure items of a certain age are purged.

        :Parameters:
          maxAge
            The maximum permitted age of titems in the store. Items older than

            this are removed.
        """
        if maxLength is not None:
            if maxLength <= 0:
                return self.clear()
            self._store[:] = self._store[-maxLength:]
        if maxAge is None:
            return
        minTime = time.time() - maxAge
        i = 0
        for i, (t, evt) in enumerate(self._store):
            if t >= minTime:
                break
        else:
            i = len(self._store)
        if i > 0:
            del self._store[0:i]

    def filter(self, predicate, klass=TestEvent):
        """Generator: Yields events that match specific criteria.

        :Param predicate:
            A function that will be called to check for equality. It is called
            as:

                predicate (storedEvt)

            and should return a true value if the event matches.
        :Param klass:
            The type of event you want to find. By default, all `TestEvent`
            entries are checked.

        :Return:
            The event that was found or None. The returned event can be passed to
            `chop` or `remove`.
        """
        self.trim(self.maxAge, self.maxLength)
        for i, (t, tryEvt) in enumerate(self._store):
            if klass is not None and not isinstance(tryEvt, klass):
                continue
            if predicate(tryEvt):
                yield tryEvt

    def chop(self, evt, inclusive=True):
        """Remove old events.

        The ``evt`` is looked for in the store. If found then all older
        events are deleted. If ``inclusive`` is omitted or ``True`` then
        the ``evt`` itself is also removed.

        :Parameters:
          evt
            The event to search for. This must be an actual event in the
            store; i.e. you must have gotten it by searching the store.
          inclusive
            True by default. Set to a ``False`` value to prevent the
            ``evt`` in the store.

        """
        for i, (t, tryEvt) in enumerate(self._store):
            if tryEvt is evt:
                break
        else:
            return
        if inclusive:
            i += 1
        del self._store[0:i]

    def remove(self, evt):
        """Remove a single event from the store.

        The ``evt`` is looked for in the store. If found then it
        is removed.

        :Parameters:
          evt
            The event to search for. This must be an actual event in the
            store; i.e. you must have gotten it by searching the store.

        """
        for i, (t, tryEvt) in enumerate(self._store):
            if tryEvt is evt:
                break
        else:
            return
        del self._store[i]

    def removeAll(self, evtSet):
        """Remove a set of events from the store.

        This is typically used with the return value from `findAll`. All the
        events in evtSet are removed from the store.

        :Parameters:
          evtSet
            The set of events to search for. Each entry be an an actual event
            in the store; i.e. you must have gotten it by searching the store.
            This can be any object that can be converted to a list using
            ``list(evtSet)``.

        :Return:
            A tuple of any events that were not found.

        """
        remaining = list(evtSet)
        toDel = []
        for i, (t, tryEvt) in enumerate(self._store):
            if tryEvt in remaining:
                remaining.remove(tryEvt)
                toDel.append(i)
        for i in reversed(toDel):
            del self._store[i]

        return tuple(remaining)

    def find(self, evt=None, klass=TestEvent, predicate=None,
                chop=False):
        """Try to find an event in the store.

        :Parameters:
          evt
            An event to compare to items in the store.
          klass
            The type of event you want to find. By default, all `TestEvent`
            entries are checked againt the `evt`.
          predicate
            A function that will be called to check for equality. It is called
            as:

                predicate (storedEvt)

            and should return a true value if the event matches. When the
            ``predicate`` parameter is supplied, the `evt` parameter is not
            used.
          chop
            If you set this to a true value then the event that is found and
            all older events are removed from the store.

        :Return:
            The event that was found or None.
        """
        self.trim(self.maxAge, self.maxLength)
        for i, (t, tryEvt) in enumerate(self._store):
            if klass is not None and not isinstance(tryEvt, klass):
                continue
            if predicate:
                if predicate(tryEvt):
                    break;
            elif evt == tryEvt:
                break
        else:
            return None

        if chop:
            del self._store[0:i+1]
        return tryEvt

    def findAll(self, evt=None, klass=TestEvent, predicate=None):
        """Find mulitple events in the event store.

        This is like `find`, but a tuple of all matching events is returned.

        :Parameters:
          evt
            An event to compare to items in the store.
          klass
            The type of event you want to find. By default, all `TestEvent`
            entries are checked againt the `evt`.
          predicate
            A function that will be called to check for equality. It is called
            as:

                predicate (storedEvt)

            and should return a true value if the event matches. When the
            ``predicate`` parameter is supplied, the `evt` parameter is no
            used.

        :Return:
            A tuple of all the matching events, oldest first.

        """
        found = []
        self.trim(self.maxAge, self.maxLength)
        for i, (t, tryEvt) in enumerate(self._store):
            if klass is not None and not isinstance(tryEvt, klass):
                continue
            if predicate:
                if predicate(tryEvt):
                    found.append(tryEvt)
            elif evt == tryEvt:
                break
        return tuple(found)

    def __len__(self):
        self.trim(self.maxAge, self.maxLength)
        return len(self._store)


#: The default (kind of singleton) event store.
#:
#: Most test applications can simply use this. Only special situations
#: require more than one instance of `EventStore`.
eventStore = EventStore()


if __name__ == "__main__": #pragma: no cover
    s = EventStore(2)
    s.addEvent(3)
    s.addEvent(4)
    s.addEvent(5)
    s.addEvent(6)
    time.sleep (1.8)
    s.addEvent(7)

    print(s.find(4, int, chop=1))
    print(s.find(3, int))
    print(s.find(5, int, predicate=lambda a: a == 5))
    print(s.find(6, int))
    print(s.find(7, int))
    time.sleep(1)
    print("---")
    print(s.find(3, int))
    print(s.find(4, int))
    print(s.find(5, int))
    print(s.find(6, int))
    print(s.find(7, int))
    time.sleep(2)
    print("---")
    print(s.find(6, int))
    print(s.find(7, int))

