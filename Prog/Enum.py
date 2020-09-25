#!/usr/bin/env python
"""Support for enumerated values.

Sometimes your really want something closer to an enumerated type. This is my
take on supplying something to do this.

Usage is along the lines of::

    Colours = Enum("Colours")
    RED = Colours("Red")
    BLUE = Colours("Blue")
    GREEN = Colours("Green")

The above defines an enumerated type called ``Colours`` then three "constants"
of that type. The values are all subclassed from ``int``.

Currently there is no way to explicitly set the values of Enums.

"""
from __future__ import print_function
__docformat__ = "restructuredtext"


class DuplicateTypeName(Exception):
    """An attempt to define two enum type with the same name"""

class DuplicateEnum(Exception):
    """An attempt to define two enums with the same name"""


class EnumVal(int):
    """An individual enumerated type value.

    Direct construction of these is not supported. You should call an
    `EnumType` instance, as in:<py>:

        Colours = Enum("Colours")
        RED = Colours("Red")

    Enumerated values are based on the built-in ``int`` and so can be used
    wherever you would normally use an ``int``. The main difference is the
    way they are converted to strings, using ``repr`` and ``str``.

    """
    def __new__(cls, *args, **kwargs):
        v, name, enumTypeName = args[:3]
        # Convert name to EnumType. Note: we cannot use the type directly
        # because that would mean ``__getnewargs__`` would have to return an
        # EnumType instance, which breaks (un)pickling.
        enumType = _getEnumType(enumTypeName)
        obj = enumType.getDefined(name)
        if obj is not None:
            return obj
        return super(EnumVal, cls).__new__(cls, v)

    def __init__(self, value, name, enumTypeName, **kwargs):
        enumType = _getEnumType(enumTypeName)
        self.name = name
        self.enumType = enumType
        self.altName = kwargs.pop("altName", name)

    def __repr__(self):
        return "%s:%s=%s" % (self.enumType.name, self.name,
                super(EnumVal, self).__repr__())

    def __str__(self):
        return self.name

    def __getnewargs__(self):
        return int(self), self.name, self.enumType.name


class EnumType:
    """An enumerated type.

    Direct construction of these is not supported. Use the `Enum` factory
    function.

    """
    def __new__(cls, *args, **kwargs):
        name = args[0]
        if name in _definedTypes:
            return _definedTypes[name]
        return super(EnumType, cls).__new__(cls)

    def __getnewargs__(self):
        return (self.name, )

    def __init__(self, name, strict):
        self._defined = {}
        self._nextVal = 0
        self._strict = strict
        self.name = name

    def getDefined(self, name):
        """Check if a given Enum name is defined.

        :Return:
            A True value if the given name is defined.

        :Param name:
            The name to look up.

        """
        if name in self._defined:
            return self._defined[name]

    def __call__(self, name, **kwargs):
        if name in self._defined:
            if self._strict:
                raise DuplicateEnum(
                    "There is already an Enum called %r for %s" % (
                        name, self.name))
            else:
                return self._defined[name]

        v = EnumVal(self._nextVal, name, self.name, **kwargs)
        self._defined[name] = v
        self._nextVal += 1
        return v


_definedTypes = {}
def Enum(typeName, strict=True):
    """Declares a new enumerated type.

    This acts as a factory function, returning an `EnumType` instance.

    :Return:
        The new `EnumType`.

    :Param typeName:
        The name for the enumerated type. This has to be unique across your
        entire application. (I hope to lift this restriction at a later
        date.)
    :Param strict:
        Selects whether the new enumerated type allows enumerated value to
        be redefined. If this is True then enumerated values cannot be
        redefined.

    """
    if typeName in _definedTypes:
        raise DuplicateTypeName(
                "There is already an Enum called %r" % typeName)
    _definedTypes[typeName] = EnumType(typeName, strict)
    return _definedTypes[typeName]


def _getEnumType(typeName):
    return _definedTypes.get(typeName, None)


if __name__ == "__main__": #pragma: debug
    TrafficLights = Enum("TrafficLights")
    tl_red = TrafficLights("red")
    tl_amber = TrafficLights("amber")
    tl_green = TrafficLights("green")

    print([repr(e) for e in (tl_red, tl_amber, tl_green)])
    print(tl_red > tl_amber)
    print(tl_green > tl_amber)

    Colours = Enum("TrafficLights")
