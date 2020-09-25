"""A module that maps unique strings to the same objects.

This is useful when, for example, you have some complicated structures that
are identified and referenced by names.

"""
__docformat__ = "restructuredtext"


import builtins

from cleversheep3.Prog.Aspects import decorator


try:
    _intern = builtins.intern
except AttributeError:
    import sys
    _intern = sys.intern


def intern(s):
    """Intern a string.

    This simply invokes the builtin intern function. You do not need to
    use this, but this will work for python3.0 as well.
    """
    return _intern(s)


def internIfStr(s):
    """Intern `s` if it is a string type.

    :Param s:
        The 'string' to be interned.
    :Return:
        If `s` is a string type the interned string. Otherwise the return value
        is simply ``s``.
    """
    if isinstance(s, str):
        return intern(s)
    return s


def internProperty(attrName):
    """Property maker: For attributes that must be stored as interned strings.

    :Param attrName:
        The name of the internal attribute associated with this property.
    :Return:
        A property that interns upon assignment.
    """
    def get(self):
        return getattr(self, attrName)

    def set(self, v):
        setattr(self, attrName, internIfStr(v))

    return property(fget=get, fset=set)


@decorator
def internFuncStrings(func, *args, **kwargs):
    """"Function decorator: Converts all str args to `Ustr` instances.

    Arguments that are not strings are left unmodified.
    """
    args = (internIfStr(v) for v in args)
    for name in kwargs.keys():
        kwargs[name] = internIfStr(kwargs[name])
    return func(*args, **kwargs)


@decorator
def internMethodStrings(func, self, *args, **kwargs):
    """"Method decorator: Converts all str args to `Ustr` instances.

    Arguments that are not strings are left unmodified.

    This assumes that the function being decorated is a method.
    """
    args = tuple((internIfStr(v) for v in args))
    for name in kwargs.keys():
        kwargs[name] = internIfStr(kwargs[name])
    return func(self, *args, **kwargs)
#!/usr/bin/env python
