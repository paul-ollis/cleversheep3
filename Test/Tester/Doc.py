"""Documentation support for tests.

The cleversheep3 test framework provides support for generating documentation
from test scripts. This is achieved using the docstrings for the scripts,
classes and tests, plus stylised comments within the test functions themselves.


How tests are documented
========================

Any test method, class or module *must* contain some documentation. At the
very least, each must provide a docstring. As in:<py>:

    #!/usr/bin/env python
    '''A collection of tests.'''
    from cleversheep3.Test.Tester import *

   class Suite_A(Suite):
        '''The first suite'''
        @test
        def check_a(self):
            '''A test'''
            # ...

    class Suite_B(Suite):
        '''The second suite'''
        # ...

The framework does not allow you to omit these docstrings [#]_. They are used in
the basic output during test runs and for the test log.


Basic docstring format
----------------------

A docstring consists of two parts, following the basic PEP-8 guidelines. First
there is a short, preferably one or two line summary. The summary is used to
announce each test suite and test during a test run.

Optionally, following the summary you can add any amount of detail. A blank
line separates the summary from the details section.

The framework assumes that you will use reStucturedText formatting for your
test documentation [#]_.


Stylised comments specification
-------------------------------

Currently the only special comment form looked for is
:<py>:

    #> Some procedure details.

All such comments are collected and presented as a desciption of the procedure
carried out by the test.

.. [#] If is is important enough to test then it is important enough have
       documented tests.

.. [#] At some later date support for alternatives may be added, but for now
       it is easiest to support a single markup format in order to be able to
       generate high quality output.

"""
from __future__ import print_function
__docformat__ = "restructuredtext"


import inspect
import sys
import os

from cleversheep3.Test.Tester import Logging, Suites, Fixture
from cleversheep3.Prog import Files

class _Struct: pass


def _lineBlocks(s):
    prev_i = -1
    block = []
    for i, line in s:
        if i - prev_i > 1:
            if block:
                yield block
            block = []
        block.append(line.rstrip())
        prev_i = i

    if block:
        yield block


def _getTestProcedureComments(lines):
    for i, rawLine in enumerate(lines):
        line = rawLine.strip()
        if not line.startswith("#>"):
            continue
        yield i, line[2:]


def _getTestProcedure(testFunc):
    """Extract test procedure details from a test function, using
    introspection.

    :Param testFunc:
        The actual test script function, typically a method of a
        :obj:`Suite<Test.Tester.Suites.Suite>`.

    """
    try:
        lines, lineNumber = testFunc.getSourceLines()
    except IOError:
        # Source could not be read by ``inspect``.
        lines = ["# TEST SOURCE COULD NOT BE READ"]
        lineNumber = 0
        # Logging.sEmph.write("No source for %r\n" % testFunc)
    for block in _lineBlocks(_getTestProcedureComments(lines)):
        yield block


def putTitle(f, t, uc):
    f.write("\n%s\n%s\n\n" % (t, uc * len(t)))


class Detailer(Fixture.Visitor):
    """A visitor that displays detailed information about the tests."""
    def doEnterSuite(self, suite):
        """Invoked when the walker enters a suite.

        This outputs the top level detailed information about a test suite.

        """
        if suite.getState() in Fixture._disabledConditions:
            return
        title = "Suite: %s" % (self.title)
        Logging.sTitle.write("\n%s\n" % (title))
        Logging.sTitle.write("%s\n" % ("=" * len(title)))
        src = enumerate(self.docLines)
        for i, l in src:
            if not l.strip():
                break
        for i, l in src:
            Logging.sNormal.write("  %s\n" % l)

    def doEnterTest(self, test):
        """Invoked when the walker enters a suite.

        This outputs the detailed information about an individual test,

        """
        if test.getState() in Fixture._disabledConditions:
            return
        for i, l in enumerate(Fixture.getDocLines(test.doc)):
            if i > 0:
                Logging.sNormal.write("      %s\n" % l)
            else:
                Logging.sTitle.write("\n%-4d  %s\n" % (
                    self.cmdLineNumber, l))
        for i, block in enumerate(_getTestProcedure(test.func)):
            #if i:
            #    Logging.sEmph.write("\n")
            for l in block:
                Logging.sEmph.write("        %s\n" % l)

        if i > 0:
            Logging.sNormal.write("\n")
        klass = test.getClass()
        path = test.moduleFile
        name = test.name
        if path:
            Logging.sEmph.write("      Path:     %s\n" % (path))
        if klass:
            Logging.sEmph.write("      Class:    %s\n" % (klass.__name__))
        if name:
            Logging.sEmph.write("      Function: %s\n" % (name))


