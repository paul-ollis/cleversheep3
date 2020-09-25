"""Test loading and execution context.

During test loading and execution, there is an amount of context that needs
to be maintained in order to manage some behaviours and reporting. This
information is stored in a `TesterContext`.

"""
__docformat__ = "restructuredtext"


import os
import sys

from cleversheep3.Prog import Files

_curContext = None


class CSMod:
    def __init__(self, name, parent, pathDir):
        self.parent = parent
        self._name = name
        self.__path__ = [pathDir]
        self.__builtins__ = __builtins__

    @property
    def __name__(self):
        if self.parent:
            return "%s_%s" % (self.parent._name, self._name)
        return self._name


class TesterContext:
    """The context for a test, suite, script, etc.

    This is not anything particularly special. It ia basically somewhere to
    store information pertinent to a given test, script, etc.

    """
    execDir = None
    _contexts = {}

    def __init__(self, dirPath, packageName):
        self.dirPath = dirPath
        self.packageName = packageName
        if self.packageName not in sys.modules:
            mod = CSMod(self.packageName, None, self.dirPath)
            sys.modules[self.packageName] = mod

    @property
    def package(self):
        return sys.modules.get(self.packageName, None)


def getContext(dirPath=None, filePath=None):
    """Get the context matching specific information.

    :Parameters:
      dirPath
        The path of a directory that identifies the context.
      filePath
        The path of a file within the directory that identifies the context.

    """
    if (dirPath, filePath) == (None, None):
        return _curContext

    if TesterContext.execDir is None:
        TesterContext.execDir = os.path.abspath(os.getcwd())

    if filePath:
        dirPath = os.path.dirname(os.path.abspath(filePath))

    if dirPath not in TesterContext._contexts:
        scriptRelDir = Files.relName(dirPath, TesterContext.execDir)
        if scriptRelDir and scriptRelDir != ".":
            packageName = os.path.join("_CS_", scriptRelDir)
        else:
            packageName = "_CS_"
        packageName = packageName.replace(os.sep, "_")
        context = TesterContext._contexts[dirPath] = TesterContext(dirPath, packageName)

    context = TesterContext._contexts[dirPath]
    switchContext(context)
    return context


def switchContext(context):
    global _curContext
    _curContext = context
