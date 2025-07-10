#!/usr/bin/env python
"""The various functions that can be used to check results.

This module provides all the built-in test assertions of the cleversheep3 test
framework. Test assertions tend to follows a common pattern, which is::

    failUnless<assertion> (<expect>, <actual>, makeMessage=None, msg=None)

But there are some exceptions, such as `fail` and `failIf`. However all
assertions should take the ``makeMessage`` and ``msg`` arguments.
Unfortunately, there are currently some exceptions to this rule.

"""
__docformat__ = "restructuredtext"

import os
import re

_reType = type(re.compile(""))

from cleversheep3.TextTools import Diff
from cleversheep3.Test.Tester import options
from cleversheep3.Test.Tester import UlpCompare
from cleversheep3.Test.Tester import Errors

_cs_assertion_ = None

def _normaliseRe(expr):
    """Normalise a regular expression.

    :Parameters:
      expr
        This can be a string or an already compiled regular expression.

    :Return:
        If ``expr`` is a compiled regular expression then it it returned
        unchanged. Otherwise ``expr`` is compiled and the resulting compiled
        expression is returned.

    """
    if type(expr) != _reType:
        return re.compile(expr) # Just re.error propagate.
    return expr


def _oldShowStringDiffs(asserter, expect, actual, **kwargs):
    """Indicate the differences between two strings.

    :Parameters:
      expect, actual
        The expected and actual strings.
      kwargs
        Currently just the getTitle keyword argument is supported.

    :Keyword getTitle:
        If provided, this must be a function that can be called with zero
        arguments. It must return a string, which is used to provide a title line
        for the returned string.

    :Return:
        A string showing all the lines in the expected and actual strings. Where
        the lines differ, they are marked with a leading ``>`` character.

    """
    getTitle = kwargs.pop("getTitle", None)
    expectLines = expect.splitlines(1)
    actualLines = actual.splitlines(1)
    if getTitle:
        s = [getTitle()]
    else:
        s = ["The two strings do not match"]
    for hdr, lines, altLines in (
            ("Expected", expectLines, actualLines),
            ("Actual", actualLines, expectLines)):
        s.append("%s:" % hdr)
        for i, l in enumerate(lines):
            prefix=" "
            if i >= len(altLines) or l != altLines[i]:
                prefix = ">"
            s.append("  %4d:%s%r" % (i + 1, prefix, l))

    return "\n".join(s)


def _showStringDiffs(asserter, expect, actual, **kwargs):
    """Indicate the differences between two strings.

    :Parameters:
      expect, actual
        The expected and actual strings.
      kwargs
        Currently just the getTitle keyword argument is supported.

    :Keyword getTitle:
        If provided, this must be a function that can be called with zero
        arguments. It must return a string, which is used to provide a title line
        for the returned string.

    :Return:
        A string showing all the lines in the expected and actual strings. Where
        the lines differ, they are marked with a leading ``>`` character.

    """
    try:
        data = asserter.data[0]
    except IndexError:
        return _oldShowStringDiffs(asserter, expect, actual, **kwargs)

    getTitle = kwargs.pop("getTitle", None)
    expectLines = expect.splitlines(1)
    actualLines = actual.splitlines(1)
    if getTitle:
        s = [getTitle()]
    else:
        s = ["The two strings do not match"]
    diffCount = 0
    for before, after in data:
        s.append("== expected " + ("=" * 67))
        for i, cc, text, marks in before:
            s.append("%3d:%s %s" % (i, cc, text))
            if marks:
                s.append("%3s   %s" % (" ", marks))
        s.append("-- actual   " + ("-" * 67))
        for i, cc, text, marks in after:
            s.append("%3d:%s %s" % (i, cc, text))
            if marks:
                s.append("%3s   %s" % (" ", marks))
        s.append("")
        diffCount += 1
        if diffCount == options.num_diffs:
            break

    return "\n".join(s)


