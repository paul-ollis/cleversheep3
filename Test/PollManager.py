"""Thin layer around aynchronous I/O module.

This allows automatic use of Tornado if available, but will fall back
to a built-in alternative.

"""
__docformat__ = "restructuredtext"

import six

import weakref

from cleversheep3.Test import cs_asyncio
from cleversheep3.App import Config


options = Config.Options("cstest")

default_impl = cs_asyncio.PollManagerImpl

POLLIN = default_impl.POLLIN
POLLPRI = default_impl.POLLPRI
POLLOUT = default_impl.POLLOUT
POLLERR = default_impl.POLLERR
POLLHUP = default_impl.POLLHUP
POLLNVAL = default_impl.POLLNVAL


class PollManager:
    """An event based asynchonous I/O (reactor).

    """
    def __init__(self, impl=None):
        """Initialisation.

        :Parameters:
          impl
            If supplied then this is typically a class that provides
            the underlying implementation. By default this is cleversheep3's
            built-in implementation, `cs_asyncio.PollManagerImpl`.
        """
        impl = cs_asyncio.PollManagerImpl
        self.impl = impl(CallbackRef)

    def __getattr__(self, name):
        return getattr(self.impl, name)


class CallbackRef:
    """A class to encapsulate information for callback functions.

    This class can effectively store a weak reference to a bound method; i.e.
    the method of a class instance (as opposed to a method of the class
    itself). Bound functions are created on the fly, and can have very short
    lifetimes (typically only as long as it takes to invoke the bound method.
    This is inconvenient when you want a bound method to be used as a callback,
    but also wish to reference the callback weakly.

    The way this class works is to store a weak reference to the class instance
    and also a reference to the class method.

    """
    def __init__(self, func=None):
        """Constructor:

        :Param func:
            The bound or unbound functions to be used as a callback.
            This may be omitted or set to ``None``, in which case the
            `CallbackRef` does nothing when invoked.
        """
        if func is None:
            self.cb = None
            return
        if hasattr(func, "__self__"):
            # This looks like a bound method so split up into instance and
            # function.
            self.cb = (
                weakref.ref(func.__self__), six.get_method_function(func))
        elif type(func) == type(len):
            self.cb = (None, lambda: func)
        else:
            self.cb = (None, weakref.ref(func))

    def isDead(self):
        return self.cb is None

    def kill(self):
        self.cb = None

    def isFunc(self, cmpFunc):
        if hasattr(cmpFunc, "__self__"):
            ref, func = self.cb
            if ref is None or ref() is None:
                return
            return ref() is cmpFunc.__self__ and func is cmpFunc.__func__
        if self.cb[0] is None:
            return self.cb[1]() is cmpFunc
        return self.cb[1] is cmpFunc

    def realFunc(self):
        if self.cb is None:
            return
        ref, func = self.cb
        if ref is None:
            func = func()
            if func is None:
                return None
        return func

    def __call__(self, *args, **kwargs):
        """Invoke the callback function, if possible.

        If the stored callback function can be invoked then it is,
        passing the ``args`` and ``kwargs``, as in::

            func(*args, **kwargs)

        :Return:
            If the callback cannot be invoked then a tuple of ``(None,None)``.
            Otherwise s tuple of ``(True, ret)``, where ``ret`` is the return
            code from the callback function.
        """
        if self.cb is None:
            return False, None
        ref, func = self.cb
        if ref is None:
            func = func()
            if func is None:
                return False, None
            return True, func(*args, **kwargs)
        inst = ref()
        if inst is None:
            return False, None
        return True, func(inst, *args, **kwargs)


class Handler:
    """A skeleton class that defines the 'handler protocol'."""
    def process(self, fd, ev):
        """Process a file event.

        :Param fd:
            The file descriptor for which there is activity.

        :Param ev:
            The actual event type.
        """

    def init(self):
        """This is invoked when the PollManager is started.

        Typically this would open file, sockets, etc and set up file events.
        """
