"""The cleversheep3 services API descriptions.

This is not a real module, but it does provide template classes for each type
of service provider used in the cleversheep3 test framework.

"""

class Collector:
    """Provides collection (discovery) of tests.

    """
    def collectModule(self, collection, namespace, instance, parent):
        pass

    def collectTree(self, collection, namespace, instance, parent):
        pass

    def doCollect(self, collector, namespace, inoreFiles=[]):
        pass


class Logger:
    """Provide core logging.

    This should provide log function like error, warning, etc.

    """


class LogReporter:
    def critical(self, fmt, *args):
        pass

    def error(self, fmt, *args):
        pass

    def warn(self, fmt, *args):
        pass

    def info(self, fmt, *args):
        pass

    def debug(self, fmt, *args):
        pass

    def write(self, s):
        pass

    def writelines(self, lines):
        pass

    def announceSuiteStart(self, summary, result=None):
        pass

    def announceSuiteEnd(self, summary):
        pass

    def announceTestStart(self, number, summary, result=None):
        pass

    def putResult(self, result, itemType=None):
        pass

    def setCommentary(self, s):
        pass

    def setField(self, name, s):
        pass

    def setDelayLeft(self, rem):
        pass

    def setProgress(self, n, m):
        pass

    def setMode(self, mode):
        pass


class General:
    """A general to command the test troops.

    The highest rank of test commander.

    [Of course, being British, I was tempted to use FieldMarshal, but General
    is probably the most senior rank that springs to the mind of most people.
    Besides, a hierarchy that continued General, Lieutenant General, Major
    General, Brigadier, Colonel, Lieutenant Colonel, Major, *etc*. isn't likely
    to be easy to remember for most. (Yes I Googled it.)]

    """
    def bootStrap(self, collectMethod, namespace):
        """Run the test in bootstrap mode.

        Bootstrap mode is when a user executes a test script directly from the
        command line.

        :Parameters:
          collectMethod
            A string defining the method to use to collection the tests suite.
            There are two methods:

            collectModule
                Used when the script being bootstrapped is a self contained
                suite of tests.

            collectTree
                Typically used when the script is an ``all_tests.py`` script,
                which wants to (recusively) discovert tests within a directory
                tree.

          namespace
            The top-level namespace that provides suites and/or tests. This is
            where the collector will look for ``Suite`` classes and test
            methods.

        """


class Manager:
    """A test manager.

    This class defines the basic abstraction of a test manager. Various tester
    functions need access to a manager, for example the `collectModule`
    function.

    TODO: Make the above correct.

    Within a GUI, the manager would be something akin to the 'controller'. And
    the ``ui`` passed to the constructor is something akin to the 'view'.

    """
    def __init__(self):
        pass

    def selectedTests(self):
        pass

    def setField(self, name, s):
        pass

    def run(self):
        pass

    def setSelector(self, selector):
        pass

    def setCollection(self, collection):
        pass

    def summarise(self):
        pass


class StatusLine:
    """The status line output for executing tests.

    """
    def stop(self):
        pass

    def start(self):
        pass

    def setField(self, name, text):
        pass

    def setDelayLeft(self, seconds):
        pass

    def setCommentary(self, text):
        pass

    def setElapsed(self, seconds):
        pass


def getInterfaceMethods(klass):
    names = []
    for name in dir(klass):
        if name.startswith("_"):
            continue
        if not hasattr(getattr(klass, name), "__call__"):
            continue
        names.append(name)
    return names

statusLineMethods = getInterfaceMethods(StatusLine)
