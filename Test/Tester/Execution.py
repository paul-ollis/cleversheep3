"""Main execution control for the Tester.

"""
__docformat__ = "restructuredtext"


import sys
import optparse
import logging

import cleversheep3

from cleversheep3.Test.Tester import Coordinator
from cleversheep3.Test.Tester import Manager
from cleversheep3.Test.Tester import Errors

from cleversheep3.Test.Tester import Logging
from cleversheep3.Test.Tester import WatchDog
from cleversheep3.Test.Tester import CmdLine
from cleversheep3.Test.Tester import options
from cleversheep3.App import Config


# DEPRECATED
def coverageIsEnabled():
    """Return True if (python) coverage has been enabled for this test run."""
    return options.cover


#{ Command line and option support

_preTestFilterCallbacks = []
_postCollectionCallbacks = []
_optionsParsedCallbacks = []
_remArgs = []
userParser = optparse.OptionParser(usage=optparse.SUPPRESS_USAGE)
userParser.get_option("-h").help = optparse.SUPPRESS_HELP


def parseUserOptions(args):
    # TODO: Hack to get around a nasty circular dependency.
    from cleversheep3.Test import Tester

    userOptions, userArgs = userParser.parse_args(args)
    args[:] = userArgs
    Tester.userOptions = userOptions


def add_optionsParsedCallback(func):
    """Add a callback for when the command line options have been parsed.

    This allows a test script to register a function to be called immediately
    after the test framework has finished parsing the command line options. The
    function is invoked simply as ``func()``. You can register multiple
    functions, in which case they are invoked in the order they were
    registered.

    The callbacks are invoked immediately after any user options (those defined
    using ``add_option``) have been parsed.

    :Param func:
        The function to be invoked once the command line options have been
        parsed.

    """
    if func not in _optionsParsedCallbacks:
        _optionsParsedCallbacks.append(func)


def add_preTestFilterCallback(func):
    _preTestFilterCallbacks.append(func)


def add_postCollectionCallback(func):
    _postCollectionCallbacks.append(func)


def invokePreTestFilterCallbacks():
    for func in _preTestFilterCallbacks:
        func()


def invokePostCollectionCallbacks(collection):
    for func in _postCollectionCallbacks:
        func(collection)


# TODO: This seems to be in the wrong module. Something like discovery seems
#       more appropriate.
def add_option(*args, **kwargs):
    """Add a user (test writer) defined command line option.

    This function can be used to add extra command line options for a set of
    tests. This function takes exactly the same arguments as the `add_option
    <http://www.python.org/doc/2.4.4/lib/optparse-defining-options.html>`_
    method of Python's standard `optparse
    <http://www.python.org/doc/2.4.4/lib/module-optparse.html>`_ module.

    Options defined this way need to be separated on the command line
    from other options using the ``-z`` option. As in::

        $ ./test_something --keep-going -z --my-option

    """
    userParser.add_option(*args, **kwargs)


def rerunForCCoverage():
    # See if we can run tpython.
    code = os.system("tpython -c None")
    if code != 0:
        sys.exit("You need 'tpython' to support C code coverage")

    # OK. We seem to have a tpython so run as a sub-process using the --c2-cover
    # option.
    import sys
    import subprocess
    args = ["tpython"] + sys.argv[0:1] + ["--c2-cover"] + sys.argv[1:]
    proc = subprocess.Popen(args)
    proc.wait()

    # Then generate coverage information, by execing with the c3-cover option.
    args = ["python"] + sys.argv[0:1] + ["--c3-cover"] + sys.argv[1:]
    os.execvp("python", args)


def parseCoreOptions(features={}):
    parser = _createCoreOptionParser(features=features)
    opt, args = options._control.parse_args(parser)
    logger = Coordinator.getServiceProvider("logging")
    logger.setLogPath(options.log_file)
    log_level = options.log_level.lower()
    if log_level not in Logging.validLevels:
        sys.exit("Invalid '--log-level'\n"
                "Valid values are: %s" % " ".join(Logging.validLevels))
    # TODO: Would be cleaner to make the logger understand the names and lose
    #       the dependency on the standard logger module.
    logger.setLogLevel(getattr(logging, log_level.upper()))

    if options.c2_cover or options.c3_cover:
        pass
    elif options.c_cover:
        rerunForCCoverage()


