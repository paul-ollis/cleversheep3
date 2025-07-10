#!/usr/bin/env python
"""Support for handling actual files.

This module provides the following classes.

  - `Stat`. This is a mixin, which provides clean access to information about
    files.

"""
__docformat__ = "restructuredtext"

import os
import stat
import re
import fnmatch

from cleversheep3.Prog.Aspects import decorator

# TODO: This breaks if no .PROJECT_ROOT exists.

#: The projectRoot is used to determine the relative path of file names. This
#: attribute can be modified by users of this module.
try:
    projectRoot = os.getcwd()
except OSError:
    # In rare cases, the CWD may have been deleted.
    projectRoot = ""


_rModePart = re.compile(r'([ugoa])([+=-])([rwx]+)$')

_bitMap = {
        "ur": 0o400,
        "uw": 0o200,
        "ux": 0o100,
        "gr": 0o040,
        "gw": 0o020,
        "gx": 0o010,
        "or": 0o004,
        "ow": 0o002,
        "ox": 0o001,
        "ar": 0o444,
        "aw": 0o222,
        "ax": 0o111,

        "u":  0o077,
        "g":  0o707,
        "o":  0o770,
        "a":  0o000,
    }


def _listize(p):
    if isinstance(p, str):
        return [p]
    return p


def chmod(path, mode):
    """Changes the mode flags of a file, using ASCII notation.

    This provides something closer to the *Unix* chmod command.
    The mode should be a string that is simliar to the 'chmod' command
    string, for example 'u+w,o-w'.

    Currently only 'rwx' attributes are supported.

    :Param path:
        The path of the file whose mode you want to alter.
    :Param mode:
        Either a number, as you wuld supply to the chmod system call or
        a string, as described above.

    :Return:
        None, None
           Unable to get the current mode of the file.
        mode, 0
            Mode changed successfully. The *mode* is the original mode of the
            file.
        mode, -1
            Unable to set the new mode.
        mode, -2
            An error in the mode's format.
    """
    try:
        st = os.stat(path)
    except OSError:
        return None, None

    origMode = fMode = stat.S_IMODE(st.st_mode)
    if isinstance(mode, str):
        parts = [s.strip() for s in mode.split(",")]
        for s in parts:
            m = _rModePart.match(s)
            if not m:
                return origMode, -2

            role, op, flags = m.groups()

            bits = 0
            for f in flags:
                bits |= _bitMap[role+f]

            if op == "+":
                fMode |= bits
            elif op == "-":
                fMode &= ~bits
            else:
                fMode = (fMode & _bitMap[role]) | bits
    else:
        fMode = mode

    try:
        os.chmod(path, fMode)
    except OSError:
        return origMode, -1

    return origMode, 0


def rmFile(path, parentDir=None):
    """Remove a file if it exists.

    :Param path:
        The path name of the file.
    :Param parentDir:
        The file's parent directory. If supplied then this is prepended to eh
        `path`.
    """
    if parentDir:
        path = os.path.join(parentDir, path)
    if os.path.exists(path):
        os.unlink(path)


# TODO: I am not happy with this. It probably should **really** check that the
#       directory is empty. It was added to support Mym's cache.
def rmEmptyDir(path):
    """Remove the directory `path` if it is empty.

    This will try to remove a directory, failing silently if the directory
    is not empty.

    Actually this is a bit of a cheat. All it really does is try to remove the
    directory and suppress error conditions. Thus, failure could be for a
    reason other than the directory not being empty.

    :Return:
        True if the directory was removed, a false value otherwise.
    :Param path:
        The path of the directory to be removed.

    """
    try:
        os.rmdir(path)
    except OSError as exc:
        return False
    return True


