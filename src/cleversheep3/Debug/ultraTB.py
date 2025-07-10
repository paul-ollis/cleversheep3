"""Deprecated: Wraps Extras.ultraTB."""
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
The 'cleversheep3.Debug.ultraTB' module is deprecated. Please use either:

  The official ultraTB (http://www.n8gray.org/files/ultraTB.py)

or the copy.

  cleversheep3.Extras.ultraTB
----------------------------------------------------------------------
""", PendingDeprecationWarning, stacklevel=count + 1)

import cleversheep3.Extras.ultraTB as _ultraTB

Colors = _ultraTB.Colors
ColorTB = _ultraTB.ColorTB
VerboseTB = _ultraTB.VerboseTB
del _ultraTB