def processOptions():
    if options.timeout:
        setDefaultTimeout(options.timeout)


def parseCommandLineOptions(features={}):
    # Parse command line. First pass is with the Tester's built-in options and then
    # a second pass looks for user-defined options.
    global args

    parser = _createMainOptionParser(features=features)

    # TODO: The rc-file processing should probably be done in __init__.py.
    rcpath, values = parseRc()
    if rcpath:
        options._control.addConfigFileValues(rcpath, values)
    _, args = options._control.parse_args(parser)
    args.extend(_remArgs)
    processOptions()
    parseUserOptions(args)
    if options.help:
        parser.print_help()
        parser.exit()

    # Allow test scripts the chance to react to the end of command line
    # processing. This is done before test selection because we allow
    # (but not encourage) the callbacks to modify the command line
    # arguments.
    for func in _optionsParsedCallbacks:
        func()

    CmdLine.parseTestSelections(args)


def getArgs():
    """Get the command line arguments.

    This function returns the command line arguments use when the tests
    were invoked. It can be used in a post-options parsed callback (see
    `add_optionsParsedCallback`) or any time thereafter. The result of
    calling it any earlier is undefined.

    The returned value is the actual list of arguments after all options
    have been parsed (and removed). You can modify this list and it will
    affect the arguments that the test framework sees.

    This allows very specialised test script argument processing. In
    particular, if you use this in a post-options parsed callback then
    any changes to the argument list will affect test selection.

    Using this to change the argument list after the post-options parsed
    callbacks have all been invoked has undefined effects; and you should then
    then treat the return value as read only.

    """
    global args
    return args


#}


#{ Global test execution control and querying support


# The writer of a test can arrange to get called back upon certain events
# occurring.
#
# - Once the command line options have been parsed.
# - At the end of a test run; i.e. all tests have run, whether they all passed
#   or not.
# - Just before the test framework is about to exit; i.e. the test framework
#   code has nothing else to do at all.
_testRunEndCallbacks = []
_testExitCallbacks = []


def add_testRunEndCallback(func):
    """Register a function to be invoked when a test run ends.

    The function is invoked after all tests have finished being executed.

    More than one function can be registered. The function is called with no
    arguments. You can register multiple functions, in which case they are
    invoked in the order they were registered.

    :Param func:
        The function to be invoked once the test run has ended.

    """
    if func not in _testRunEndCallbacks:
        _testRunEndCallbacks.append(func)


def add_test_exit_callback(func):
    """Register a function to be invoked just before exiting the test
    framework.

    More than one function can be registered. The function is called with no
    arguments. You can register multiple functions, in which case they are
    invoked in the order they were registered.

    :Param func:
        The function to be invoked once the test run has ended.

    """
    if func not in _testExitCallbacks:
        _testExitCallbacks.append(func)


def currentTestHasFailed():
    """Returns True if the current (just run) test has failed.

    This is intended to be used in tear down methods (``tearDown`` and
    ``suiteTearDown``). Some times if can be useful to behave differently when
    tearing down after a failed test - for example you might wish so save
    (rather than delete) temporary files.

    """
    manager = Coordinator.getServiceProvider("manager")
    return manager.executingTest.hasFailed


def setDefaultTimeout(timeoutPeriod):
    """Set the default watchdog timeout period.

    Tests can be run with a watchdog active to force tests to terminate after
    a specific time. This is useful, for example, in unattended overnight test runs
    where you wish to ensure that a non-terminating test run is treated as an error,
    so that subsequent test runs get a chance to execute.

    Normally the default timeout is ``None``; i.e. disabled.

    :Param timeoutPeriod:
        The watchdog timeout period in whole seconds.
    """

    options.timeout = timeoutPeriod


#}
#{ Test script entry points


import os


def currentTestInfo():
    manager = Coordinator.getServiceProvider("manager")
    try:
        test = manager.executingTest
    except (AttributeError, NameError):
        test = None
    if test is not None:
        return test.info