def relName(path, cwd=None, root=None):
    """Return pathname relative to `cwd`.

    If possible, returns a relative pathname for path. The rules are:

       1. If the file is in or below `cwd` then a simple relative name is
          returned. For example: 'dir/fred.c'.

       2. If both the file and `cwd` are in or below `root` then a relative
          path is also generated, but it will contain double dots. For
          example: '../../dir/fred.c'.

       3. If neither (1) or (2) applies then the absolute path is returned.

    :Param cwd:
       Used as the current directory. It defaults to ``{os.getcwd()``.
    :Param root:
       Defines the root directory, which determines whether a relative
       pathname can be returned. It defaults to ``projectRoot``.
    """
    relRoot = os.path.normpath((root or projectRoot)) + os.sep
    cwd = os.path.abspath((cwd or os.getcwd())) + os.sep
    if path == cwd or path == cwd[:-1]:
        return "."

    if path.startswith(cwd):
        # The relative name is below the CWD, so we simply strip off the
        # leading parts.
        return path[len(cwd):]

    if path.startswith(relRoot) and cwd.startswith(relRoot):
        # The path is below the nominal root but parallel to the CWD. We need
        # to add some '../' parts.
        relToRootPath = path[len(relRoot):]
        relToRootCWD = cwd[len(relRoot):-1]
        count = 0
        while count < 1000 and relToRootCWD and relToRootCWD != os.sep:
            relToRootCWD, b = os.path.split(relToRootCWD)
            relToRootPath = ".." + os.sep + relToRootPath
        assert count < 1000
        return relToRootPath

    return path


# TODO: Should probably move to Utils.
def normPath(path, parentDir):
    """Return a normalised absolute path for path.

    If the path is not an absolute name then the parentDir is used.
    """
    if not os.path.isabs(path):
        path = os.path.join(parentDir, path)
    return os.path.normpath(os.path.abspath(path))


def findInPathSets(path, *pathSets, **kwargs):
    """See if `path` can be found in any of a sequence of `pathSets`.

    :Param path:
        The pathname to look for.
    :Param pathSets:
        One or more pathSets to look in. Each pathSet must sequence
        (or iterable) of absolute directory names.
    :Return:
        A tuple of ``(fullPath, dirName, setIdx)``. The ``setIdx`` indicates
        which set dirName was found. If the path was not found then fullPath
        will be ``None`` and you should ignore the other values.
    """
    exists = kwargs.pop("exists", None)
    if exists is None:
        exists = os.path.exists
    if os.path.isabs(path):
        return None, None, 0
    for i, pathSet in enumerate(pathSets):
        for dirName in pathSet:
            fullPath = os.path.join(os.path.abspath(dirName), path)
            fullPath = os.path.normpath(fullPath)
            if exists(fullPath):
                return fullPath, dirName, i
    return None, None, 0


class Stat:
    """Mixin: Provides limited wrapping of os.stat and os.path.

    This mixin expects to access a file's absolute path as ``self.path``.
    This absolute path should not be quoted or in any other way escaped.
    """
    def relName(self, cwd=None, root=None):
        """If possible, return pathname, relative to cwd.

        :Param cwd:
           If supplied, will be used instead of ``os.getcwd()``
        :Param root:
           If supplied then this over-rides the default ``projectRoot``

        """
        return relName(self.path, cwd, root)

    def relDir(self, cwd=None, root=None):
        """If possible, return pathname, relative to cwd of files file's directory.

        This is basically equivalent to
        :<py>:

            os.path.dirname(self.relName(cwd, root))

        except that it will return '.' rather than an empty string.

        :Param cwd:
           If supplied, will be used instead of ``os.getcwd()``
        :Param root:
           If supplied then this over-rides the default ``projectRoot``

        """
        return os.path.dirname(self.relName(cwd, root)) or "."

    def relHead(self, cwd=None, root=None):
        """Returns the base part (without the extension) of the name."""
        return os.path.splitext(self.relName(cwd, root))[0]

    def projName(self):
        """Do not use!

        """
        # TODO: Find a better name
        return self.relName(cwd=projectRoot)

    def mode(self):
        """Return the protection mode bits of this file."""
        st = os.stat(self.path)
        return stat.S_IMODE(st.st_mode)

    def lmode(self):
        """Return the protection mode bits without following links."""
        if self.islink():
            st = os.lstat(self.path)
        else:
            st = os.stat(self.path)
        return stat.S_IMODE(st.st_mode)

    def getmtime(self):
        """Return the modification time of this file."""
        if self.exists():
            return os.path.getmtime(self.path)
        return 0
    mtime = getmtime

    def getlmtime(self):
        """Return the modification time of this link.

        This must only be used if the file is a symbolic link.
        """
        if self.islink() and self.lexists():
            st = os.lstat(self.path)
            return st.st_mtime
        return Stat.getmtime(self)

    def exists(self):
        """Return True if the file currently exists.

        If the path refers to a symlink, then the links are followed to see if
        the actual file exists.
        """
        # TODO: What about broken sym-links?
        return os.path.exists(self.path)

    def lexists(self):
        """Return True if the file currently exists and is a symbolic link.

        This must only be used if the file is a symbolic link.
        """
        return os.path.lexists(self.path)

    def isfile(self):
        """Returns True if the file exists and is a plain file."""
        return os.path.isfile(self.path)

    def isdir(self):
        """Returns True if the file exists and is a directory."""
        return os.path.isdir(self.path)

    def islink(self):
        """Returns True if the file is a symbolic link."""
        return os.path.islink(self.path)

    def getsize(self):
        """Returns the size of the file.

        @Todo:
            What if the file does not exist.
        """
        return os.path.getsize(self.path)

    # TODO: We could optimize by caching some of the following.
    def ext(self):
        """Returns the extension (including dot) of the name."""
        return os.path.splitext(self.path)[1]

    def head(self):
        """Returns the base part (without the extension) of the name."""
        return os.path.splitext(self.path)[0]

    def dir(self):
        """Returns the directory part of the name."""
        return os.path.dirname(self.path)

    def base(self):
        """Returns the base (last) part of the name."""
        return os.path.basename(self.path)
    basename = base

    def isBelowDir(self, dirPath):
        """Check whether this file is in or below ``dirPath``.

        :Return:
            True if this file appears to be in this ``dirPath`` or any
            directory below it.
        :Param dirPath:
            The path to the directory to be checked.

        """
        rel = self.relName(dirPath)
        if rel[0] not in "."+ os.sep:  # TODO: Not portable
            return True

    def isInDir(self, dirPath): #pragma: unsupported
        """Do not use!"""
        return self.dir() != os.path.abspath(dirPath)



