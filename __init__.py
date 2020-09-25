#!/usr/bin/env python
"""A collection of re-usable packages.

This is the top-level package for various other general purpose packages. It
exists in order keep the other packages tidily hidden within a single name
space. The sub-packages available are:

`Prog`
    Provides various general programming tools.

`TTY_Utils`
    Provides utilities assocated with logging to terminals and related
    activities.

`Test`
    Provides general support for testing.

`Debug`
    Some debug aids.

`Log`
    Useful things for logging support.

`VisTools`
    Tools to help visualisation. Most notably, at the moment,
    the sequence chart drawing module.

`IOUtils`
    Provides things like clever redirection.

The "Clever Sheep" was called Harold.

"""
__docformat__ = "restructuredtext"


# cleversheep3 version numbering scheme
# ====================================
#
# The version numbering follows the rules of 'Semantic Versioning 2.0.0'
# (http://http://semver.org/). Pre-releases are always given a suffix of
# 'alpha-N', where N is initially 1 and increments for each new pre-release.
# When the official release is reached, the 'alpha-N' is dropped, by setting
# ``preRelease`` to ``None``.
versionNum = (0, 5, 10)
preRelease = None
if preRelease is not None:
    versionNumStr = "%d.%d.%d-%s" % (versionNum + (preRelease, ))
else:
    versionNumStr = "%d.%d.%d" % versionNum
versionRelDate = "27 August 2014"
versionStr = "%s, released %s" % (versionNumStr, versionRelDate)

magic = ("This is magic")
