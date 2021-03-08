"""Test collection support.

"""
from __future__ import print_function
__docformat__ = "restructuredtext"

import builtins
import glob
import imp
import inspect
import os
import sys

from cleversheep3.Extras.decorator import decorator
from cleversheep3.Prog import Files
from cleversheep3.Sys import Platform
from cleversheep3.Test import ImpUtils
from cleversheep3.Test.Tester import Core
from cleversheep3.Test.Tester import Context
from cleversheep3.Test.Tester import Coordinator
from cleversheep3.Test.Tester import Errors
from cleversheep3.Test.Tester import testspec


# TODO: Put this in a sensible place. Possibly where intelliProp lives.
class PropertyError(Exception):
    pass


class Unsupported(Exception):
    """**TODO**"""


_loadedModules = {}
_doneFixups = False
_hooked = []
_import = None
_loading = None
_curScriptPackage = None


def _isTest(name, obj):
    debug = lambda *a: None
    if name == 'x':
        debug = print
    debug(f'{name=} {obj=}')
    try:
        info = getattr(obj, "cs_test_info", None)
    except:
        # This handles (for example) objects that over-ride __getattr__ in a
        # way that breaks here.
        return False

    if not hasattr(obj, "__call__"):
        return False

    if info is None:
        if name.startswith("test_"):
            info = Core.TestInfo()
            try:
                obj.cs_test_info = Core.TestInfo()
            except AttributeError:
                # Happens for some instance methods. We need to use the
                # underlying function.
                obj.__func__.cs_test_info = Core.TestInfo()
                obj.__func__.cs_test_info._test_seq = -1
            return True
        return False

    flags = info.cs_flags
    if "plat" in flags:
        if Platform.platformType not in flags["plat"]:
            return False

    try:
        info.cs_tags["cs_modPath"] = os.path.abspath(
                obj.__globals__["__file__"])
    except AttributeError:
        # The function may be a callable class instance.
        info.cs_tags["cs_modPath"] = os.path.abspath(
                obj.__call__.__globals__["__file__"])

    # if getattr(obj.__self__.__class__.cs_attrs, 'inherit_tests', False):
    #     return True
    return True
    return info.reserved_cs_flags['defined_in_base'] is obj.__class__


def formatImportFailure(name, exc):
    _execDir = ""
    import traceback
    s = []
    s.append("Error occurred importing %r" % name)
    s.append("%s" % exc)
    exc_type, exc_value, exc_traceback = sys.exc_info()
    #s.append("".join(traceback.format_tb(exc_traceback)))
    exTB = traceback.extract_tb(exc_traceback)
    for filename, line_number, function_name, text in exTB:
        if filename == _loading:
            filename = os.path.join(os.getcwd(), filename)
        filename = Files.relName(filename, _execDir)
        if filename.endswith("Test/Tester/Collection.py"):
            if function_name == "hookedImport":
                continue
    return "\n".join(s)


def hookedImport(name,  globals=None, locals=None, fromlist=None, *args, **kwargs):
    _hooked.append(name)
    context = Context.getContext()
    parent = context.package
    mod = None
    try:
        if parent is not None:
            subName = "%s.%s" % (parent.__name__, name)
            try:
                mod = _import(subName, globals, locals, fromlist, *args,
                        **kwargs)
                submod = getattr(mod, name, None)
                mod = sys.modules[subName]
            except Exception as exc:
                pass

        if mod is None:
            try:
                mod = _import(name, globals, locals, fromlist,
                        *args, **kwargs)
            except:
                raise
    finally:
        _hooked.pop()

    return mod


@decorator
def wrapImport(func, *args, **kwargs):
    global _import
    if _import is not None:
        return func(*args, **kwargs)

    _import, builtins.__import__ = builtins.__import__, hookedImport
    try:
        return func(*args, **kwargs)
    finally:
        builtins.__import__, _import = _import, None


