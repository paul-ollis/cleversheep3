#!/usr/bin/env python
"""Aspect oriented programming stuff.

This module provides support for some aspect oriented programming features.

Currently this mainly provides mainly ways to decorate methods/functions
en-masse.

"""
from __future__ import print_function
__docformat__ = "restructuredtext"

import six

import inspect
import linecache
import sys

NOVALUE = type("NOVALUE", (object,), {})


# This exposes the functions provided by Michele Simionato's decorater.py
# module.
try: #pragma: unreachable
    from decorator import decorator
except ImportError: #pragma: unreachable
    from cleversheep3.Extras.decorator import \
            decorator

from cleversheep3.Extras.decorator import \
        decorator


def callWrapper(func, before=None, after=None):
    """Wrap a function with L{before} and L{after} decoration.

    This generalises decorating a function with code to be run before and
    after the decorated function. The resulting function behaves like this(#py)::

        def newFunc(*args, **kwargs):
            closure = before()
            ret = func(*args, **kwargs)
            after(closure)
            return ret

    In practice, it is slighlty more complex, in order to handle exceptions
    gracefully. Also the details vary depending on which of L{before} and L{after}
    are supplied.

    If the L{before} function is not provided then the L{after} method is
    invoked as C{after()}.

    :Param func:
        The function to be decorated.
    :Param before:
        If provided and not None, then this function is invoked before
        the decorated function is invoked.
    :Param after:
        If provided and not None, then this function is invoked after
        the decorated function has completed.
    :Note:
        In the degenerate case of both before and after being None, the original
        L{func} is returned.
    """
    def caller12(*args, **kwargs):
        import os
        closure = before()
        try:
            return func(*args, **kwargs)
        finally:
            after(closure)

    def caller1(*args, **kwargs):
        before()
        return func(*args, **kwargs)

    def caller2(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            after()

    if before is not None:
        if after is not None:
            return caller12
        return caller1
    elif after is not None:
        return caller2
    return func


def decorate(func, decorator, owner=None):
    """Decorates a function 'in-place'.

    This decorates a function, effectively replacing it with the newly
    decorated form. If the function is a module level function, then the module's
    dictionary is updated. If the C{func} is a class method then it you should
    provide the class as the owner.

    For example(#py)::

        import fred

        def trace(func, *args, **kwargs):
            print("Call:", func.__name__)
            return func(*args, **kwargs)

        decorate(fred.myfunc, trace, fred)
        fred()                             # This call is traced.

        class X:
            def a(self):
                pass

        decorate(X.a, trace, X)
        x = X()
        x.a()                         # This call is traced.

    For module level functions, the owner can be omitted. For example, the following
    calls have the same effect(#py)::

        decorate(myfunc, trace, fred)
        decorate(myfunc, trace)

    :Param func:
        The function to be decorated.
    :Param decorator:
        A function that returns a decorated form of C{func}. This will be
        invoked as C{decorator(func)}.
    :Param owner:
        This should be zero for plain old functions and the class for
        methods.
    :Return:
        The decorated form of the function.
    """
    # if owner:
    #     ownerDict = dir(owner)
    name = func.__name__
    f = decorator(func)
    if owner:
        setattr(owner, name, f)
    elif owner != 0:
        func.__globals__[name] = f

    return f


@decorator
def protectCwd(func, *args, **kwargs):
    """Decorator that ensures the CWD does not change."""
    import os
    here = os.getcwd()
    try:
        return func(*args, **kwargs)
    finally:
        os.chdir(here)


def allSubclasses(namespace, klass):
    """Generator: Yield all classes in namespace that are a subclass of klass.

    This can be used to walk the tree of classes and subclasses. It
    helps when we wish to decorate class methods.
    """
    for name in namespace.copy():
        c = namespace[name]
        try:
            if issubclass(c, klass):
                yield c
        except TypeError:
            pass


def decorMethods(klass, regExpOrPredicate, wrapper):
    import re

    choose = lambda n, m: regExpOrPredicate(n, m)
    if not hasattr(regExpOrPredicate, "__call__"):
        rName = re.compile(regExpOrPredicate)
        choose = lambda n, m: rName.match(n)

    for name in dir(klass):
        method = getattr(klass, name)
        if choose(name, method):
            # Decorate the underlying function because decorator.py will not
            # decorate a class method.
            func = wrapper(six.get_unbound_function(method))
            setattr(klass, name, func)


# TODO: Duplication from Tester.Test.ImpUtils!
def _getCallerDict(callerDict=None, depth=2):
    """This is IT!!!!"""
    if callerDict is None:
        linecache.checkcache()
        frame = inspect.stack()[depth][0]
        try:
            return frame.f_globals
        finally:
            del frame
    return callerDict


def exportedFunction(f, asName=None):
    d = _getCallerDict()
    if not "__all__" in d:
        d["__all__"] = []
    name = asName or f.__name__
    if name not in d["__all__"]:
        d["__all__"].append(name)

    return f


if 'epydoc' in sys.modules: # pragma: no cover
    def public(f):
        d = _getCallerDict()
        if not "__all__" in d:
            d["__all__"] = []
        try:
            if f.__name__ not in d["__all__"]:
                d["__all__"].append(f.__name__)
        except AttributeError:
            return f

        return f
else:
    def public(f):
        return f


class PropertyError(Exception):
    pass


def intelliprop(method, prop=property):
    """Property decorator that keeps documentation.

    You can use this using the common property decorator idiom:<py>:

        @intelliprop
        def area(self):
            '''Get the area, calculated from the width and height'''
            return self._w * self._h

    However this decorator does some extra work. Firstly your can create
    read-write properties using a default value. As in:<py>:

        @intelliprop
        def area(self, value=NOVALUE):
            '''Get the area, calculated from the width and height.

            If this is set then the width and height are scaled to make the
            rectangle have the new area.

            '''
            if value is NOVALUE:
                return self._w * self._h
            a = self._w * self._h
            factor = value / a
            self._w *= factor
            self._h *= factor

    Secondly, the created property has a docstring, which is the docstring
    of the decorated method, prefixed by either 'Read-only: ' or 'Read-write: '.
    So for the above example, the properties docstring would start::

        Read-write: Get the area, calculated from the width and height.

        ...

    :Param method:
        The method to convert to a property.

    """
    try:
        doc = method.__doc__
        s = "" + doc
    except (AttributeError, TypeError):
        raise SyntaxError(
                "Methods docorated by intelliprop must have docstrings")
    if method.__defaults__:
        d = "Property: read-write\n\n" + method.__doc__
        return prop(method, method, doc=d)
    else:
        d = "Property: read-only\n\n" + method.__doc__
        return prop(method, doc=d)
