#! /usr/bin/env python
"""High level process management for Linux.

This module provides support for high-level querying and management of processes.
It uses the ``/proc`` file system to query details about processes.

The `getProcesses` is the normal way to get information.
"""
__docformat__ = "restructuredtext"

import os
import glob
import re

from cleversheep3.TextTools import DocParse

class NullOptions:
    def __getattr__(self, name):
        return None
_null = NullOptions()
del NullOptions


class _Process:
    """A class providing information about a process.

    It is instances of this class that you normally work with when using this
    module. It provides information about a process, mostly in the form
    of attributes. The names of the attributes mainly taken from the output of
    ``man proc`` (literally - I have just replicated much of the man page
    information here).

    Not all described attributes will necessarily be available, depending on
    your version of Linux.

%(attrs)s
    :Ivar uid:
        The user ID of the process.
    :Ivar gid:
        The group ID of the process.
    :Ivar tracerpid:
        The PID of the program that is tracing this process.
    :Ivar sleepavg:
        The percentage of time that this process has spent sleeping.
    :Ivar children:
        A list of the immediate child processes.
    :Ivar cmdline:
        The command as a tuple of ``(prog, args, arg2, ...)``. The ``prog`` is
        is not necessarily the full path of the executable.

    """
    def __init__(self, statText, statusText, cmdlineText):
        """Constructor:

        You would not normally use this directly, use `getProcesses`. If you do
        use it then beware that the arguments may change in the future, in
        non-compatible ways.

        :Param statText:
            The text from ``/proc/[number]/stat``.
        :Param statusText:
            The text from ``/proc/[number]/status``.
        """
        # The cmdlineText uses nul characters as separators, including a
        # trailing nul. So we do not want the last element when we split.
        self.cmdline = tuple(cmdlineText.split(chr(0))[:-1])
        self.children = []
        m = rStat.search(statText)
        if not m: #pragma: unreachable
            for attr, r, desc in statInfo:
                self.__dict__[attr] = None
            return

        for g, (attr, r, desc) in zip(m.groups(), statInfo):
            try:
                self.__dict__[attr] = int(g)
            except ValueError:
                self.__dict__[attr] = g

        for line in statusText.splitlines():
            if ':' not in line: #pragma: unreachable
                continue
            attr, value = [s.strip() for s in line.split(':', 1)]
            attr = attr.lower()
            if attr in statusInfo:
                self.__dict__[attr] = statusInfo[attr](value)

    def descendants(self, topdown=True):
        """Generator: Yield all descendants of this node.

        Useful if you need to find all the processes that have this process as
        an ancestor.

        :Param topdown:
            If True (the default) then the parent nodes are yielded
            before the child nodes.
        """
        for c in self.children:
            if topdown:
                yield c
            for d in c.descendants(topdown=topdown):
                yield d
            if not topdown: #pragma: unreachable (python sys.settrace issue)
                yield c
    descendents = descendants

    def find(self, predicate):
        """Generator: Find all descendant process that match the criteria.

        :Param predicate:
            A function that takes a `Process` instance and returns ``True`` is
            the process is a match.
        """
        return (p for p in self.descendants() if predicate(p))

    def getClones(self):
        """Return a list of process clones.

        This is currently ill-defined. The idea is that you can use this rather than
        directly access the `children` attribute in order to 'collapse' multiple
        processes of the same name into a single `Clone` instance.

        Asssume nothing.
        """
        clones = []
        for p in self.children:
            for c in clones:
                if p.comm == c.comm:
                    c.add(p)
                    break
            else:
                clones.append(Clone(p))
        return clones


class Clone:
    """Do not use"""
    def __init__(self, p):
        self.children = [p]
        self.comm = p.comm

    def add(self, p):
        self.children.append(p)


def _getProcText(pidDir, name):
    path = os.path.join(pidDir, name)
    f = open(path)
    text = f.read()
    f.close()
    return text


def process(pid):
    """Create a `Process` for the given process ID.

    The process must exist.

    :Return:
        A `Process` instance.
    :Param pid:
        The processes ID. This may be an integer or string.
    """
    pidDir = "/proc/%s" % pid
    try:
        statText = _getProcText(pidDir, "stat")
        statusText = _getProcText(pidDir, "status")
        cmdlineText = _getProcText(pidDir, "cmdline")
    except IOError:
        return None

    return Process(statText, statusText, cmdlineText)