def loadModule(path, doReload=False):
    """Load a test script as a module.

    This is used by the collectTree method.

    At entry, the CWD is the directory of the test module. The normal
    __import__ will also have been replace by the hookedImport funtion, which
    will attempt arrange for non-relative imports to work as expected.

    """
    relPath = Files.relName(path)
    context = Context.getContext()
    parentMod = context.package
    if parentMod is not None:
        modName = "%s.%s" % (parentMod.__name__,
                relPath.replace("/", ".")[:-3])
    else:
        modName = "%s" % (relPath.replace("/", ".")[:-3])
    if not doReload and path in _loadedModules:
        return _loadedModules[path]

    ns = {}
    here = os.getcwd()
    subDir = os.path.dirname(path)
    if subDir:
        os.chdir(subDir)

    global _loading, _curScriptPackage
    try:
        try:
            try:
                _loading = os.path.basename(path)
                _curScriptPackage = parentMod
                mod = imp.load_source(modName, os.path.basename(path))
            except Unsupported as exc:
                return
            except Exception as exc:
                print(formatImportFailure(modName, exc))
                print("Hmm", exc)
                raise
        except Unsupported:
            return
    finally:
        os.chdir(here)
    return mod


class Collection:
    """A collection of test objects.

    Actually this is currently little more than an ordered dictionary. The key
    is a test object's UID and each entry is ``(uid, object)``.

    Well, actually, it is now more complex. Only the tests are part of the
    ordered dictionary. The suites are just a dictionary, keyed by UID.

    """
    def __init__(self):
        self._tests = []
        self._dict = {}
        self._suites = {}
        self._testIDs = {}
        self._problems = {}
        self._pruned = False
        self.spec = testspec.TestSpecDB()

    def resetSuites(self):
        for suite in self._suites.values():
            suite.reset()

    def clearAllTestMarks(self, mark):
        for test in self._tests:
            test.clearMark(mark)

    def clearAllSuiteMarks(self, mark):
        for suite in self._suites.values():
            suite.clearMark(mark)

    def clearAllMarks(self, mark):
        selc.clearAllTestMarks()
        selc.clearAllSuiteMarks()

    def getItemByUid(self, uid):
        if uid in self._suites:
            return self._suites[uid]
        for test in self._tests:
            if test.uid == uid:
                return test

    def addProblem(self, uid, exc):
        self._problems[uid] = exc

    def addSuite(self, uid, suite):
        self._suites[uid] = suite
        suite.setCollection(self)
        self._pruned = False

    def addTest(self, test):
        self._tests.append(test)
        self._dict[test.uid] = test
        test.setCollection(self)
        assert len(self._tests) == len(self._dict)
        if test.testID:
            if test.testID in self._testIDs:
                sys.stderr.write("Warning: Duplicate testID %r\n"
                        % test.testID)
            self._testIDs[test.testID] = test
        self._pruned = False
        self.spec.gatherTestSteps(test.func)

    def numberTests(self):
        """Give each test a number."""
        for i, test in enumerate(self._tests):
            test.number = i + 1
            test.info.cs_test_num = test.number

    def parent(self, item):
        return self._suites.get(item.parentUid)

    def getAncestors(self, item, oldestFirst=False):
        if not item:
            return []
        parent, ancestors = item.parentUid, []
        while parent:
            suite = self._suites.get(parent, None)
            ancestors.append(suite)
            if suite:
                parent = suite.parentUid
        if not oldestFirst:
            ancestors.reverse()
        return ancestors

    def getLevel(self, test):
        return len(self.getAncestors(test))

    def __iter__(self):
        return iter(self._tests)

    def prune(self):
        if self._pruned:
            return
        #print "PRUNE"
        testSuites = [s.uid for s in list(self._suites.values()) if s.children]
        #for t in testSuites:
        #    print "SUITE", t
        toDel = []
        for problemUid, problem in self._problems.items():
            #print "PROBLEM", problemUid
            if problemUid not in testSuites:
                if isinstance(problem, Errors.SuiteNoDocstringError):
                    toDel.append(problemUid)
        for problemUid in toDel:
            #print "PRUNE", problemUid
            self._problems.pop(problemUid)
        self._pruned = True

    @property
    def suites(self):
        return self._suites.values()

    def getProblems(self):
        return self._problems.items()

    def hasFailures(self):
        for t in self._tests:
            if t.hasRunProblem:
                return True

    def select(self, select):
        for test in self._tests:
            select.matches(test)

    def diffAncestors(self, test, otherTest):
        """Get a list of differences between test ancestors.

        This gets the list of ancestor suites for each test and compares them
        in order to find the sequence of ``test``'s ancestors which are not
        ``otherTest``'s ancestors.

        :Parameters:
          test, otherTest
            The two tests to compare.
        :Return:
            A sequence of tuples ``(level, suite)`` of the different ancestors.
            The root suite for all tests has a ``level`` of zero.

        """
        ancestors = self.getAncestors(test)
        otherAncestors = self.getAncestors(otherTest)
        ret = list(enumerate(ancestors))
        while ancestors and otherAncestors:
            if otherAncestors.pop(0) is not ancestors.pop(0):
                break
            ret.pop(0)
        return ret

    def __len__(self):
        return len(self._tests)