def _showFloatDiffs(asserter, expect, actual, **kwargs):
    """Indicate the differences between two floats.

    :Parameters:
      expect, actual
        The expected and actual float.
      kwargs
        ignored.

    :Return:
        A string showing why the float values differ.

    """
    ulpDiff = UlpCompare.ulpFloatDifference(expect, actual)
    return "Floating-point values not equal: %r != %r ULPs=%r\n" % (
            repr(expect), repr(actual), ulpDiff)


class Assertion:
    """Generic assertion management class.

    Assertions functions are based on instances of this (callable) class. This
    ensures a basic framework for creating assertions functions.

    A test assertion is used to check that some expected condition holds
    ``True``. For example, to check for an expected value, we do::

        failUnlessEqual(expect, actual)

    The processing of an assertion has a number of distinct actions:

    1. The condition is checked. If it is met then no further processing
       occurs.
    2. A (possibly quite detailed) descriptions of the failure is generated.
    3. An `Errors.Failure` exception is created and raised, using the message
       generated in step 2.

    For consistency, all assertion methods should to follow a common form of
    prototype::

        assertion (cond-args, [message], **kwargs)

    Where:

      *cond-args*
          These depend on the assertion. In the extreme case of `fail` there
          are no cond-args.

      *message*
          For simple cases this provides a simple description of why the test
          failed. Long term, this may become deprecated in favour of the
          keyword form ``message=string``.

          Note that the official name for this argument is ``message``. Older
          versions of the framework also permitted ``msg``, but this is now
          deprecated.

      *kwargs*
          All other arguments should be keyword arguments. The exact keyword
          arguments accepted depend on the specific assertion function, but
          some are common.

          *makeMessage*
            This should be a function that can be invoked with zero arguments.
            It should return a string, which may consist of multiple lines.

            This is only invoked in the event that a test fails.

            Use this in preference to the ``message`` argument when the time to
            generate the message is significant; i.e. it would otherwise
            noticably slow down a test run where all tests pass.

          *augmentMessage*
            This is like makeMessage, but it is passed a single string parameter
            which is the default message generated by the particular assertion.

    There is a convention that expected results should appear before actual
    results. For example::

        failUnlessEqual (expected, actual)

    """
    _spoofFail = -1

    def __init__(self, autoMessage=None, checkMethod=None,
                 extendedAutoMessage=None):
        """Construct:

        :Param autoMessage:
            The simple automatic message source. This can be a simple string or
            a function that takes no arguments. In the latter case the function
            will be called in the event of failure and should return a string.
        :Param checkMethod:
            The method to be invoked to verify that the ``cond-args`` pass;
            i.e. the test does **not** fail.
        :Param extendedAutoMessage:
            The extended automatic message source. This is always a function
            that can take arguments. The arguments provided are those that
            follow the ``cond-args``.

            Note that your should use either ``autoMessage`` or
            ``extendedAutoMessage``. The effects of using both are undefined.

        """
        self._checkMethod = checkMethod
        self._autoMessage = autoMessage
        self._extendedAutoMessage = extendedAutoMessage
        self.data = []

    @classmethod
    def reset(klass):
        klass._spoofFail = options.fail_on

    @classmethod
    def failOn(klass, count):
        klass._spoofFail = count

    def check(self, *args, **kwargs):
        if hasattr(self._checkMethod, "__call__"):
            return self._checkMethod(self, *args, **kwargs)
        return False, (), args

    def describeFailure(self, usedArgs, remArgs, kwargs):
        """Generate a string describing the failure in some detail.

        :Parameters:
          usedArgs
            The arguments use by the assertion when determining that faiure has
            occurred.
          remArgs
            The non-positional arguments that were ignore when determining that
            faiure has occurred.
          kwargs
            Additional keyword argument pairs.

        :Keywords:
          message, msg
            A fixed string to use as the failure message.
          makeMessage
            A function to invoke to create the failure message. If supplied then
            the message/msg argument is not used.
          augmentMessage
            An additional function which will be invoked to modify the failure
            message. This is invoked with the already created message.

        """
        # For evolutionary reasons a number of options are supported:
        #
        # - The argument message or msg may be a plain string.
        # - Or, a function that returns a string.
        # - Or the makeMessage argument, if supplied is invoked to get the
        #   string.
        #
        # I would not do it the same way again.
        message = kwargs.pop("message", None) or kwargs.pop("msg", None)
        makeMessage = kwargs.pop("makeMessage", None)
        if makeMessage is not None:
            try:
                message = makeMessage()
            except Exception as exc:
                message = "!! Cannot correctly describe failure !!"
                message += "\nThe function %r raised the exception" % makeMessage
                message += "\n    %r" % exc
        if message is None:
            # See if we have a spare argument, which will be taken as the message.
            if remArgs:
                message, remArgs = remArgs[0], remArgs[1:]
        if message is not None:
            try:
                message = message()
            except TypeError:
                pass
        if message is None:
            if self._extendedAutoMessage:
                message = self._extendedAutoMessage(self, *usedArgs, **kwargs)
            elif hasattr(self._autoMessage, "__call__"):
                message = self._autoMessage(usedArgs, remArgs, kwargs)
            else:
                message = self._autoMessage

        augmentMessage = kwargs.pop("augmentMessage", None)
        if augmentMessage is not None:
            origMessage = message
            try:
                message = augmentMessage(message)
            except Exception as exc:
                message = "!! Cannot correctly describe failure !!"
                message += "\nThe function %r raised the exception" % augmentMessage
                message += "\n    %r" % exc
                message += "\nThe original unaugmented message is:"
                message += "\n%s" % origMessage
        return message

    def __call__(self, *args, **kwargs):
        Assertion._spoofFail -= 1
        ret, usedArgs, remArgs = self.check(*args, **kwargs)
        if ret and Assertion._spoofFail != 0:
            return ret
        details = self.describeFailure(usedArgs, remArgs, kwargs)

        addDetails = kwargs.get("addDetails", None)
        if addDetails is not None:
            details += "\n" + addDetails()

        raise Errors.Failure(details, altStack=kwargs.pop("altStack", None))


