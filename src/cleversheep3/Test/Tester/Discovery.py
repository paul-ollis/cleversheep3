"""Test discovery support.

TODO

"""
__docformat__ = "restructuredtext"


import os
import inspect

from cleversheep3.Test import ImpUtils

#: DEPRECATED: This stores the names of all python module source files that are
#: defined to be under test. It is used to generate coverage reports.
modules_under_test = {}


def addModulesUnderTest(pathOrPaths, moduleDir=None):
    """Used to manually define which Python modules are being tested.

    This is used internally by the Tester framework, but you can also use it
    directly if necessary. All the specified modules are noted so that, when
    running with coverage enabled, the framework knows which modules should be
    used in any generated coverage reports.

    It is more common to simply defined the modules being tested using the
    global variables ``modules_under_test`` and/or ``module_under_test``. These
    are normally put near the top of a test script.

    :Parameters:
      pathOrPaths
        This can be the name of a single Python module or a list of names.

       moduleDir
        This can be used to specify that the module(s) in ``pathOrPaths`` are
        not in the current working directory.

    """
    if not pathOrPaths:
        return
    if isinstance(pathOrPaths, str):
        paths = [pathOrPaths]
    else:
        paths = pathOrPaths
    moduleDir = moduleDir or os.getcwd()
    for path in paths:
        if path is None:
            continue
        if not os.path.isabs(path):
            path = os.path.abspath(os.path.join(moduleDir, path))
        modules_under_test[path] = None