def doCollect(collector, namespace, context, doReload=False, ignoreFiles=[]):
    collection = Collection()
    path = _getFile(namespace)
    uid = os.path.split(path), None, None
    if not namespace.get("__doc__", None):
        instance = Errors.SuiteNoDocstringError(None,
                "Module %r does not have a docstring" % (path))
        collection.addProblem(uid, instance)
    instance = Core.ModuleSuite(path, uid, None, context, namespace=namespace,
                                myDir=os.getcwd())
    collection.addSuite(uid, instance)
    try:
        collector(collection, namespace, instance, parent=uid, doReload=doReload,
                ignoreFiles=ignoreFiles)
    except Errors.DiscoveryError as exc:
        import sys
        sys.stderr.write("Discovery error\n%s\n%s" % exc.args)

    # Give each test its own number so they can be easily referred to on the
    # command line.
    collection.numberTests()

    return collection


def _getFile(namespace, abs=True):
    if abs:
        path = os.path.abspath(namespace["__file__"])
    else:
        path = namespace["__file__"]
    if path.endswith(".pyo") or path.endswith(".pyc"):
        path = path[:-1]
    return path


def collectFromNamespace(collection, instance, info, parent):
    """
    :Parameters:
      collection
        The collection of all tests and suites.
      instance
        The TODO
      info
        TODO
      parent
        The UID of the parent suite. This may be ``None``.

    """
    from cleversheep3.Test import Tester

    # First find any 'bare' tests within the namespace and and add each to the
    # collection, as a `Test` instance, in sorted order.
    # TODO: Change _getTestKey to avoid two loops.
    context = Context.getContext(dirPath=os.getcwd())
    tests = []
    for name, value in info.items():
        if _isTest(name, value):
            if not value.__doc__:
                uid = getSig(value)
                filePath = Files.relName(os.path.join(*uid[0]))
                collection.addProblem(uid,
                    Errors.TestNoDocstringError(None,
                        "Test %r in file %s does not have a docstring" % (
                            name, filePath)))
            tests.append((name, value))

    tests.sort(key=_getTestKey)
    for name, value in tests:
        uid = getSig(value)
        if isinstance(value, Errors.TestNoDocstringError):
            collection.addProblem(uid, value)
        test = Core.Test(value, uid, parent, context)
        try:
            funcSelf = test.func.im_self
        except AttributeError:
            funcSelf = None
        if hasattr(test.func, "cs_is_applicable"):
            if test.func.cs_is_applicable(funcSelf, test):
                collection.addTest(test)

    # Then find any test suite classes and sort into a local list. Once sorted,
    # recursively look for contained tests and suites.
    suiteEntries = sorted([(name, value)
            for name, value in info.items()
                if _isSuite(name, value)],
            key=_getSuiteKey)

    # Create a basic suite instance for each suite, plus UID.
    instances = []
    for name, value in suiteEntries:
        try:
            inst = value()
        except Unsupported:
            continue
        except TypeError:
            raise
        uid = getSig(inst, hints=Hints(klass=value))
        if not inst.__doc__:
            path = os.path.join(*uid[0])
            collection.addProblem(uid,
                Errors.SuiteNoDocstringError(None,
                    "Suite %r in file %s does not have a docstring" % (
                        name, Files.relName(path, cwd=Tester.execDir))))
            #assert 0
        instNamespace = dict((n, getattr(inst, n)) for n in dir(value))
        instNamespace.update(inst.__dict__)
        parentSuite = collection.getItemByUid(parent)
        suite = Core.ClassSuite(inst, uid, parent, context,
                                namespace=instNamespace,
                                myDir=parentSuite.myDir)
        instances.append((uid, suite))

    for uid, suite in instances:
        collection.addSuite(uid, suite)
        if isinstance(suite, Errors.DiscoveryError):
            continue
        collectFromNamespace(collection, suite, suite.namespace, parent=uid)
    return collection