def _failAlways(asserter, *args, **kwargs):
    return False, (), args


_fail = Assertion(
        #autoMessage="The 'fail' assertion was invoked.",
        checkMethod=_failAlways)


def fail(*args, **kwargs):
    """Make current test fail unconditionally.

    """
    return _fail(*args, **kwargs)


class _ReAssertion(Assertion):
    def __call__(self, expr, actual, *args, **kwargs):
        return super(_ReAssertion, self).__call__(
                _normaliseRe(expr), actual, *args, **kwargs)


class _RaisesAssertion(Assertion):
    def check(self, excType, func, *args, **kwargs):
        self.raisedInstead = None
        try:
            func(*args, **kwargs)
        except excType as exc:
            return exc, (excType, func) + args, ()
        except Exception as details:
            # TODO: This is a work-around for hooked imports.
            e1, e2 = str(excType), str(details.__class__)
            e1 = e1.replace("_CS_.", "")
            e2 = e2.replace("_CS_.", "")
            if e1 == e2:
                return details, (excType, func) + args, ()
            self.raisedInstead = details
        return None, (excType, func) + args, ()

    def describeFailure(self, usedArgs, unusedArgs, kwargs):
        excType, func = usedArgs[0], usedArgs[1]
        if self.raisedInstead:
            exc = self.raisedInstead
            e1, e2 = str(exc.__class__.__name__), str(excType.__name__)
            if e1 == e2:
                # The exceptions are different, but have the same name. This
                # is a horrible thing to debug, so try to be extra helpful.
                return ("failUnlessRaises: Raised %s.%s instead of %s.%s\n"
                    "  str(exc) = %r" % (
                        exc.__class__,
                        exc.__class__.__name__,
                        excType,
                        excType.__name__, str(exc)))
            else:
                return ("failUnlessRaises: Raised %r instead of %r\n"
                    "  str(exc) = %r" % (
                        exc.__class__.__name__, excType.__name__, str(exc)))

        return "failUnlessRaises: Did not raise expected %r exception" % (
            excType.__name__)