class General:
    """Base class for the General service.

    """
    features = {
    #    "c-cover": None,
    }

    def collectTests(self, collectMethod, info, ignoreFiles=[]):
        # Find a collector
        collector = Coordinator.getServiceProvider("collection")
        collectFunc = collector.getFunction(collectMethod)

        # TODO: Collection should possibly interact with the manager.
        try:
            sys.stdout.flush()
            collection = WatchDog.runUnderWatchDog(options.timeout,
                collector.doCollect, collectFunc, info,
                ignoreFiles=ignoreFiles)
        except WatchDog.Timeout as exc:
            sys.stderr.write("Timout during test collection\n")
            sys.stderr.write(Errors.fmtException(exc) + "\n")
            sys.exit(1)

        fail = False
        collection.prune()
        for uid, exc in collection.getProblems():
            sys.stderr.write("Test loading error\n%s\n" % exc)
            fail = True
        if fail:
            sys.exit(1)

        invokePostCollectionCallbacks(collection)
        return collection


class CSGeneral(Coordinator.Provider, General):
    """A general to command the test troops.

    """
    features = {
        "c-cover": None,
    }

    def __init__(self):
        pass

    def bootStrap(self, collectMethod, info):
        """Run the test framework.

        This will perform the test collection phase and then hand over control
        to a test manager [TODO: The manager concept may disappear].

        Currently, only the default built in manager is supported. In the
        future this will behave differently depending on which manager has been
        selected.

        """
        # Perform a minimal command line option parsing in order to establish
        # things like which manager is being used. Then create the manager
        # object.
        parseCoreOptions(features=self.features)
        manager = Coordinator.getServiceProvider("manager")
        logging = Coordinator.getServiceProvider("logging")

        # Collect the tests, which can result in more command options being
        # defined.
        collection = self.collectTests(collectMethod, info)

        # Now do a full parsing of the command line options.
        parseCommandLineOptions(features=self.features)
        logging.set_columns(options.columns)
        invokePreTestFilterCallbacks()

        manager.loadJournal()
        manager.setCollection(collection)
        manager.addSelector(options.select)

        logger = Coordinator.getServiceProvider("logging")

        if options.c3_cover:
            sources = []
            for t in manager._collection:
                sources.extend(t.sourcesUnderTest)
            sources = sorted(dict((n, None) for n in sources).keys())

            from cleversheep3.Test import Gcov
            print
            Gcov.main(sources)
            return

        if options.no_action:
            manager.null_action()
            return
        elif options.times or options.all_times:
            manager.listTimes()
            return
        elif options.summary:
            manager.summarise()
            return
        elif options.list_ids:
            manager.listIDs()
            return
        elif options.list_modules:
            manager.listModules()
            return
        elif options.list_no_ids:
            manager.listIDs(no_ids=True)
            return
        elif options.sphinx:
            manager.sphinx()
            return
        elif options.list_no_ids:
            manager.listIDs(no_ids=True)
            return
        elif options.details:
            manager.detail()
            return
        elif options.ids_summary:
            manager.show_ids()
            return

        logger.start()
        exitCode = manager.run()

        # Perform one-time tidy up.
        for func in _testExitCallbacks:
            try:
                func()
            except:
                pass

        # TODO: What is this for????
        if options.c3_cover:
            return exitCode

        return exitCode


Coordinator.registerProvider("cscore", ("general",), CSGeneral())


#}
#{ Suspect stuff

class MainOptionParser(Config.SlackOptionParser):
    def format_help(self, formatter=None):
        mainHelp = optparse.OptionParser.format_help(self, formatter)
        userHelp = userParser.format_help(formatter)
        userHelp = "\n".join(userHelp.splitlines()[1:])
        return mainHelp + "\nAdditional User Options:\n" + userHelp + "\n"

usage = "usage: %prog [options] [test-nums ...]"

def parseRc():
    """Parse the user's ``.cstesterrc`` file, if it exists.

    """
    configFile = Config.ConfigFile()
    path = os.path.expanduser("~/.cstesterrc")
    try:
        f = open(path)
    except IOError:
        return None, configFile
    d = {}
    exec(f.read(), d, d)

    for name, value in d.items():
        if name.startswith("_"):
            continue
        setattr(configFile, name, value)
    return path, configFile


