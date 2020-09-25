from cleversheep3.Prog import Aspects

import functools
import inspect
import os
import sys

from cleversheep3.Prog import Files


class Partial:
    """Enhanced form of functools.partial.

    This allows the arguments to be modified, using `update`, before the
    partial function is invoked
    """
    def __init__(self, func, *args, **kwargs):
        self._partial = functools.partial(func, *args, **kwargs)

    def update(self, *args, **kwargs):
        args = self._partial.args + args
        keywords = self._partial.keywords
        keywords.update(kwargs)
        self._partial = functools.partial(self._partial.func, *args,
                                          **keywords)

    def __call__(self, *args, **kwargs):
        return self._partial(*args, **kwargs)


class TrackerSet(set):
    """Set class that activiely tracks additions.

    This is for debugging - *not* general use please. In particular, do not
    expect the API to be particularly stable. If you put into your application
    and the application breaks in the future - tough!
    """
    def __init__(self, *args, **kwargs):
        super(TrackerSet, self).__init__(*args, **kwargs)
        self._triggers = {"add": []}

    def add(self, v):
        for matcher, action in self._triggers["add"]:
            if matcher(v):
                action(v)
        super(TrackerSet, self).add(v)

    def addTrigger(self, matcher, action):
        self._triggers["add"].append((matcher, action))


def dumpStack(level=1, incCS=False, f=None, exclude=()):
    """Print a clean stack trace back.

    This tries to make the stack easier to follow by:

    - Hiding cleversheep3 entries.
    - Hiding '<string>' entries.
    - Keeping file names relative to the 'suite' directory.
    - Keeping the output compact.

    The result is a lie, but normally more readily useful. It is only intended
    to be used for debugging.
    """
    import traceback, os, sys
    from io import StringIO

    cwd = os.path.dirname(os.path.dirname(__file__))
    stack = traceback.extract_stack()
    data = []
    maxLen = 0
    s = StringIO()
    for filename, lineNumber, functionName, text in stack[:-level]:
        if not incCS and "/cleversheep3/" in filename:
            continue
        if filename == "<string>":
            continue
        skip = False
        for candidate in exclude:
            if candidate in filename:
                skip = True
                break
        if skip:
            continue
        location = "%s:%d %s" % (
            Files.relName(filename, cwd), lineNumber, functionName)
        data.append((location, text))
        maxLen = max(len(location), maxLen)

    s.write("Stack dump:\n")
    for location, text in data:
        s.write("    %-*s - %s\n" % (maxLen, location, text))

    f = f or sys.stdout
    f.write("%s\n" % s.getvalue())


def getCallerDict():
    frame = None
    try:
        frame = inspect.stack()[2][0]
        return frame.f_globals
    finally:
        del frame


def trimLines(lines, stats=False):
    """Remove leading and trailing blank lines from a seqence of lines.

    :Parameters:
      lines
        The lines to be trimmed. May be a sequences or generator.
      stats
        If supplied and true then trimmed lines statistics are include in the
        return value.

    :Return:
        If ``stats`` is true then a tuple of::

            ``(trimmed-lines, (before, after))``

        where ``before`` is the number of leading blank lines and ``after`` the
        number of trailing blank lines. Otherwise just the trimmed list of
        lines is returned.
    """
    lines = list(lines)
    before, after = 0, 0
    while lines and not lines[0].strip():
        lines.pop(0)
        before += 1
    while lines and not lines[-1].strip():
        lines.pop()
        after += 1
    if stats:
        return lines, (before, after)
    return lines


def trimText(text):
    """Remove leading and trailing blank lines from a block of text.

    Like `trimLines`, but takes a multi=line string rather than a sequenc of
    lines.
    """
    return "\n".join(trimLines(text.splitlines()))


class preserveCWD:
    """Context manager to undo and os.chdir calls.

    The current working directory in effect before context entry is restored
    when the context exits.
    """
    def __enter__(self):
        self._saveCWD = os.getcwd()

    def __exit__(self, type, value, traceback):
        os.chdir(self._saveCWD)


class temporaryCWD(preserveCWD):
    """Context manager to temporarily change the current working directory.

    The CWD is chaged when the context is entered. The current working
    directory in effect before context entry is restored when the context exits.
    """
    def __init__(self, targetDirectory):
        self._targetDirectory = targetDirectory

    def __enter__(self):
        super(temporaryCWD, self).__enter__()
        os.chdir(self._targetDirectory)


def loadCSMeta(dirPath='.'):
    meta = {
        'requires': (),
    }
    metaPath = os.path.join(dirPath, '.cs-meta')
    if os.path.exists(metaPath):
        d = {}
        with open(metaPath) as f:
            code = compile(f.read(), metaPath, 'exec')
            exec(code, d, )
        meta.update(d)
    return meta


def addThisProjectSourceToSysPath():
    """Add the source directory of the project to sys.path.

    This is intended to typically be used in _fixup_.py, when os.getcwd() will
    typically be <project-dir>/test and the 'test' sub-directory is at the same
    level as the 'src' sub-directory.
    """
    here = os.getcwd()
    srcParent = os.path.dirname(here)
    modDir = os.path.join(srcParent, "src")
    if modDir not in sys.path:
        sys.path[0:0] = [modDir]


def _getProjectDir(projectName):
    here = os.getcwd()
    srcParent = os.path.dirname(here)
    devDir = os.path.dirname(srcParent)
    return os.path.join(devDir, projectName)


def addProjectSourceToSysPath(projectName):
    """Add the source directory of a project to sys.path.

    This is intended to typically be used in _fixup_.py.
    """
    projDir = _getProjectDir(projectName)
    modDir = os.path.join(projDir, "src")
    if modDir not in sys.path:
        sys.path[0:0] = [modDir]


def addDependenciesToSysPath(dirPath='.'):
    loaded = set()
    meta = loadCSMeta(dirPath)
    loaded.add(os.path.abspath(dirPath))
    for required in meta['requires']:
        addProjectSourceToSysPath(required)
        projDir = _getProjectDir(required)
        if projDir not in loaded:
            loaded.add(projDir)
            addDependenciesToSysPath(projDir)


def findFileAbove(filename):
    """Find the root directory for a project.

    This function examines the current directory, is parent directory and the
    parent's parent directory, etc., until the `filename` is found.

    :Note:
        The function will only look a maximum of 20 levels above the CWD.

    :Param filename:
        The name of a file that is only expected to be found in the project's
        root directory. If you stick to the convention of having a file called
        '.PROJECT_ROOT' then you can omit this paramneter.
    :Return:
        The absolute path of the root directory or None if it could not be
        found.
    """
    workDir = ""
    for i in range(20):
        path = os.path.join(workDir, filename)
        if os.path.exists(path):
            return os.path.abspath(path)
        workDir = os.path.join(workDir, "..")


def _getCallerDict(level=2):
    frame = None
    try:
        frame = inspect.stack()[level + 1][0]
        return frame.f_globals
    finally:
        del frame
