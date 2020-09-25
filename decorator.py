"""Deprecated: Wraps Extras.decorator.py."""
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
The 'cleversheep3.decorator' module is deprecated. It will no longer be
supported from version 0.5 onwards and will be removed in version 0.6.
Please use either:

  The official decorator (http://pypi.python.org/pypi/decorator)

or the convenient copy in the cleversheep3 library:

  cleversheep3.Extras.decorator
----------------------------------------------------------------------
""", PendingDeprecationWarning, stacklevel=count + 1)

from cleversheep3.Extras.decorator import *