_failUnlessRaises = _RaisesAssertion()

def failUnlessRaises(excType, func, *args, **kwargs):
    """Check that an exception is raised.

    The ``func`` is invoked as::

        func(*args, **kwargs)

    If the function does not raise an exception of ``excType`` then the
    test fails.

    :Return:
        The exception that was raised, if the test passes.

    :Parameters:
      excType
        The type of exception that is expected to be raised.
      func, args, kwargs
        The function to be executed, its positional and keyword arguments.

    """
    return _failUnlessRaises(excType, func, *args, **kwargs)


def failUnlessRaisesMsg(excType, func, expectMsg, *args, **kwargs):
    """Check that an exception matching a message is raised.

    This is like ``failUnlessRaises``, but you can also verify that that
    ``str(exc)`` has the correct form.

    :Return:
        The exception that was raised, if the test passes.

    :Param excType, func, args, kwargs:
        See `failUnlessRaises` for details.
    :Param expectMsg:
        This is the exception message expected, which means what ``str(exc)``
        should give.

    """
    def err():
        return ("failUnlessRaisesMsg: Raises %r OK, but message was wrong\n"
            "  Expected: %r\n"
            "  Got     : %r" % (excType.__name__, expectMsg, str(exc)))

    exc = failUnlessRaises(excType, func, *args, **kwargs)
    failUnlessEqual(expectMsg, str(exc), makeMessage=err)
    return exc


def _if(asserter, cond, *args, **kwargs):
    return bool(cond), (cond,), args

def _notIf(asserter, cond, *args, **kwargs):
    return not bool(cond), (cond,), args


_failIf = Assertion(
        autoMessage="Condition is True, but should be False",
        checkMethod=_notIf)


def failIf(cond, *args, **kwargs):
    """Fail if `cond` evaluates to a ``True`` value.

    :Parameters:
      cond
        Any expression that can be evaluated. The results is converted to a
        ``bool``.

    See `Assertion` for details of the other arguments.

    """
    return _failIf(cond, *args, **kwargs)



#: Fail if `cond` does not evaluate to a ``True`` value.
_failUnless = Assertion(
        autoMessage="Condition is False, but should be True",
        checkMethod=_if)

def failUnless(cond, *args, **kwargs):
    """Fail unless `cond` evaluates to a ``True`` value.

    :Parameters:
      cond
        Any expression that can be evaluated. The results is converted to a
        ``bool``.

    See `Assertion` for details of the other arguments.

    """
    return _failUnless(cond, *args, **kwargs)


def _eq(asserter, expect, actual, *args, **kwargs):
    return actual == expect, (expect, actual,), args


def _ne(asserter, expect, actual, *args, **kwargs):
    return expect != actual, (expect, actual,), args


_failUnlessEqual = Assertion(
        autoMessage=lambda used, rem, kwargs:
                "failUnlessEqual: values do not match\n"
                "Expected: %r\n"
                "Actual:   %r" % (used[0], used[1]),
        checkMethod=_eq)


def failUnlessEqual(expect, actual, *args, **kwargs):
    """Fail if ``expected`` != ``actual``.

    :Parameters:
      expect
        The expected value.
      actual
        The actual value produces by the system under test.

    See `Assertion` for details of the other arguments.

    """
    return _failUnlessEqual(expect, actual, *args, **kwargs)


_failIfEqual = Assertion(
        autoMessage=lambda used, rem, kwargs:
                "failIfEqual: %r == %r" % (used[0], used[1]),
        checkMethod=_ne)

def failIfEqual(expect, actual, *args, **kwargs):
    """Fail if ``expected`` == ``actual``.

    :Parameters:
      expect
        The expected value.
      actual
        The actual value produces by the system under test.

    See `Assertion` for details of the other arguments.

    """
    return _failIfEqual(expect, actual, *args, **kwargs)