class SphinxDocOutline(Fixture.Visitor):
    """A visitor to build a test suites documntation in Sphinx format.

    Sphinx is the documentation generation too that creates the offical
    Python documentation. It is also used by many other projects.

    """
    def __init__(self, *args, **kwargs):
        super(SphinxDocOutline, self).__init__(*args, **kwargs)
        Files.mkDir("sphinx")
        self.stack = []
        self.testsStack = []
        self.suiteData = []

    def docFunc(self, f, tpl, t):
        return
        f.write(tpl % t.data)
        l = len(t.proc)
        if l:
            putTitle(f, "Details", "~")
            for i, p in enumerate(t.proc):
                for li, line in enumerate(p):
                    line = line.rstrip()
                    prefix = ""
                    if li == 0:
                        prefix = "%d." % (i + 1)
                    f.write("%-3s %s\n" % (prefix, line))
                f.write("\n")

    def doEnterSuite(self, suite):
        print("DOC SUITE", type(suite), type(suite.inst), type(suite.inst._obj))
        print("         ", suite.summary)
        return
        if suite.getState() in Fixture._disabledConditions:
            return

        d = _Struct()
        d = {
            "cases": [],
            "title": self.title,
            "uline": "=" * len(self.title),
            "body": [],
            "setUp": [],
        }
        src = iter(self.docLines)
        for l in src:
            if not l.strip():
                break
        d["descr"] = "\n".join(src)

        if len(self.stack) == 0:
            tpl = _sphinx_index_head
            path = "sphinx/index.rst"
        else:
            tpl = _sphinx_suite_head
            rel_path = suite.symbolicName() + ".rst"
            path = os.path.join("sphinx", rel_path)
            f = self.stack[-1]
            f.write("   %s\n" % rel_path)
        print("GEN", path)

        f = open(path, "w")
        f.write(tpl % d)
        self.stack.append(f)
        self.testsStack.append({})

        s = {
            "setUp": None,
            "tearDown": None,
            "suiteSetUp": None,
            "suiteTearDown": None,
        }
        self.suiteData.append(s)
        if suite.setUp is not Fixture.nop:
            s["setUp"] = self.getXDoc(suite, "setUp")
        if suite.setUp is not Fixture.nop:
            s["tearDown"] = inspect.getdoc(suite.tearDown)
        if suite.setUp is not Fixture.nop:
            s["suiteTearDown"] = inspect.getdoc(suite.suiteTearDown)
        if suite.setUp is not Fixture.nop:
            s["suiteSetUp"] = inspect.getdoc(suite.suiteSetUp)

    def doLeaveSuite(self, suite):
        return
        if suite.getState() in Fixture._disabledConditions:
            return

        tests = self.testsStack.pop()
        f = self.stack.pop()
        detailed = []
        others = []

        for n, d in sorted(tests.items()):
            if not d.data["descr"]:
                others.append((n, d))
            else:
                detailed.append((n, d))

        if detailed:
            f.write(".. contents::\n")
            f.write("   :depth: 3\n\n")

        s = self.suiteData.pop()
        for func, title in (
            ("suiteSetUp", "Suite set up"),
            ("suiteTearDown", "Suite tear down"),
            ("setUp", "Per-test set up"),
            ("tearDown", "Per-test tear down"),
        ):
            continue
            doc = s[func]
            if not doc:
                continue
            putTitle(f, title, "=")
            for li, line in enumerate(doc.splitlines()):
                line = line.rstrip()
                prefix = ""
                if li == 0:
                    prefix = "%d." % (li + 1)
                f.write("%-3s %s\n" % (prefix, line))
            f.write("\n")

        if others:
            tpl = _sphinx_test_title_only
            putTitle(f, "Undocumented tests", "=")
            for n, t in others:
                f.write(tpl % t.data)

        if detailed:
            tpl = _sphinx_test_head
            putTitle(f, "Detailed tests", "=")
            for n, t in detailed:
                self.docFunc(f, _sphinx_test_head, t)

        return
        d.data["body"] = "\n".join(d.data["body"])
        f = open(d.path, "w")
        f.write(d.tpl % d.data)
        f.close()

    def doEnterTest(self, test):
        """Invoked when the walker enters a test.

        This outputs the detailed information about an individual test,

        """
        return
        if test.getState() in Fixture._disabledConditions:
            return
        f = self.stack[-1]
        d = self.testsStack[-1][test.cmdLineNumber] = _Struct()
        d.data = {
            "number": test.cmdLineNumber,
            "title": self.title,
            "uline": "-" * len(self.title),
        }
        src = iter(self.docLines)
        #src = iter(Fixture.getDocLines(test.doc))
        for l in src:
            if not l.strip():
                break
        d.data["descr"] = "\n".join(test.details)
        d.proc = list(_getTestProcedure(test.func))
        #self.stack[-1].data["cases"].append(d)

    def doLeaveTest(self, test):
        """Invoked when the walker leaves a test.

        This outputs the detailed information about an individual test,

        """

    def getXDoc(self, obj, name):
        import re
        rBaseInit = re.compile(r' *super *\( *([A-Za-z_]+) *, *self *\) *. *setUp *\(')

        f = getattr(obj, name, None)
        if f is None:
            return
        doc = inspect.getdoc(f)
        lines, lnum = f.getSourceLines()
        for l in lines:
            m = rBaseInit.match(l)
            if m:
                klass = f.getClass()
                for b in inspect.getmro(klass):
                    if b.__name__ == m.group(1):
                        bfunc = getattr(b, name, None)
                        print("---", name, m.group(1), bfunc)
                kk = inspect.getmro(klass)
                print("   ", klass, kk)
        return inspect.getdoc(f)

