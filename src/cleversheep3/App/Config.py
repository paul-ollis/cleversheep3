#!/usr/bin/env python
"""General configuration and command line option management.

One of the 'patterns' that regularly occurs for me, is the need to provide
program configuration options using a variety of methods. In order of
precedence (later methods over-ride earlier methods) these are:

    1. Setting default values for when no other method has been used.
    2. Setting config values using multiple configuration files.
    3. Setting config values using command line options.
    4. Setting config values programtically.

I *always* use the ``optparse`` module to process command line options, so this
module is designed to work with ``optparse``.

Using this module is fairly simple. Normally you can simply use the `config`
module member rather than explictly creating your own `Config` instance. An
application that parses options using options using ``optparse`` would normally
look something like:<py>:

    if __name__ == "__main__":
        import optparse

        usage = "usage: %prog [options] source-path dest-path"
        parser = optparse.OptionParser(usage)
        parser.add_option("--verbose", action="store_true",
                          help="Run in verbose mode")
        # ... additional options.
        options, args = parser.parse_args()

Using this module the code looks like:<py>:

    if __name__ == "__main__":
        import optparse
        from cleversheep3.App import Config

        usage = "usage: %prog [options] source-path dest-path"
        parser = optparse.OptionParser(usage)
        parser.add_option("--verbose", action="store_true",
                          help="Run in verbose mode")
        # ... additional options.
        options, args = Config.config._control.parse_args(parser)

That is one extra import and the call to ``parse_args`` is changed. As a
result, you can use ``Config.config`` in place of the returned ``options``. The
results will be the same.

However, you can also use the additional `Config` methods to over-ride the
default values (`Config._setDefault`), load values typically read from a file
(`Config._addConfigFileValues`) and simply over-ride value programatically
(`Config._set`).

Normally, you should use these methods via the `Config._control` special
member; e.g. ``config._control.set("x", 3)`` rather than
``config._set("x",3)``.

"""
__docformat__ = "restructuredtext"


import optparse

try:
    tx = optparse._
except AttributeError:
    tx = lambda x: x


class _Values(optparse.Values):
    """A specialisation of ``optparse.Values``, which tracks set values.

    This class simply adds the ability to know which values have been
    explicitly set, rather than just set to default values. This allows the
    `Config` class to determine when a config value has been over-ridden on the
    command line.

    :Ivar _isset:
        A dictionary of explicitly set config items; the key is the config item
        name. The leading underscore is to avoid clashing with any potential
        coinfig name; it does not indicate that the attribute is considered
        private.

    """
    def __init__(self, defaults=None):
        self.__dict__["_isset"] = {}
        if defaults:
            for (attr, val) in defaults.items():
                self.__dict__[attr] = val

    def __setattr__(self, name, value):
        self._isset[name] = True
        self.__dict__[name] = value


def _optionValues(parser):
    """Helper factory function to provide values for ``parser.parse_args``.

    This creates an instance of `_Values`, initialised with the defaults
    defined by the ``optparser`` `parser`.

    :Param parser:
        This should be an ``optparse.OptionParser`` instance.

    """
    values = parser.get_default_values()
    return _Values(values.__dict__)


def parse_args(parser, args=None):
    """Helper functions to parse command line arguments.

    This is equivalent to invoking ``parser.parse_args()`` except that
    the returned options will be a `_Values` instance rather than a simple
    ``optparse.Values`` instance. The ``Config._setOptparseOptions`` method
    needs a `_Values` instance as its argument.

    Normally it is simpler to use `Config.parse_args(parser)`.

    """
    return parser.parse_args(args, _optionValues(parser))


class ConfigFile(_Values):
    """Class to store values set in a config file.

    This is actually just a form of the (internal) `_Values` class.

    """


class _Struct:
    pass


