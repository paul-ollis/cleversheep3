#!/usr/bin/env python
"""Various network programming related utilities.

This module provides some support for manipulating IP addresses.

"""
__docformat__ = "restructuredtext"

class InvalidFormat(Exception):
    """Raised if a dotted IP address string does have the correct format."""


class IpAddress:
    """An IP address.

    Just makes it *that much* easier to manipulate IPV4 addresses.
    A number of properties -- `ival`, `hval`, `sval`, `bytes` --
    provide the address in a number of useful formats.
    """
    def __init__(self, addr):
        """Constructor:

        See `set` for parameter details.

        """
        self.set(addr)

    def set(self, addr):
        """Set the address.

        :Param addr:
            May be a 32 bit value or a string in dotted notation.
        :Raises InvalidFormat:
            If ``addr`` does not look like a valid IP address.
        """
        if isinstance(addr, IpAddress):
            return self.set(addr.addr)

        error = InvalidFormat("Not a valid IP address %r" % (addr,))
        if isinstance(addr, str):
            temp = addr.split(".")
            parts = [s.strip() for s in temp]
            if len(parts) != 4 or parts != temp:
                raise error

            try:
                values = [int(i) for i in parts]
            except (ValueError, TypeError):
                raise error

            for v in values:
                if not 0 <= v <= 255:
                    raise error

            # Yipee! The string is a valid address.
            v = values
            self.addr = (int(v[0]) << 24) | (v[1] << 16) | (v[2] << 8) | v[3]

        else:
            if not 0 <= addr <= 0xFFFFFFFF:
                raise error
            self.addr = addr

    def increment(self, v=1):
        """Increment the IP address value

        :Param v:
            The increment, which defaults to 1.

        """
        self.addr += v

    def _bytes(self):
        v = self.addr
        bytes = [v >> 24, (v >> 16) & 0xff, (v >> 8) & 0xff, v & 0xff]
        return bytes

    def _dotted(self):
        return ".".join([str(v) for v in self._bytes()])

    ival = property(fget=lambda o: o.addr,
            doc="The address as a number")

    hval = property(fget=lambda o: "0x%08x" % o.addr,
            doc="The address as a hexadecimal string")

    sval = property(fget=lambda o: o._dotted(),
            doc="The address in dotted form.")

    bytes = property(fget=lambda o: o._bytes(),
            doc="The address as a tuple of 4 byte values (as longs)")

    def __str__(self):
        return self.sval


class InetAddr(IpAddress):
    """An internet address for AF_INET socket programming.

    This is a nice convenience for use with socket programming. It simply adds
    a `port` number to the `IpAddress` properties of `ival`, `hval`, `sval`,
    `bytes`.
    """
    def __init__(self, addr, port):
        """Constructor:

        :Param addr:
            See `IpAddress.set` for details.
        :Param port:
            The port number.
        """
        IpAddress.__init__(self, addr)
        self.port = port #: The port part of the address.


class MaskedIpAddress(IpAddress):
    """An IP address with a mask.

    TODO
    """
    def __init__(self, addr, bits=32):
        """Constructor: See `set` for parameter details."""
        self.set(addr, bits)

    def set(self, addr, bits=32):
        """Set the address and mask.

        :Param addr:
            May be a 32 bit value or a string in dotted notation, with optional
            trailing mask. An example string is '127.0.0.0/24'. If a mask is
            included then the `bits` parameter is ignored.
        :Param bits:
            A number between 0 and 32. The default is 32, i.e. not masked.

        :Raises InvalidFormat:
            If the address or bit mask is invalid.
        """
        if isinstance(addr, MaskedIpAddress):
            return self.set(addr.addr, addr._maskBits)
        if isinstance(addr, IpAddress):
            return self.set(addr.addr)

        if isinstance(addr, str):
            error = InvalidFormat("Not a valid IP address %r" % addr)
            temp = addr.split("/")
            if len(temp) not in (1, 2):
                raise InvalidFormat("Not a valid masked IP address %r" %
                        addr)

            IpAddress.set(self, temp[0])

            if len(temp) == 2:
                maskStr = temp[1]
                try:
                    bits = int(maskStr)
                except (ValueError, TypeError):
                    raise InvalidFormat("Not a valid bits mask '%r'" % maskStr)

        else:
            IpAddress.set(self, addr)

        self._setBits(bits)

    def _setBits(self, bits):
        if not 0 <= bits <= 32:
            raise InvalidFormat("Not a valid bits mask '%r'" % bits)
        self._maskBits = bits
        self._mask = (0xffffffff >> (32 - bits)) << (32 - bits)

    sval = property(fget=lambda o: "%s/%d" % (o._dotted(), o.bits),
            doc="The address in dotted form.")

    bits = property(fget=lambda o: o._maskBits, fset=_setBits,
            doc="The number of bits in the mask")

    mask = property(fget=lambda o: o._mask,
            doc="The address mask as a integer")

    hmask = property(fget=lambda o: "0x%08x" % o._mask,
            doc="The address mask as a hexadecimal string")
