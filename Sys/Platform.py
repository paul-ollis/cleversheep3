#!/usr/bin/env python
"""<+One-liner+>

<+Detailed multiline documentation+>
"""
from __future__ import print_function
__docformat__ = "restructuredtext"

import sys
import platform

# Work out the generic platform type
_platformTypeMap = {
    "linux": "unix",
    "cygwin": "unix",
    "win32": "windows",
}
platformType = _platformTypeMap.get(sys.platform, "unix")
platform = sys.platform

del _platformTypeMap


if __name__ == "__main__": #pragma: no cover
    # This is useful for checking what your platform does.
    print("sys.platform", sys.platform)
    print("platform.system()", platform.system())
    print("platform.release()", platform.release())
    print("platform.version()", platform.version())
    print("platform.system_alias()", platform.system_alias(
            platform.system(),
            platform.release(),
            platform.version(),
            ))
    print("platform.platform(0, 0)", platform.platform(0, 0))
    print("platform.platform(0, 1)", platform.platform(0, 1))
    print("platform.platform(1, 0)", platform.platform(1, 0))
    print("platform.platform(1, 1)", platform.platform(1, 1))
