#!/usr/bin/env python
"""Lots of ways to generate data for tests.

This will probably evolve into a full package. For now it is mainly
designed to provide ways to generate text data as inputs to tests.
"""
__docformat__ = "restructuredtext"

from cleversheep3.Prog import Files


def literalText2Lines(text, noTail=False, params=None):
    """Generator: Convert a literal text representation to lines.

    The supplied `text` is one or more multiline string, with leading '|'
    characters on each line. All text up to each '|' plus the following
    character (which should be a space) is stripped from each line. Lines that
    have no leading '|' character are (currently) silently discarded.

    If you need trailing whitespace then put a '|' character to represent the
    end of the line. If you need a '|' at the end of the line then put two
    '|' characters.

    So, for example::

        | Hello||
        |    There |

    Will yield ``"Hello|"`` followed by ``"   There "``.

    :Parameters:
      text
        Either:

           A multiline string, with leading '|' characters on each
           line. Each '|' should be followed by a space (not currently
           enforced but may be in the future).

        or:

           A sequence of strings with the above described format.

      noTail
        If ``True`` then a '|' character at the end of a line is not treated as
        an end of line marker, so all lines will have no trailing whitespace.

      params:
        If supplied and not ``None`` then this must be a dictionary which
        will be used for interpolation (using ``%``) for each line.

    """
    if isinstance(text, str):
        blocks = [text]
    else:
        blocks = text

    lines = []
    for text in blocks:
        for line in text.splitlines():
            if "|" in line:
                line = line[line.index("|")+2:].rstrip()
                if not noTail and line.endswith("|"): #pragma: debug
                    line = line[:-1]
                if params is not None:
                    yield line % params
                else:
                    yield line


def literalText2Text(text, noTail=False, params=None):
    """Like literalText2Lines, but returns a full string.

    See `literalText2Lines` for parameter details.
    """
    return "\n".join(literalText2Lines(text, noTail=noTail, params=params))


def makeSimpleFile(path, text, mode=None):
    """Create a data file containing text.

    This simply writes the provided text to the specified file. It also tries
    to create any required intermediate directories.

    Often `makeFile` is a more convenient function for non-trivial content.

    :Parameters:
      path
        The path name of the file to be created.
      text
        The text to write to the file.
      mode
        A string specifying how to modify the permissions of the created file.
        See `Prog.Files.chmod` for details of this argument.
    """
    Files.mkParentDir(path)
    with open(path, "w") as f:
        f.write(text)
        f.write('\n')
    if mode is not None:
        Files.chmod(path, mode)


def makeFile(path, text, noTail=False, params=None, mode=None):
    """Create a data file containing text.

    This uses `literalText2Text` to convert the ``text`` argument to the actual
    file content, which it passs to `makeSimpleFile`.

    :Parameters:
      path
        The path name of the file to be created.
      text, noTail, params
        See `literalText2Text` for details.
      mode
        A string specifying how to modify the permissions of the created file.
        See `Prog.Files.chmod` for details of this argument.
    """
    makeSimpleFile(path, literalText2Text(text, noTail, params), mode=mode)