class File(Stat):
    """Uses the `Stat` mixin to provide abstract access to a file.

    This is a demonstration of how to use the `Stat` mixin, but also useable in
    its own right,

    """
    #: This provides the 'path' attribute that the Stat mixin requires.
    path = property(fget=lambda o:o._path)

    def __init__(self, path):
        """Constructor:

        :Param path:
            The path of the file to be queried/manipulated. This may be
            relative (to the CWD) or absolute. It is converted to an absolute
            path internally.
        """
        self._path = os.path.abspath(path)

    def __str__(self):
        return self.relName()


def iterGlobTree(rootDir, inclFiles=["*"], exclFiles=[],
        inclDirs=["*"], exclDirs=[], stripCount=0):
    """Generator: Same as `globTree`, but returns an iterator.

    """
    exclFiles = set(_listize(exclFiles))
    inclFiles = set(_listize(inclFiles))
    exclDirs = set(_listize(exclDirs))
    inclDirs = set(_listize(inclDirs))

    def inclFilter(names, patterns):
        matches = []
        for p in patterns:
            matches.extend(fnmatch.filter(names, p))
        return matches

    def exclFilter(names, patterns):
        toExcl = set()
        for p in patterns:
            toExcl.update(set(fnmatch.filter(names, p)))
        return [n for n in names if n not in toExcl]

    exclDirs.update(set(["CVS", ".svn", ".git"]))
    for dirpath, dirnames, filenames in os.walk(rootDir):
        filenames[:] = inclFilter(filenames, inclFiles)
        filenames[:] = exclFilter(filenames, exclFiles)
        dirnames[:] = inclFilter(dirnames, inclDirs)
        dirnames[:] = exclFilter(dirnames, exclDirs)

        selection = [os.path.join(dirpath, n) for n in filenames]
        if stripCount:
            selection = [stripDirs(p, stripCount) for p in selection]
        for el in selection:
            yield el


def globTree(rootDir, inclFiles=["*"], exclFiles=[],
        inclDirs=["*"], exclDirs=[], stripCount=0):
    """Performs a glob over an entire tree.

    This walks the directory tree starting at the root, descending into all
    directories that match ``inclDirs``, but do not match ``exclDirs``.

    :Param rootDir:
        The directory to start looking in.
    :Param inclFiles, exclFiles:
        Optional lists of glob patterns to include and exclude files. You
        can also supply a string if there is only one pattern; e.g. you can use
        ``"*.java"`` instead of ``["*.java"]``.
    :Param inclDirs, exclDirs:
        Optional lists of glob patterns to include and exclude sub-directories.
        The search does not descend into any directories that does not get
        selected. As for `inclFiles` and `exclFiles`, you can uses strings
        for single patterns.
    :Param stripCount:
        Strip the specified number of leading directory names from the
        list of returned file paths.
    """
    return list(iterGlobTree(rootDir, inclFiles=inclFiles, exclFiles=exclFiles,
        inclDirs=inclDirs, exclDirs=exclDirs, stripCount=stripCount))