class Config:
    """Multi-source configuration manager.

    This class povides a wrapping around configuration/options information
    from multiple sources:

    1. Explictly (programatically) set values.
    2. Command line options.
    3. Initialisation file(s)
    4. Default (programatically set) values.

    The above order defines the override precedence; an initialisation file can override
    the default value, which can be overriden by a command line option, etc.

    :Ivar _control:
        Use this to access the control methods. For example,
        ``config._control.set("x", 3)`` rather than ``config._set("x",3)``
    """
    def __init__(self):
        """Constuctor"""
        self._reset()

    def _reset(self):
        self.__set("_explicit", {})
        self.__set("_optparseOptions", None)
        self.__set("_configFileValues", [])
        self.__set("_defaults", {})
        self.__set("_control", _Struct())
        self._control.setOptparseOptions = self._setOptparseOptions
        self._control.addConfigFileValues = self._addConfigFileValues
        self._control.parse_args = self._parse_args
        self._control.setDefault = self._setDefault
        self._control.set = self._set
        self._control.get = self._get
        self._control.has = self._has
        self._control.reset = self._reset
        self._control.definedItems = self._definedItems

    def __set(self, name, value):
        self.__dict__[name] = value

    def _setOptparseOptions(self, options):
        """Set the ``optparse`` options, as read from the command line.

        :Param options:
            This must be a `_Values` instance or an object that provides
            a ``_isset`` member and similar behaviour.
        """
        self.__set("_optparseOptions", options)
        assert hasattr(options, "_isset")

    def _addConfigFileValues(self, path, values):
        assert hasattr(values, "_isset")
        self._configFileValues.append((path, values))

    def addConfigFileValues(self, path, values):
        """Add a set of option values, typically read from a file.

        :Parameters:
          path
            Typically the path to the file, from which the `values` were read.
            This is a place-holder for future functionality and is for
            information only.
          values
            Typically this should be a `ConfigFile` instance or something
            that provides similar behaviour. Nominally, the values are as
            read from some configuration file, but the mechanism is general.

        """
        self._addConfigFileValues(path, values)

    def _parse_args(self, parser, args=None):
        """Invoke ``parser.parse_args`` but return `_Values`.

        This is intended to be used rather than invoking ``parser.parse_args``
        directly. Using this makes this `Config` instance aware of which
        values have been defined by command line options.

        :Param parser:
            An ``optparse.OptionParser`` instance.
        :Param args:
            Optional arguments to be passed to ``parser.parse_args``.
        """
        options, args = parse_args(parser, args)
        self._setOptparseOptions(options)
        return options, args

    def _setDefault(self, name, value):
        """Set a (last resort) default fallback value for a config item.

        :Param name:
            The config item's name. This should normally be a valid Python
            identifier, which does not have a leading underscore.
        :Param value:
            The default value to set.
        """
        self._defaults[name] = value

    def _set(self, name, value):
        """Set an over-riding value for a config item.

        :Param name:
            The config item's name. This should normally be a valid Python
            identifier, which does not have a leading underscore.
        :Param value:
            The value to set.
        """
        setattr(self, name, value)

    def _get(self, name, default=None):
        """Get the value of a config item.

        :Param name:
            The config item's name. This should normally be a valid Python
            identifier, which does not have a leading underscore.
        :Param default:
            The value to return if the item is not set and no other default has
            been defined.
        """
        return self.__getattr__(name, default)

    def _has(self, name):
        value, isDefined = self._getattr(name, None)
        return isDefined

    def _definedItems(self):
        """Iterate the defined values.

        This yields ``(name, value)`` for all defined config values, which are
        those that have been given a default value. The returned values are
        sorted by name.
        """
        for name in sorted(self._defaults):
            yield name, self._getattr(name)[0]

    def _getattr(self, name, default=None):
        """Get an attribute by name.

        :Param name:
            The name of the parameter.
        :Param default:
            A default to return, if no defined value exists.

        :Return:
            A tuple of ``(value, isDefined)``. The ``isDefined`` value will be
            ``False`` unless the supplied `default` had to be used.
        """
        # Explictly set values trump all other sources
        if name in self._explicit:
            return self._explicit[name], True

        # Values supplied on the command line have high priority.
        if (self._optparseOptions
                and self._optparseOptions._isset.get(name, None)):
            return getattr(self._optparseOptions, name), True

        # Next we look to see if any configuration file has defined the value.
        for path, values in reversed(self._configFileValues):
            if values._isset.get(name, None):
                return getattr(values, name), True

        # If we have an explicit default, use that.
        if name in self._defaults:
            return self._defaults[name], True

        # If there is no explicit default then the option parser default is used.
        if self._optparseOptions:
            if hasattr(self._optparseOptions, name):
                return getattr(self._optparseOptions, name), True

        # And finally, use the last resort fallback value.
        return default, False

    def __getattr__(self, name, default=None):
        value, isDefined = self._getattr(name, default)
        return value

    def __setattr__(self, name, value):
        self._explicit[name] = value

    __getitem__ = __getattr__
    __setitem__ = __setattr__


