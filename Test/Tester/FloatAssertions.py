"""Support for meanfingful eqality test for floats.

This comes from GoogleTest, which references the following article by Bruce
Dawson:

    http://www.cygnus-software.com/papers/comparingfloats/comparingfloats.htm

and was originally pointed out to me by John Tidmus.

"""

import struct


def asInt(f):
    """Convert a floating point number into a comparable integer.

    This is designed to work IEEE floating point numbers.

    Given ``fa`` and ``fb``, where there is no floating point number between
    ``fa`` and ``fb`` that can be represented, but ``fa`` and ``fb`` have
    different IEEE representations, then:

        abs(asInt(fa) - asInt(fb)) == 1

    The only meaningful exception is that +0.0 and -0.0 are both converted to
    zero.

    :Parameters:
      f
        A number to be converted and manipulated as an IEEE 4-byte value.

    :Return:
        An integer that can be used to compared against other (converted)
        numbers in order to make 'meaninful' equality tests.

    """
    bytes = [ord(c) for c in struct.pack(">f", f)]
    v = 0
    while bytes:
        v = (v << 8) | bytes.pop(0)
    if v >= 0x80000000:
        v = 0x80000000 - v
    return v


if __name__ == "__main__":
    # Just for a flavour - not module tests.
    print(asInt(1.4012985e-045))
    print(asInt(0.0))
    print(asInt(-0.0))
    print(asInt(-1.4012985e-045))