def _doUserOptions(option, opt, value, parser):
    remArgs[:] = parser.rargs
    parser.rargs[:] = []


def _createCoreOptionParser(parser=None, features={}):
    logging = Coordinator.getServiceProvider("logging")
    if parser is None:
        parser = MainOptionParser(usage)
        parser.remove_option("-h")

    parser.add_option("--log-file", action="store",
        default="test.log", metavar="PATH",
        help="Set the log file to PATH (default = test.log)")
    parser.add_option("--log-level", action="store",
        default="debug", metavar="LEVEL",
        help="Set the logging level LEVEL (default = debug)."
             " Valid values: %s" % " ".join(Logging.validLevels))
    parser.add_option("--timeout", action="store", type="int",
        metavar="T", default=0,
        help="Timeout the test run after T seconds")

    if "c-cover" in features:
        parser.add_option("--c-cover", action="store_true",
            help="Do C/C++ code coverage.")

        # These are use internally when providing automated C coverage.
        parser.add_option("--c2-cover", action="store_true",
            help=optparse.SUPPRESS_HELP)
        parser.add_option("--c3-cover", action="store_true",
            help=optparse.SUPPRESS_HELP)

    return parser


def addDebugOptions(parser):
    group = optparse.OptionGroup(parser, "Debugging Options",
        "Useful when debugging problems with tests.")
    parser.add_option_group(group)

    group.add_option("--full-stack", action="store_true",
        help="Print full stack traceback for test failures.")
    group.add_option("--full-inner-stack", action="store_true",
        help="Print full inner stack traceback for test failures.")
    group.add_option("--partial-inner-stack", action="store_true",
        help="Print partial inner stack traceback for test failures.")
    group.add_option("--all-diffs", action="store_const", const=None,
        dest="num_diffs",
        help="Show all differences when strings do not match")
    group.add_option("--num-diffs", action="store", type="int", default=1,
        metavar="N",
        help="Display N differences when strings do not match (default=1)")
    group.add_option("--fail-on", action="store", type="int", default=-1,
        metavar="N", help="Make each test fail on the Nth asstertion")


def addDocumentationOptions(parser):
    group = optparse.OptionGroup(parser, "Documentation Options",
        "For generating documentation from tests.")
    parser.add_option_group(group)
    group.add_option("--details", action="store_true",
        help="Dump a detailed list of the loaded tests")
    group.add_option("--list-ids", action="store_true",
        help="List the IDs of matching tests")
    group.add_option("--list-modules", action="store_true",
        help="List the modules of matching tests")
    group.add_option("--list-no-ids", action="store_true",
        help="List tests without test IDs")
    group.add_option("--sphinx", action="store",
        metavar="DIR",
        help="Generate documention in Sphinx format DIR")
    group.add_option("--doc-root", action="store", default=None,
        metavar="PATH",
        help="Set documentation root to PATH (default=Use full paths)")


def addObsoleteCoverageOptions(parser):
    group = optparse.OptionGroup(parser, "Obsolete Coverage Options",
        "Do not use.")
    parser.add_option_group(group)
    group.add_option("-e", "--erase", action="store_true",
        help="Erase existing coverage data")
    group.add_option("-r", "--report", action="store_true",
        help="Display coverage report")
    group.add_option("-a", "--annotate", action="store_true",
        help="Created annotated source")
    group.add_option("-c", "--cover", action="store_true",
        help="Run under coverage")
    group.add_option("--cov-self", action="store_true",
        help="Do not exclude the test framework from coverage")


def addCoverageOptions(parser):
    try:
        import coverage
    except ImportError:
        return
    group = optparse.OptionGroup(parser, "Coverage Options")
    parser.add_option_group(group)
    group.add_option("--coverage", action="store_true",
        help="Enable coverage support")


def addJournalOptions(parser):
    group = optparse.OptionGroup(parser, "Journalling Options")
    parser.add_option_group(group)
    group.add_option("--enable-journal", action="store_true",
        help="Enable the long-term journal.")


