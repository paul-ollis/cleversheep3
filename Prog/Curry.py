#!/usr/bin/env python
"""Function currying.

This module exports a single class called `Curry`.
"""
from __future__ import print_function
__docformat__ = "restructuredtext"

import os
import re

class Curry:
    """A general purpose function currying facility.

    This provides a flexible way to curry functions. The basic usage is:<py>:

        curried = Curry(somefunc, a1, a2, k1="high", k3="low")
        # ... do other things
        result = curried(a3, k2="middle")

    The last line is much like to doing:<py>:

        result = somefunc(a1, a2, a3, k1="high", k2="low", k3="low")

    However, arguments are evaluated at construction time, so given a function:<py>:

        def product(x, prefix="Product is"):
            print(prefix, x * x)

    Then:<py>:

        a = 2
        s = Curry(product, a, 5)
        a = 5
        s()                       # Prints 'Product is 10' (not 25)

    You can change and add arguments for a curried function. For example:<py>:

        s = Curry(product, 3)
        s.append(6)
        s()                       # Prints 'Product is 18'
        s.set(prefix="Result is")
        s()                       # Prints 'Result is 18'

    :Param func:
        The function to be curried.
    :Param args:
        Positional arguments for the function.
    :Param kwargs:
        Keyword arguments for the function.

    """
    def __init__(self, func, *args, **kwargs):
        self._func = func
        self.pending = list(args[:])
        self.kwargs = kwargs.copy()
        self.__name__ = func.__name__
        self.__name__ = self.__name__

    def __call__(self, *args, **kwargs):
        if kwargs and self.kwargs:
            kw = self.kwargs.copy()
            kw.update(kwargs)
        else:
            kw = kwargs or self.kwargs
        return self._func(*(self.pending + list(args)), **kw)

    def set(self, **kwargs):
        """Add or modify keyword arguments.

        :Param kwargs:
            Each keyword argument is used to update the curried function's
            keyword arguments.
        """
        self.kwargs.update(kwargs)

    def append(self, *args):
        """Append to the list of positional arguments.

        :Param args:
            Each argument is added to the set list of arguments.
        """
        self.pending.extend(args)

    def function(self):
        """Return the underlying function."""
        return self._func