def _inRange(asserter, minVal, maxVal, actual, *args, **kwargs):
    return minVal <= actual <= maxVal, (minVal, maxVal, actual), args

def _inRangeMsg(args, unusedArgs, kwargs):
    minVal, maxVal, actual = args
    return "failUnlessInRange: %r <= %r <= %r" % (minVal, actual, maxVal)


_failUnlessInRange = Assertion(autoMessage=_inRangeMsg, checkMethod=_inRange)

def failUnlessInRange(minVal, maxVal, actual, *args, **kwargs):
    """Fail unless the condition ``minVal <= actual <= maxVal`` is True.

    :Parameters:
      minVal, maxVal
        The permitted, inclusive range.
      actual
        The actual value produces by the system under test.

    See `Assertion` for details of the other arguments.

    """
    return _failUnlessInRange(minVal, maxVal, actual, *args, **kwargs)


def _diffStrings(asserter, expect, actual, *args, **kwargs):
    expectLines = expect.splitlines()
    actualLines = actual.splitlines()
    lineWrapper = kwargs.pop("lineWrapper", None)
    diffs = list(Diff.diffTextIter(expectLines, actualLines,
                    lineWrapper=lineWrapper))
    if diffs:
        asserter.data[:] = [diffs]
        return False, (expect, actual), args
    return True, (expect, actual), args


_oldFailUnlessEqualStrings = Assertion(
        extendedAutoMessage=_showStringDiffs,
        checkMethod=_eq)

_failUnlessEqualStrings = Assertion(
        extendedAutoMessage=_showStringDiffs,
        checkMethod=_diffStrings)


def failUnlessEqualStrings(expect, actual, *args, **kwargs):
    """Fail unless the expected string matches the actual string.

    This is similar to using failUnlessEqual, but the default generated message
    is more readable.

    :Parameters:
      expect
        The expected value.
      actual
        The actual value produces by the system under test.

    :Keywords:
      simple
        If ``True`` then only simple comparison and difference display will
        be used. This is only really here to allow avoid he need to update
        a load of cleversheep3's own tests.
      lineWrapper
        If supplied then this will be invoked as ``lineWrapper(line)`` for each
        line in the expected and actual text. The returned value *must* be an
        object that acts like a string and is hashable. Typically the object
        will also provide a custom __cmp__ operator method, to ignore
        uninteresting differences.

    See `Assertion` for details of the other arguments.

    """
    simple = kwargs.pop("simple", None)
    if simple:
        return _oldFailUnlessEqualStrings(expect, actual, *args, **kwargs)
    return _failUnlessEqualStrings(expect, actual, *args, **kwargs)


def _diffFloats(asserter, expect, actual, *args, **kwargs):
    """Returns whether the floating-point values

    This uses ULP difference to compare and assumes equality if 4 or less
    ULPs between the values.

    """
    ulpDiff = UlpCompare.ulpFloatDifference(expect, actual)
    if ulpDiff <= 4:
        return True, (expect, actual), args
    return False, (expect, actual), args


_failUnlessEqualFloats = Assertion(
        extendedAutoMessage=_showFloatDiffs,
        checkMethod=_diffFloats)


def failUnlessEqualFloats(expect, actual, *args, **kwargs):
    """Fail unless the expected floating-point matches the actual floating-point.

    This provides floating-point comparison using ULPs (Units of Least Precision).
    Float values are considered equal if within 4 ULPs of each other.

    :Parameters:
      expect
        The float expected value.
      actual
        The float actual value produced by the system under test.

    See `Assertion` for details of the other arguments.

    """
    return _failUnlessEqualFloats(expect, actual, *args, **kwargs)


def _reMatch(asserter, rExpr, actual, *args, **kwargs):
    return rExpr.search(actual), (rExpr, actual), args


def _notReMatch(asserter, rExpr, actual, *args, **kwargs):
    return not rExpr.search(actual), (rExpr, actual), args


_failUnlessReMatches = _ReAssertion(
        autoMessage=lambda used, rem, kwargs:
            "Regexp %r does not match %r" % (
                used[0].pattern, used[1]),
        checkMethod=_reMatch)