class SlackOptionParser(optparse.OptionParser): #pragma: needs testing
    """Special version of ``optparse.OptionParser``, which ignores errors.

    This is intended to be used where you need to pre-parse the command line
    options before it has been possible to create a fully defined
    `OptionParser`.

    When you invoke the ``parse_args`` on this option parser, it will silently
    skip any options that are not recognised and copy them into the list of
    unconsumed argument. Then you can pass those (unconsumed) arguments to
    another parser's ``parse_args`` method.

    """
    def _process_args(self, largs, rargs, values):
        """Version of _process_args, which does not stop on errors.

        Any unrecognised options are not consumed, they are copied to the
        ``largs`` list. This allows those options to be passed to a second
        command line parser.

        This s mostly a duplication of the code from the Python2.4 release.

        """
        while rargs:
            arg = rargs[0]
            # We handle bare "--" explicitly, and bare "-" is handled by the
            # standard arg handler since the short arg case ensures that the
            # len of the opt string is greater than 1.
            if arg == "--":
                return
            elif arg[0:2] == "--":
                # process a single long option (possibly with value(s))
                try:
                    self._process_long_opt(rargs, values)
                except (optparse.BadOptionError, optparse.OptionValueError):
                    largs.append(arg)
            elif arg[:1] == "-" and len(arg) > 1:
                # process a cluster of short options (possibly with
                # value(s) for the last one only)
                opt = self._process_short_opts(rargs, values)
                if opt:
                    largs.append(opt)
            else: # Always allow interspersed args.
                largs.append(arg)
                del rargs[0]

    def _process_long_opt(self, rargs, values):
        """Version of _process_long_opt, which does not stop on errors.

        This s mostly a duplication of the code from the Python2.4 release.
        """
        arg = rargs.pop(0)

        # Value explicitly attached to arg?  Pretend it's the next
        # argument.
        if "=" in arg:
            (opt, next_arg) = arg.split("=", 1)
            rargs.insert(0, next_arg)
            had_explicit_value = True
        else:
            opt = arg
            had_explicit_value = False

        try:
            opt = self._match_long_opt(opt)
        except optparse.BadOptionError:
            if had_explicit_value:
                rargs.pop(0)
            raise
        option = self._long_opt[opt]
        if option.takes_value():
            nargs = option.nargs
            if len(rargs) < nargs:
                if nargs == 1:
                    self.error(tx(
                        "%s option requires an argument") % opt)
                else:
                    self.error(tx(
                        "%s option requires %d arguments")
                               % (opt, nargs))
            elif nargs == 1:
                value = rargs.pop(0)
            else:
                value = tuple(rargs[0:nargs])
                del rargs[0:nargs]

        elif had_explicit_value:
            self.error(tx("%s option does not take a value") % opt)

        else:
            value = None

        option.process(opt, value, values, self)

    def _process_short_opts(self, rargs, values):
        """Version of _process_short_opts, which does not stop on errors.

        This s mostly a duplication of the code from the Python2.4 release.

        :Return:
            If the option is unknown then the option string (e.g. ``-x``)
            is returned. Otherwise returns ``None``.
        """
        newOptStr = "-"
        arg = rargs.pop(0)
        stop = False
        i = 1
        for ch in arg[1:]:
            opt = "-" + ch
            option = self._short_opt.get(opt)
            i += 1                      # we have consumed a character

            if not option:
                newOptStr += ch
                continue
            if option.takes_value():
                # Any characters left in arg?  Pretend they're the
                # next arg, and stop consuming characters of arg.
                if i < len(arg):
                    rargs.insert(0, arg[i:])
                    stop = True

                nargs = option.nargs
                if len(rargs) < nargs:
                    if nargs == 1:
                        self.error(tx(
                            "%s option requires an argument") % opt)
                    else:
                        self.error(tx(
                            "%s option requires %d arguments") % (opt, nargs))
                elif nargs == 1:
                    value = rargs.pop(0)
                else:
                    value = tuple(rargs[0:nargs])
                    del rargs[0:nargs]

            else:                       # option doesn't take a value
                value = None

            option.process(opt, value, values, self)

            if stop:
                break
        if newOptStr != '-':
            return newOptStr


config = Config()

#: Option sets identified by name.
_configs = {}


# TODO: Used in Mym tests.
def reset():
    pass


def _getConfig(name):
    if name not in _configs:
        _configs[name] = Config()
    return _configs[name]


class Options:
    def __init__(self, name):
        self.__dict__["_name"] = name
        self.__dict__["_optionsInstance"] = _getConfig(name)

    def __getattr__(self, name):
        return getattr(self._optionsInstance, name)
