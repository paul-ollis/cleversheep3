#!/usr/bin/env python
"""Import utilities for testing.

Actually some of these could be considered general purpose, but I have only
found them to be of legitimate use in testing.

"""
__docformat__ = "restructuredtext"

import os
import os.path
import sys
import imp
import inspect


def _findImported(path):
    """Do a full search to see if a module has already been imported.

    """
    path = os.path.abspath(path)
    for n in list(sys.modules):
        m = sys.modules[n]
        try:
            if os.path.abspath(m.__file__) == path:
                return m
            if os.path.abspath(m.__file__) == path + "c": #pragma: unreachable
                return m
        except:
            pass


def _makeModName(modPath):
    modName = modPath.replace("."+ os.sep, "_")
    modName = modName.replace("-", "_")
    modName = modName.replace(os.sep, "_")
    modName = modName.replace(".", "_")
    return modName


def _getCallerDict(callerDict):
    """IMP Utils version"""
    if callerDict is None:
        try:
            frame = inspect.stack()[2][0]
            return frame.f_globals
        finally:
            del frame
    return callerDict


def _getModPath(modPath, cwd, callerDict):
    # Convert the path to the absolute form.
    if not modPath.endswith(".py"):
        modPath += ".py"
    if not os.path.isabs(modPath):
        if cwd:
            modPath = os.path.join(os.getcwd(), modPath)
        else:
            callerDir = os.path.abspath(os.path.dirname(
                callerDict.get("__file__")))
            modPath = os.path.join(callerDir, modPath)
    return os.path.normpath(os.path.abspath(modPath))


class _Str(str):
    """Local version of ``str``.

    This allows us to insert strings in ``sys.path``, and then remove them
    again reliably.
    """


# TODO: The 'cwd' param is not very obvious. Add a better named parameter
#       and deprecate 'cwd'.
def importPath(modPath, name=None, cwd=False, star=False, callerDict=None,
        doReload=False):
    """Import a module given its path, a low level import function.

    The simplest way to use this is:

        mod = importPath(modName)

    In this case the following steps are taken:

    1. The ``modPath`` is converted to an absolute path (if necessary) by
       prepending the directory part of the invoking module's ``__file``.

    2. The converted (absolute) path is used to make a module ``name``, by
       replacing dashes, dots and slashes with underscores.

    3. An attempt is made to find a matching, already imported, module using
       the (absolute) ``modPath``. If found then this module is
       returned - job done.

    4. Otherwise, ``imp.load_module`` is used to perform the import.

    The above behaviour can be altered using the optional keyword arguments,
    see the individual parameter docuementation for details.

    :Parameters:
      modPath
        The path to the module. This can optionally include the ``.py``
        extension - it is added if missing, so packages cannot be imported with
        this function. Do not use a ``.pyc`` or ``.pyo`` extension; the results
        are undefined.
      name
        The name to give the module. If this is None then a name is constructed
        from the path components.
      cwd
        If True then the modPath is taken to be relative to the CWD rather than
        the calling module's directory.
      star
        If True then ``from X import *`` is emulated.
      callerDict
        If set then this is used as the caller's dictionary, rather than
        inspecting the call stack.

    :Raises ImportError:
        If there is any problem with the import.
    """
    # Work out the module's absolute path and a suitable name.
    callerDict = _getCallerDict(callerDict)
    absModPath = _getModPath(modPath, cwd, callerDict)
    if name is None:
        modName = _makeModName(absModPath)
    else:
        modName = name

    # Try to find the module in the list of already loaded modules. If that
    # fails the perform the import.
    mod = _findImported(absModPath)
    if mod is None or doReload:
        try:
            f = open(absModPath)
        except IOError:
            raise ImportError("Could not open %r for reading" % absModPath)
        desc = (".py", 'r', imp.PY_SOURCE)

        # Do the actual import.
        try:
            mod = imp.load_module(modName, f, absModPath, desc)
        finally:
            f.close()

    # Emulate 'from X import *' if requrested.
    if star:
        try:
            names = mod.__all__
        except AttributeError:
            names = mod.__dict__.keys()
        for n in names:
            if not n.startswith("_"):
                callerDict[n] = getattr(mod, n)

    return mod


def findRoot(markerFileName=".PROJECT_ROOT"):
    """Find the root directory for a project.

    This function examines the current directory, is parent directory and the
    parent's parent directory, etc., until the `markerFileName` is found.

    :Note:
        The function will only look a maximum of 20 levels above the CWD.

    :Param markerFileName:
        The name of a file that is only expected to be found in the project's
        root directory. If you stick to the convention of having a file called
        '.PROJECT_ROOT' then you can omit this paramneter.
    :Return:
        The absolute path of the root directory or None if it could not be
        found.
    """
    workDir = ""
    for i in range(20):
        path = os.path.join(workDir, markerFileName)
        if os.path.exists(path):
            return os.path.abspath(workDir)
        workDir = os.path.join(workDir, "..")

    # FUTURE: The remainder of this function is for backward compatability. Eventually
    #         it should probably be removed.
    if markerFileName == ".PROJECT_ROOT":
        return findRoot("PROJECT_ROOT")
    return None


def addPathAtRoot(relPath, markerFileName=".PROJECT_ROOT"):
    """Add a directory to ``sys.path``, relative to the project root.

    This function finds the project root and the prefixes it to the `relPath`
    to obtain the absolute pathname. If this directory is not already in ``sys.path``
    then it is appended.

    :Param relPath:
        The name of a directory, relative to the project root directory.
    :Param markerFileName:
        The name of a file that is only expected to be found in the project's
        root directory. If you stick to the convention of having a file called
        '.PROJECT_ROOT' then you can omit this paramneter.
    """
    root = findRoot(markerFileName=markerFileName)
    fullPath = os.path.normpath(os.path.join(root, relPath))
    if fullPath not in sys.path:
        sys.path.append(fullPath)


def importAbove(pyFileName, star=False, mode="", cwd=False, startAbove=False):
    """Import a python file from here or some directory above.

    This function examines the current module's directory, its parent directory
    and the parent's parent directory, etc., until the named python file is
    found. If found, the module is imported as if it were a module found in
    ``sys.path``.

    You can use the ``cwd`` argument to start the search from the current
    working directory instead of the calling module's directory.

    :Param pyFileName:
        The name of a python file to be imported as a module. This should be a
        plain file name, without directory parts, but with the '.py' extension.
    :Param star:
        If ``True`` then the effect is similar to doing ``from X import *``.
    :Param mode:
        An alternative way of defining the import mode. Using ``mode="*"`` is
        the same as using ``start=True``. Currently only ``*`` is a valid mode
        character.
    :Param cwd:
        If ``False`` (the default) then the search starts in the directory that
        contains the calling module. If ``True`` then the search starts from
        the CWD.
    :Param startAbove:
        If ``True`` then the current module's directory is excluded from the
        search.

    """
    import inspect
    try:
        frame = inspect.stack()[1][0]
        callerDict = frame.f_globals
    finally:
        del frame

    if mode == "*":
        star = True
    workDir = ""
    if not cwd and callerDict:
        workDir = os.path.abspath(os.path.dirname(callerDict.get("__file__")))

    for i in range(20):
        if i > 0 or not startAbove:
            modPath = os.path.join(workDir, pyFileName)
            if os.path.exists(modPath):
                mod = importPath(modPath, cwd=True,
                        callerDict=callerDict, star=star)
                return mod
        workDir = os.path.join(workDir, "..")

    else:
        raise ImportError("Could not find %r module in any parent directory"
                % pyFileName)