def getProcesses(options=_null):
    """Get a list of `Process` instances, filtered by the options.

     This provides a slightly quirky API, specifically the ``options``
     argument. This is because this was absracted from some code to provide
     process querying and management, which used ``optparse``.

    :Return:
        A tuple of ``(thisProcess, processes, root_processes)``. Where:

        thisProcess
            A single instance of `Process`, representing, well, this process;
            i.e. ``thisProcess.pid == os.getpid()``.
        processes
            A list of all the processes, each entry is a `Process` instance.
        roots
            A list of all the processes that are not the child of another process.
            In other words all the processes that are the root process of a
            process tree. Each entry is a `Process` instance.

    :Param options:
        This must be an object that is like the ``options`` returned from the
        standard ``optparse`` module. The options that affect the behaviour
       are:

        user
            A user-id. Only processes that have this user ID are selected.
        exclude_user
            A user-id. Processes that have this user ID are **not** selected.
    """
    thisPid = os.getpid()
    thisProcess = None
    processes = []
    for pidDir in glob.glob("/proc/[0-9]*"):
        p = process(os.path.basename(pidDir))
        if p is None:
            continue
        if p.pid == thisPid:
            thisProcess = p
        if options.user is not None and p.uid != options.user:
            continue
        if options.exclude_user is not None and p.uid == options.exclude_user:
            continue
        processes.append(p)

    # Link parents to their children and identify all root processes.
    roots = []
    for p in processes:
        for q in processes:
            if p.ppid == q.pid:
                q.children.append(p)
                break
        else:
            roots.append(p)

    return thisProcess, processes, roots


def username2Uid(user):
    """Convert a user name to a UID.

    :Return:
        The UID or, if no matching user was found, ``None``.
    """
    if user is None:
        return user

    pwEnt = uid = None
    import pwd
    try:
        pwEnt = pwd.getpwnam(user)
    except KeyError:
        try:
            pwEnt = pwd.getpwuid(int(user))
        except (KeyError, ValueError):
            pass
    if pwEnt is not None:
        uid = pwEnt.pw_uid

    return uid



statusInfo = {
    "uid": lambda s: int(s.split()[0]),
    "gid": lambda s: int(s.split()[0]),
    "tracerpid": lambda s: int(s.split()[0]),
    "sleepavg": lambda s: int(s.split()[0][:-1]),
}

statInfo = ( #pragma: unreachable
    ("pid", r"([-+]?\d+)", """
         The process ID.
        """),
    ("comm", r"\(([^)]+)\)", """
         The filename of the executable, in parentheses.  This is visible
         whether or not the executable is swapped out.
        """),
    ("state", r"(\S)", """
         One  character  from the string "RSDZTW" where R is running, S is
         sleeping in an interruptible wait, D is waiting in uninterruptible
         disk sleep, Z is zombie, T is traced or stopped (on a signal), and W
         is  paging.
        """),
    ("ppid", r"([-+]?\d+)", """
         The PID of the parent.
        """),
    ("pgrp", r"([-+]?\d+)", """
         The process group ID of the process.
        """),
    ("session", r"([-+]?\d+)", """
         The session ID of the process.
        """),
    ("tty_nr", r"([-+]?\d+)", """
         The tty the process uses.
        """),
    ("tpgid", r"([-+]?\d+)", """
         The process group ID of the process which currently owns the tty that
         the process is connected to.
        """),
    ("flags", r"([-+]?\d+)", """
         The kernel flags word of the process. For bit meanings, see the
         ``PF_*`` defines in <linux/sched.h>.  Details depend on the kernel
         version.
        """),
    ("minflt", r"([-+]?\d+)", """
         The number of minor faults the process has made which have not
         required loading a memory page from  disk.
        """),
    ("cminflt", r"([-+]?\d+)", """
         The number of minor faults that the process's waited-for children have
         made.
        """),
    ("majflt", r"([-+]?\d+)", """
         The number of major faults the process has made which have required
         loading a memory page from disk.
        """),
    ("cmajflt", r"([-+]?\d+)", """
         The number of major faults that the process's waited-for children have
         made.
        """),
    ("utime", r"([-+]?\d+)", """
         The number of jiffies that this process has been scheduled in user mode.
        """),
    ("stime", r"([-+]?\d+)", """
         The number of jiffies that this process has been scheduled in kernel mode.
        """),
    ("cutime", r"([-+]?\d+)", """
         The number of jiffies that this process's waited-for children have
         been scheduled in user mode. (See also times(2).)
        """),
    ("cstime", r"([-+]?\d+)", """
         The number of jiffies that this process's waited-for children have
         been scheduled in kernel mode. """),
    ("priority", r"([-+]?\d+)", """
         The standard nice value, plus fifteen.  The value is never negative in
         the kernel.
        """),
    ("nice", r"([-+]?\d+)", """
         The nice value ranges from 19 (nicest) to -19 (not nice to others).
        """),
    ("unused", r"([-+]?\d+)", """
         This value is hard coded to 0 as a placeholder for a removed field.
        """),
    ("itrealvalue", r"([-+]?\d+)", """
         The time in jiffies before the next SIGALRM is sent to the process due
         to an interval timer.
        """),
    ("starttime", r"([-+]?\d+)", """
         The time in jiffies the process started after system boot.
        """),
    ("vsize", r"([-+]?\d+)", """
         Virtual memory size in bytes.
        """),
    ("rss", r"([-+]?\d+)", """
         Resident Set Size: number of pages the process has in real memory,
         minus 3 for  administrative  purposes. This is just the pages which
         count towards text, data, or stack space.  This does not include pages
         which have not been demand-loaded in, or which are swapped out.
        """),
    ("rlim", r"([-+]?\d+)", """
         Current limit in bytes on the rss of the process (usually 4294967295
         on i386).
        """),
    ("startcode", r"([-+]?\d+)", """
         The address above which program text can run.
        """),
    ("endcode", r"([-+]?\d+)", """
         The address below which program text can run.
        """),
    ("startstack", r"([-+]?\d+)", """
         The address of the start of the stack.
        """),
    ("kstkesp", r"([-+]?\d+)", """
         The current value of esp (stack pointer), as found in the kernel stack
         page for the process.
        """),
    ("kstkeip", r"([-+]?\d+)", """
         The current EIP (instruction pointer).
        """),
    ("signal", r"([-+]?\d+)", """
         The bitmap of pending signals.
        """),
    ("blocked", r"([-+]?\d+)", """
         The bitmap of blocked signals.
        """),
    ("sigignore", r"([-+]?\d+)", """
         The bitmap of ignored signals.
        """),
    ("sigcatch", r"([-+]?\d+)", """
         The bitmap of caught signals.
        """),
    ("wchan", r"([-+]?\d+)", """
         This is the "channel" in which the process is waiting.  It is the
         address of a system call,  and  can  be looked up in a namelist if you
         need a textual name.  (If you have an up-to-date /etc/psdatabase, then
         try ps -l to see the WCHAN field in action.)
        """),
    ("nswap", r"([-+]?\d+)", """
         Number of pages swapped (not maintained).
        """),
    ("cnswap", r"([-+]?\d+)", """
         Cumulative nswap for child processes (not maintained).
        """),
    ("exit_signal", r"([-+]?\d+)", """
         Signal to be sent to parent when we die.
        """),
    ("processor", r"([-+]?\d+)", """
         CPU number last executed on.
        """),
    ("rt_priority", r"([-+]?\d+)", """
         Real-time scheduling priority (see sched_setscheduler(2)).
         (since kernel 2.5.19)
        """),
    ("policy", r"([-+]?\d+)", """
         Scheduling policy (see sched_setscheduler(2)).
         (since kernel 2.5.19)
        """),
)


