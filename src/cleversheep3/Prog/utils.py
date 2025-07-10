"""A dumping ground."""

import sys
import os


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

    This is intended to typically be used in _fixup_.py.
    """
    here = os.getcwd()
    srcParent = os.path.dirname(os.path.dirname(here))
    modDir = os.path.join(srcParent, "src")
    if modDir not in sys.path:
        sys.path[0:0] = [modDir]


def _getProjectDir(projectName):
    here = os.getcwd()
    srcParent = os.path.dirname(os.path.dirname(here))
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