def failUnlessReMatches(expect, actual, *args, **kwargs):
    """Fail unless the expected regular expression matches the actual string.

    :Parameters:
      expect
        The expected value. This can be a string containing a regular expression
        or an already compiled regular expression.
      actual
        The actual value produces by the system under test.

    See `Assertion` for details of the other arguments.

    """
    return _failUnlessReMatches(expect, actual, *args, **kwargs)


_failIfReMatches = _ReAssertion(
        autoMessage=lambda used, rem, kwargs:
            "Regexp %r unexpectedly matches %r" % (
                used[0].pattern, used[1]),
        checkMethod=_notReMatch)


def failIfReMatches(expect, actual, *args, **kwargs):
    """Fail if the expected regular expression matches the actual string.

    :Parameters:
      expect
        The expected value. This can be a string containing a regular expression
        or an already compiled regular expression.
      actual
        The actual value produces by the system under test.

    See `Assertion` for details of the other arguments.

    """
    return _failIfReMatches(expect, actual, *args, **kwargs)


def failIfExists(*paths):
    """Check that one or more files do not exist.

    This can take one or more non-keyword arguments. Each is taken to be the
    pathname of a file. If any pathname refers to a file that exists then
    the executing test will fail.

    Currently, this does not accept any keyword arguments.

    :Parameters:
      paths
        All arguments are treated as pathnames to be checked.

    """
    def msg():
        return "The file %r should not exist" % p

    for p in paths:
        failIf(os.path.exists(p), makeMessage=msg)


def failUnlessExists(*paths):
    """Check that one or more files do exist.

    This can take one or more non-keyword arguments. Each is taken to be the
    pathname of a file. If any pathname refers to a file that does not exist
    then the executing test will fail.

    Currently, this does not accept any keyword arguments.

    :Parameters:
      paths
        All arguments are treated as pathnames to be checked.

    """
    def msg():
        return "The file %r should exist" % p

    for p in paths:
        failUnless(os.path.exists(p), makeMessage=msg)


def failUnlessFilesMatch(expect, actual, *args, **kwargs):
    """Check a pair of files have the same contents.

    :Parameters:
      expect
        The path to the file containing the expected content.
      actual
        The path to the file containing the actual content.

    :Keywords:
      simple
        If ``True`` then only simple comparison and difference display will
        be used. This is only really here to allow avoid he need to update
        a load of cleversheep3's own tests.
      lineWrapper
        If supplied then this will be invoked as ``lineWrapper(line)`` for each
        line in the expected and actual text. The returned value *must* be an
        object that acts like a string and is hashable. Typically the object
        will also provide a custom __cmp__ operator method, to ignore
        uninteresting differences.

    """
    def msg():
        return "The files %s and %s do not match" % (expect, actual)

    failUnlessExists(expect)
    failUnlessExists(actual)
    a = open(expect).read()
    b = open(actual).read()
    failUnlessEqualStrings(a, b, getTitle=msg, *args, **kwargs)


def _badMode(args, unusedArgs, kwargs):
    expect, actual = args
    return "The modes (permissions) of files %s and %s do not match" % (
            expect, actual)


def _eqMode(asserter, expect, actual, *args, **kwargs):
    a = os.stat(expect).st_mode
    b = os.stat(actual).st_mode
    return a == b, (expect, actual), args

_failUnlessFileModesMatch = Assertion(
        autoMessage=_badMode, checkMethod=_eqMode)


def failUnlessFileModesMatch(expect, actual, *args, **kwargs):
    """Check a pair of files have the same mode (permissions).

    :Parameters:
      expect
        The path to the file with the expected modes.
      actual
        The path to the file with the actual modes.

    """
    makeMessage = kwargs.get("makeMessage", None)
    failUnlessExists(expect)
    failUnlessExists(actual)
    _failUnlessFileModesMatch(expect, actual, makeMessage=makeMessage, *args, **kwargs)
