"""Coordination module used to connnect up the test framework.

This provides a registry that provides support for a loose implementation of
some number of classic patterns, such a publisher/subscriber.

THE ABOVE IS NOT REALLY TRUE, NOR IS WHAT FOLLOWS.

This is currently, probably, (perhaps) providing something between a message
broker and the publisher in the patterns world view.

In any case, this provides central place for parts of the cleversheep3 test
framework to resgister objects that provide a service. It can also be used
by user code for the same purpose.

"""

import weakref


class _Registry:
    """A registry for all publishers, subscribers, etc.

    There is only on of these, called 'Registry'; i.e. is it a singleton.

    TODO:
        Explain how to push and restore the registry state.
        Explain how this supports unit and other testing.

    """
    def __init__(self):
        self.groups = {}

    def addGroup(self, name, priority=100):
        if name not in self.groups:
            self.groups[name] = priority, ServiceGroup(name)
        return self.groups[name]

    def iterGroups(self):
        for priority, group in sorted(self.groups.items(), key=lambda e:e[0]):
            yield group


Registry = _Registry()


#log = open("/tmp/cs-coord.log", "w")


class ServiceGroup:
    def __init__(self, name):
        self.providers = {}

    def addServiceProvider(self, service, provider):
        self.providers[service] = provider


# TODO: Add facilities to, for example, set the current stdout/stderr
#       facilities. Actually, probably want something more generic.
#       The current Tty.py module bahaves differently depending on whether
#       output is to a log or terminal.

def registerGroup(name, priority=100):
    return Registry.addGroup(name, priority)
    if name not in Registry.groups:
        Registry.groups[name] = priority, ServiceGroup(name)
    return Registry.groups[name]


def registerProvider(groupName, serviceSet, provider):
    """Register an object that provides one or more services.

    :Parameters:
        groupName
            A name of the group of providers. If not already registered using
            `registerGroup` then it will be created with the default priority.

        serviceSet
            The services it provides. This is a list of service names or may be
            a simple string when only one servce is required.

        provider
            The provider object itself.

    """
    priorty, group = registerGroup(groupName)
    if not isinstance(serviceSet, (tuple, list, set)):
        serviceSet = (serviceSet,)
    for s in serviceSet:
        group.addServiceProvider(s, provider)
        # log.write("REG: %-20s <= %12s: %s\n" % (s, groupName, provider))


def getServiceProvider(*serviceSet):
    """Find a provider that will give the required services.

    This will look for a provider that provides all the services requested.
    If more than one provider can do the job then ...

    TODO: What then!

    :Parameters:
        serviceSet
            The name of all the services required.

    """
    for name, group in Registry.iterGroups():
        for s in serviceSet:
            if s in group.providers:
                return group.providers[s]


class Provider:
    def getFunction(self, name):
        return getattr(self, name)
