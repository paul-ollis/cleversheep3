"""This package contains copies of third party modules/packages.

This is not intended to be used directly. It is used indirectly when the
'real' package is not available. The reason for doing this is that I want
to make the cleversheep3 not depend on lots of third party modules, but
some modules, such as Michele Simionato's ``decorater`` module are pretty much
essential. Replicating them here simply means I do not have to require people
to install additional modules.

The modules in here are:

+---------------+---------+---------------------------------------------------+
| Module        | Version | Notes                                             |
+===============+=========+===================================================+
| decorator     | 2.3.2   | Michele Simionato's signature preserving          |
|               |         | decorator module.                                 |
|               |         |                                                   |
|               |         | See: http://pypi.python.org/pypi/decorator        |
+---------------+---------+---------------------------------------------------+
| ultraTBy      | 0.3     | Nathan Gray's module that provides coloured       |
|               |         | traceback output.                                 |
|               |         |                                                   |
|               |         | See: http://www.n8gray.org/files/ultraTB.py       |
+---------------+---------+---------------------------------------------------+

"""
__docformat__ = "restructuredtext"