class XSphinxDoc(Fixture.Visitor):
    """A visitor that generates documentation in Sphinx format.

    Sphinx is the documentation tool used to generate the Python documentation.
    For an example see: http://docs.python.org/.

    Sphinx can be found at: http://sphinx.pocoo.org/.

    """
    def __init__(self, *args, **kwargs):
        import shutil
        super(SphinxDoc, self).__init__(*args, **kwargs)
        Files.mkDir("sphinx")
        shutil.copy("conf.py", "sphinx/conf.py")
        self.tests = {}
        self.stack = []

    def doEnterSuite(self, suite):
        """Invoked when the walker enters a suite.

        This outputs the top level detailed information about a test suite.

        """
        if suite.getState() in Fixture._disabledConditions:
            return
        d = _Struct()
        self.stack.append(d)
        if len(self.stack) == 1:
            d.tpl = _sphinx_index
            d.path = "sphinx/index.rst"
        else:
            d.tpl = _sphinx_suite
            d.path = "sphinx/stuff.rst"

        d.data = {
            "cases": [],
            "title": self.title,
            "uline": "=" * len(self.title),
            "body": [],
        }

        src = iter(self.docLines)
        for l in src:
            if not l.strip():
                break
        d.data["descr"] = "\n".join(src)

    def doLeaveSuite(self, suite):
        d = self.stack.pop()
        d.data["body"] = "\n".join(d.data["body"])
        f = open(d.path, "w")
        f.write(d.tpl % d.data)
        f.close()

    def doEnterTest(self, test):
        """Invoked when the walker enters a suite.

        This outputs the detailed information about an individual test,

        """
        if test.getState() in Fixture._disabledConditions:
            return
        d = self.tests[test.cmdLineNumber] = _Struct()
        d = _Struct()
        d.data = {
            "number": test.cmdLineNumber,
            "title": self.title,
            "uline": "-" * len(self.title),
        }
        src = iter(self.docLines)
        #src = iter(Fixture.getDocLines(test.doc))
        for l in src:
            if not l.strip():
                break
        d.data["descr"] = "\n".join(test.details)
        self.stack[-1].data["cases"].append(d)

        return
        for i, block in enumerate(_getTestProcedure(test.func)):
            #if i:
            #    Logging.sEmph.write("\n")
            for l in block:
                Logging.sEmph.write("        %s\n" % l)

        if i > 0:
            Logging.sNormal.write("\n")
        klass = None
        try:
            path, klass, method = test.uid()
        except ValueError:
            path, method = test.uid()
        if path:
            Logging.sEmph.write("      Path:     %s\n" % (path))
        if klass:
            Logging.sEmph.write("      Class:    %s\n" % (klass))
        if klass and method:
            Logging.sEmph.write("      Method:   %s\n" % (method))
        elif method:
            Logging.sEmph.write("      Function: %s\n" % (method))


_sphinx_index_head = """
%(uline)s
%(title)s
%(uline)s

This test spec was automatically generated by the cleversheep3 test framework.

This is the top-level suite.

%(descr)s

Suites in this test tree:

.. toctree::
   :maxdepth: 1

"""

_sphix_index_tail = """

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
"""

_test_tpl = """
%(title)s
%(uline)s

%(descr)s

"""


_sphinx_suite_head = """
%(uline)s
%(title)s
%(uline)s

%(descr)s

"""


_sphinx_suite_tail = """
Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
"""


_sphinx_test_head = """
%(title)s
%(uline)s

%(descr)s

"""


_sphinx_fixture_head = """
%(title)s
%(uline)s

%(descr)s

"""


_sphinx_test_title_only = """
**%(title)s**

"""


_sphinx_test_tail = """
"""