def _getSuiteKey(v):
    name, suite = v
    if hasattr(suite, "_cs_suite_seq_"):
        return 0, suite._cs_suite_seq_
    return 1, name


def _getTestKey(v):
    name, func = v
    if hasattr(func, "cs_test_info"):
        return 0, func.cs_test_info._test_seq
    return 1, name


class Hints:
    def __init__(self, klass=None):
        self.klass = klass.__name__


# TODO: Both testspec.py and Collection.py use inspect for source code.
#       Would be nice to avoid doing the same thing twice.
def _getSource(obj, hints=None):
    source =  klass = name = None

    # Use any available hints in preference.
    if hints:
        klass = hints.klass

    # For instance methods we want the source of the bound class.
    cls = getattr(obj, "__class__", None)
    if cls is not None:
        try:
            src = inspect.getsourcefile(obj.__class__)
            return src
        except Exception as exc:
            pass

    # First, see if we can simply get the source using the object.
    src = None
    try:
        src = inspect.getsourcefile(obj)
        if src is None:
            # TODO: Really wierd stuff! Replace the next line with 'pass' and
            # on my PC this function returns ``None`` for some cases.
            print(">>>", src.__code__)
        return src
    except Exception as exc:
        pass

    # See if we can get source via the __class__ attribute.
    try:
        return inspect.getsourcefile(obj.__class__)
    except Exception as exc:
        pass

    # It could be this is decorated using decorator.py.
    while hasattr(obj, "undecorated"):
        obj = obj.undecorated
        try:
            src = inspect.getsourcefile(obj)
            if src is not None:
                return src
            return ret
        except Exception as exc:
            pass

    raise exc


def getSig(obj, hints=None):
    source = klass = name = None
    source = _getSource(obj, hints)
    sourceDir = os.path.dirname(os.path.abspath(source))

    # Use any available hints in preference.
    if hints:
        klass = hints.klass

    if inspect.isfunction(obj):
        # Use the name of plain functions.
        name = obj.__name__

    elif inspect.ismethod(obj):
        # Use the name and class name methods.
        name = obj.__func__.__name__
        klass = klass or obj.__self__.__class__.__name__

    else:
        # If the tester is being clever, then try for a function name.
        try:
            name = obj.__name__
        except AttributeError:
            pass

    return (sourceDir, source), klass, name


def _isSuite(name, klass):
    if name.startswith("__") or not inspect.isclass(klass):
        return
    if name.startswith("Test_"):
        return True
    if hasattr(klass, "_cs_suite_seq_"):
        try:
            v = int(klass._cs_suite_seq_)
            return True
        except (TypeError, ValueError):
            pass