def stripDirs(path, count):
    """Strip count directory parts from the path."""
    # TODO: This is a hack and not robust.
    parts = path.split(os.sep)
    return os.sep.join(parts[count:])


def findDirAbove(dirName):
    """Find a directory with the given name by scanning parent directories.

    This function examines the current directory, its parent directory and the
    parent's parent directory, etc., until the `dirName` is found.

    :Note:
        The function will only look a maximum of 20 levels above the CWD.

    :Param dirName:
        The name of the directory to look for.
    :Return:
        The absolute path of the directory or None if it could not be
        found.
    """
    workDir = ""
    for i in range(20):
        path = os.path.join(workDir, dirName)
        if os.path.exists(path):
            return os.path.abspath(path)
        workDir = os.path.join(workDir, "..")

    return None

# Deprecated version of findDirAbove
findDir = findDirAbove

def pathComponents(path):
    """Split a path into its components.

    :Return:
        A tuple of the main components of `path`. The returned tuple contains:

            drive
                This is something like 'C:' or None.
            [dir1, [dir2...]]
                The individual directory components.
            name
                The final component, which may be a directory of some other type
                of file.

    Note:
        Drive letters are not yet supported. In fact this probably breaks on
        non-UNIX-like systems.

    """
    parts = [p for p in path.split(os.path.sep) if p not in ["", "."]]
    return parts


def isSubDir(parent, child):
    """Determine whether `child` is a sub-dir of `parent`.

    :Param parent:
    :Param child:
    """
    pParts = pathComponents(os.path.abspath(parent))
    cParts = pathComponents(os.path.abspath(child))
    if len(pParts) < len(cParts):
        return cParts[:len(pParts)] == pParts


def mkDir(path):
    """Make sure the directory `path` exists.

    It is OK to call this if `path` already exists.

    :Param path:
        The path of a directory.
    :Raises OSError:
        As for ``os.makedirs``.
    """
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except OSError:
            # In a race between two threads, this thread may have lost,
            # in which case the directory will now exist. Otherwise this
            # is a real exception.
            if not os.path.exists(path):
                raise


def mkParentDir(path):
    """Make sure the directory for `path` exists.

    For example, ``mkParentDir(a/b/c/x.cpp)`` will create the
    directory ``a/b/c`` if it does not already exist.

    :Param path:
        The path of a file, which does not need to exist.
    :Raises OSError:
        As for ``os.makedirs``.
    """
    parentDir = os.path.dirname(path)
    if parentDir:
        return mkDir(parentDir)


def parentOrThisDir(path):
    """Get nearest directory for a path.

    :Param path:
        The path of a directory or a file in the directory you want.

    :Return:
        If `path` is a directory then simply return it. Otherwise return the
        directory part of `path`.
    """
    if not os.path.isdir(path):
        path = os.path.dirname(path)
    return path


def _regIncFilter(seq, regExp):
    if regExp is not None:
        r = re.compile(regExp)
        seq = [el for el in seq if r.match(el)]
    return seq


def filesAndDirs(rootDir, fileRegExp=None, dirRegExp=None, exclDirs=[]):
    """Get the files and directories in `rootDir`.

    :Param rootDir:
        The path of a the directory to be queried.
    :Param fileRegExp:
        A regular expression used to match file names. May be ``None`` to
        match all files.
    :Param dirRegExp:
        NOT CURRENTLY USED.
        A regular expression used to match directory names. May be ``None`` to
        match all directories.
    :Param exclDirs:
        NOT CURRENTLY USED.
    :Return:
        A tuple of (file_list, dir_list). The entries in each list are base
        names, i.e. they contain no directory separators.
    """
    paths = os.listdir(rootDir)
    filenames = [p for p in paths if os.path.isfile(os.path.join(rootDir, p))]
    dirnames = [p for p in paths if os.path.isdir(os.path.join(rootDir, p))]

    filenames = _regIncFilter(filenames, fileRegExp)
    return filenames, dirnames
