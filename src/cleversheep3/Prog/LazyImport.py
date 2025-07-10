"""Paul's paten lazy import mechanism.

TODO:

"""

import sys

class Proxy:
    def __init__(self, name):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "__getattribute__", Proxy._getattribute__)

    def __getattr__(self, name):
        return getattr(self._mod, name)

    def _getattribute__(self, name):
        print("PROXY ACTIVE")
        modName = object.__getattribute__(self, "_name")
        del sys.modules[modName]
        d = {}
        code = "import %s" % modName
        exec(code, d, d)
        sys.modules[modName] = m
        del self.__getattribute__
        self._mod, m = d[modName]
        return getattr(m, name)


def lazy(name):
    if name in sys.modules:
        return sys.modules[name]
    proxy = Proxy(name)
    sys.modules[name] = proxy



lazy("zlib")
import zlib

print(zlib)
print(dir(zlib))

print(zlib.compress)