def addCommonOptions(parser):
    parser.add_option("--summary", action="store_true",
        help="Dump a summary of the loaded tests")
    parser.add_option("--ids-summary", action="store_true",
        help="Like summary, but include test IDs.")
    parser.add_option("-i", "--ignore-case", action="store_true",
        help="Ignore case when searching test descriptions")
    parser.add_option("--skip-passed", "--resume", action="store_true",
        help="Resume execution, skipping all previously passed tests")
    parser.add_option("--run-disabled", action="store_true",
        help="Try to run disabled tests as well")
    parser.add_option("--run-broken", action="store_true",
        help="Run tests marked as broken")
    parser.add_option("--keep-going", action="store_true",
        help="Keep going when a test fails.")
    parser.add_option("--list-tested", action="store_true",
        help="List the modules being tested")
    parser.add_option("--patch-subprocess", action="store_true",
        help="Patch sub-process functions to provide status output")
    parser.add_option("--add-status-comment", action="append",
        default=[],
        help="Define additional comments used for status line,"
             " in addition to the standard '#>' form")
    parser.add_option("--show-status", action="store_true",
        help="Run with a status line")
    parser.add_option("--log-file", action="store",
        default="test.log", metavar="PATH",
        help="Set the log file to PATH (default = test.log)")
    parser.add_option("--log-level", action="store",
        default="debug", metavar="LEVEL",
        help="Set the logging level LEVEL (default = debug)."
             " Valid values: %s" % " ".join(Logging.validLevels))
    parser.add_option("--no-times", action="store_true",
        help="Do not put time stamps in the log file.")
    parser.add_option("--columns", action="store", type="int",
        metavar="COL",
        help="Try to restrict output to COL columns (min=60)")
    parser.add_option("--unsorted", action="store_true",
            help="Do not sort tests into numeric order."
                 "\nMust provide test numbers on command line.")
    parser.add_option("--random", action="store", type="int", default=0,
          metavar="N",
          help="Use N as seed for random test execution order (default=0)"
               "\nThe default of zero implies no randomisation."
               "\nA negative number means seed using system time."
               "\nA positive number means seed using N.")

    parser.add_option("--max-exec-time", action="store", type="float",
        metavar="T", default=0.0,
        help="Try to avoid running tests that take longer than T seconds.")
    parser.add_option("--times", action="store_true",
            help="List average execution times for selected tests")
    parser.add_option("--all-times", action="store_true",
            help="List all execution times for selected tests")
    parser.add_option("--timeout", action="store", type="int",
        metavar="T", default=0,
        help="Timeout the test run after T seconds")

    parser.add_option("-q", "--quiet", action="store_true",
        help="Only report pass, fail, etc. Omit details of failures.")
    parser.add_option("-n", "--no-action", action="store_true",
        help="Do not perform any actions, but still invoke registered reporters")

    parser.add_option("--pure", action="store_true",
        help=optparse.SUPPRESS_HELP)


def addDelimOption(parser):
    parser.add_option("-z", action="callback", callback=_doUserOptions,
        help="Marks end of general options")


def _createMainOptionParser(features={}):
    logging = Coordinator.getServiceProvider("logging")
    parser = MainOptionParser(usage)
    parser.remove_option("-h")

    parser.add_option("-h", "--help", action="store_true",
        help="Show this help message and exit")
    parser.add_option("", "--uids", action="append", default=[],
        help="Select IDs to be run. Use multiple options and or comma"
             "separated list.")
    parser.add_option("", "--modules", action="append", default=[],
        help="Select modules to be run. Use multiple options and or comma"
             "separated list. Partial names will match.")
    addCommonOptions(parser)
    addDocumentationOptions(parser)
    #addCoverageOptions(parser)
    addJournalOptions(parser)
    addDebugOptions(parser)

    if "c-cover" in features:
        parser.add_option("--c-cover", action="store_true",
            help="Do C/C++ code coverage.")
        # TODO: Are these ever used?????
        parser.add_option("--c-erase", action="store_true",
            help="Erase old C/C++ coverage data")
        parser.add_option("--c-all", action="store_true",
            help="Count all lines for coverage, including unreachable.")

        # These are use internally when providing automated C coverage.
        parser.add_option("--c2-cover", action="store_true",
            help=optparse.SUPPRESS_HELP)
        parser.add_option("--c3-cover", action="store_true",
            help=optparse.SUPPRESS_HELP)

    addDelimOption(parser)

    return parser

#}
