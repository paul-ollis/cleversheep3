"""Functions for comparison of floating-point numbers.

This module provides implementation of algorithms for detailed here:
http://www.cygnus-software.com/papers/comparingfloats/comparingfloats.htm.

"""
__docformat__ = "restructuredtext"


import struct
import math


def _convertFloatTo32BitInt(x):
    """Convert 32-bit float to integer.
    
    Perform something akin to a C-style memory cast in order to achieve
    conversion of float value into integer. The souce paper has C code
    along the lines of:
    
      uint32_t v = *(long*)&x;
      if (v < 0)
      {
          v = 0x80000000 - v;
      }

    However, this is relying on the way 32-bit integer math works on a CPU.
    In the Python world, integers behave more mathmatically.

    So, what this does it map a 32-bit float as::

      < 0 --------->-0x80000001 ...

      -0.0 --.
              >----> 0x80000000
      +0.0 --'

      > 0 ---------> 0x7fffffff ....

    :Return:
        The integer representation as a long. For non-NaN values this is will
        be in the range 0 to 0xffffffff. If x is a NaN then the value -1 is
        returned.

    """
    if math.isnan(x):
        return -1
    ival = struct.unpack('I', struct.pack('f', x))[0]
    if ival == 0:
        ival = 0x80000000
    elif ival < 0x80000000:
        ival += 0x80000000
    else:
        ival = 0x100000000 - ival
    return ival


def ulpFloatDifference(a, b):
    """Return the ULP difference between two (32-bit) floats.
    
    Calculate the units of least precision (ULP) between specified
    floating-point numbers.

    :Return:
        The number of ULPs difference. If either value is a NaN then
        0x100000000 (8 zeros) is returned, which is larger than the ULP
        difference between any two noNaNs.
    
    """

    aInt = _convertFloatTo32BitInt(a)
    bInt = _convertFloatTo32BitInt(b)
    if aInt < 0 or bInt < 0:
          return 0x100000000
    return abs(aInt - bInt)
