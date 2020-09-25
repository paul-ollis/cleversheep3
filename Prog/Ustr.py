#!/usr/bin/env python
"""A module that maps unique strings to the same objects.

This is useful when, for example, you have some complicated structures that
are identified and referenced by names.
"""
__docformat__ = "restructuredtext"

import os
import warnings
import inspect

csPath = os.path.join("cleversheep3", "Test", "Tester")
for count, frame in enumerate(inspect.stack()):
    if count == 0:
        continue
    if csPath not in frame[1]:
        break

warnings.warn("""
The 'cleversheep3.Prog.Ustr' module is deprecated. It will nolonger be
supported from version 0.5 onwards and will be removed in version 0.6.
Please use the 'Intern' module instead :
----------------------------------------------------------------------
""", PendingDeprecationWarning, stacklevel=count + 1)

from cleversheep3.Prog import Intern

Ustr = Intern.intern
ustrStr = Intern.internIfStr
ustr_property = Intern.internProperty
ustr_func = Intern.internFuncStrings
ustr_method = Intern.internMethodStrings

def reset():
    """Reset the module, forgetting previously defined Ustr instances.

    This exists for backward compatability only. It does nothing.

    """