# Figure out how many values this platform provides in /proc/<pid>/stat.
f = open("/proc/%s/stat" % os.getpid())
words = f.read().split()
f.close()

# Create a regular expression to match the /proc/<pid>/stat on this platform.
statRe = " ".join([s for n, s, d in statInfo[:len(words)]])
rStat = re.compile(statRe)
del words


def _makeAttrDoc():
    """Make attribute details documentation for the Process class."""
    lines = []
    for name, expr, desc in statInfo:
        lines.append("    :Ivar %s:" % name)
        for line in DocParse.trimLines(desc.splitlines()):
            lines.append("%s:" % line)
    return "\n".join(lines)

_code = ( #pragma: unreachable
        '''class Process(_Process):
    """%s"""
''' % _Process.__doc__ % {"attrs": _makeAttrDoc()})
exec(_code)

del _Process, _makeAttrDoc


if __name__ == "__main__": #pragma debug
    import optparse
    usage = "usage: %prog [options]"
    parser = optparse.OptionParser(usage)

    parser.add_option("-U", "--user", action="store", default=None,
                      metavar="USER",
                      help="Select processes owned by USER")
    parser.add_option("-x", "--exclude-user", action="store", default=None,
                      metavar="USER",
                      help="Exclude processes owned by USER")
    parser.add_option("-u", "--mine", action="store_true",
                      help="Select processes own by the invoking user.")
    parser.add_option("--me", action="store_true",
                      help="Show processes rooted at this process")
    parser.add_option("-c", "--collapse", action="store_true",
                      help="Collapse processes with the same name")

    options, args = parser.parse_args()
    if len(args) != 0:
        parser.error("Wrong number of arguments")

    if options.mine:
        options.user = str(os.getuid())
    options.user = username2Uid(options.user)
    options.exclude_user = username2Uid(options.exclude_user)

    from cleversheep3.VisTools import Tree
    thisProc, processes, roots = getProcesses(options)
    for p in roots:
        if options.me:
            Tree.drawTree(thisProc)
        elif options.collapse:
            Tree.drawTree(p, getChildren=lambda n:n.getClones())
        else:
            Tree.drawTree(p)