class Provider(Coordinator.Provider):
    @wrapImport
    def collectTree(self, collection, namespace, instance, parent,
            doReload=False, level=0, ignoreFiles=[]):
        # Find all test modules in this directory.
        topNamespace = namespace
        path = _getFile(topNamespace)
        directory = os.path.dirname(path)
        scripts = sorted(glob.glob(os.path.join(directory, "test_*.py")))
        scripts = [s for s in scripts
                if os.path.basename(s) not in ignoreFiles]
        names = [Files.relName(n, cwd=directory) for n in scripts]

        # Discover the tests in each test module.
        modules = []
        for script, name in zip(scripts, names):
            context = Context.getContext(filePath=script)
            mod = loadModule(script, doReload)
            if mod is None:
                continue
            namespace = dict((n, getattr(mod, n)) for n in dir(mod))
            uid = os.path.split(script), None, None
            instance = Core.ModuleSuite(script, uid, parent, context,
                                        namespace=namespace, myDir=os.getcwd())
            instance._data_ = (mod, namespace, uid)
            modules.append(instance)

        modules = _orderModules(modules)
        for instance in modules:
            mod, namespace, uid = instance._data_
            if os.path.isabs(mod.__file__):
                mod.__abspath__ = mod.__file__
            else:
                mod.__abspath__ = os.path.join(directory, mod.__file__)
            collection.addSuite(uid, instance)
            collectFromNamespace(collection, mod, namespace, uid)
            del instance._data_

        # Now recursively find any ``all_tests.py`` scripts in sub-directories.
        exclDirs = topNamespace.get("_exclDirs_", [])
        exclDirs.extend([".git", ".svn", "CVS"])

        subdirs = sorted([p for p in os.listdir(directory)
            if os.path.isdir(p)])
        modules = []
        for subdir in subdirs:
            if subdir in exclDirs:
                continue
            subPath = os.path.join(directory, subdir)
            allPath = os.path.join(subPath, "all_tests.py")
            if os.path.exists(allPath):
                here = os.getcwd()
                os.chdir(subPath)
                modDir = os.getcwd()
                try:
                    context = Context.getContext(filePath=allPath)
                    mod = loadModule(allPath, doReload)
                    namespace = dict((n, getattr(mod, n)) for n in dir(mod))
                    uid = os.path.split(allPath), None, None
                    instance = Core.ModuleSuite(allPath, uid, parent, context,
                                                namespace=namespace,
                                                myDir=modDir)
                    instance._data_ = (mod, namespace, uid, os.getcwd())
                    modules.append(instance)
                finally:
                    os.chdir(here)

        modules = _orderModules(modules)
        for instance in modules:
            mod, namespace, uid, here = instance._data_
            os.chdir(here)
            collection.addSuite(uid, instance)
            self.collectTree(collection, namespace, instance, uid,
                    doReload, level=level+1, ignoreFiles=ignoreFiles)
            del instance._data_

        return collection

    @wrapImport
    def collectModule(self, collection, info, instance, parent,
            doReload=False, ignoreFiles=[]):
        return collectFromNamespace(collection, instance, info, parent)

    def doCollect(self, collector, namespace, doReload=False, ignoreFiles=[]):
        context = Context.getContext(dirPath=os.getcwd())
        return doCollect(collector, namespace, context, doReload=doReload,
                ignoreFiles=ignoreFiles)


def loadFixup():
    global _doneFixups

    if not _doneFixups:
        _doneFixups = True
        fixup = ImpUtils.findRoot("_fixup_.py")
        if fixup is not None:
            here = os.getcwd()
            try:
                os.chdir(ImpUtils.findRoot("_fixup_.py"))
                with open('_fixup_.py') as f:
                    code = compile(f.read(), '_fixup_.py', 'exec')
                    exec(code)
            finally:
                os.chdir(here)


def _orderModules(modules):
    class Node:
        def __init__(self, m, p):
            self.m = m
            self.p = p
            self.children = []

    # Create a set of nodes, all children of a root node.
    root = Node(None, None)
    k = {}
    for m in modules:
        pf = m.item
        k[pf] = Node(m, m.item)
        root.children.append(k[pf])

    # Reorganise into a DAG.
    for m in modules:
        pf = m.item
        n = k[pf]
        for pp in m.runAfter:
            if m.uid[0][-1] == "all_tests.py":
                ppp = os.path.abspath(os.path.join(
                            os.path.dirname(os.path.dirname(m.item)), pp,
                            "all_tests.py"))
            else:
                ppp = os.path.abspath(os.path.join(os.path.dirname(m.item), pp))
            child = k.get(ppp, None)
            if child is None:
                continue
            try:
                root.children.remove(child)
            except ValueError:
                pass
            n.children.append(child)

    ordered = []
    def _walk(t, seen, lev=0):
        if not t.children and t.p not in seen:
            if t is not root:
                ordered.append(t.m)
            seen[t.p] = None

        for child in sorted(t.children, key=lambda n:n.p):
            if child in seen:
                continue
            _walk(child, seen, lev+1)
            if child.p not in seen:
                seen[child.p] = None
                ordered.append(child.m)

    _walk(root, {})
    return ordered


provider = Provider()
Coordinator.registerProvider("cscore", ("collection", ), provider)
