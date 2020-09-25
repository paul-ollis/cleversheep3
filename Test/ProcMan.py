#!/usr/bin/env python
"""Process management support for testing.

Actually this is not very testing specific, but it was written for testing
purposes and there will be no attempt to make/keep it general purpose.

The functions and classes exported by this module are:#

    `start_display_xterm`
        Starts a x-term running in a way that support redirection.

    `run_in_xterm`
        Starts a process running, with input and output redirected to an
        x-term.

    `stopProcesses`
        Stops all processes that have been started using run_in_x-term.
"""
from __future__ import print_function
__docformat__ = "restructuredtext"

from cleversheep3.Sys.Platform import platformType

import subprocess
import os
import sys
import signal
import time
import glob
import atexit

# The close_fds flag is not supported under Windows. So we must use it
# selectively.
close_fds = True
if platformType == "windows":
    close_fds = False

#: A list of the running processes excluding the x-terms themselves.
_running = []

#: The set of the running x-terms, keyed by name. Each entry contains:
#:   - the subprocess.Popen instance.
#:   - the file names corresponding to stdin, stdout and stderr.
#:   - open files for stdin, stdout and stderr.
_terminals = {}


# We need the sleep program, which of course may be in one of several places.
_sleepPaths = ["/usr/bin/sleep", "/bin/sleep",
               "/usr/bin/sleep.exe", "/bin/sleep.exe"]
if platformType == "windows":
    _sleepPaths = ["c:/cygwin/bin/sleep"]
for exe in _sleepPaths:
    if platformType == "windows":
        exe += ".exe"
    if os.path.exists(exe):
        _sleepProg = exe
        break
else:
    pass
    # sys.exit("Could not find 'sleep' program.\n"
    #          "Please help by modifying ProcMan.py\n")


# The time to wait for SIGINT to bite (in tenths of a second).
_stopProcessTimeout = 30

def setStopTimeout(tenthsOfASecond):
    global _stopProcessTimeout
    _stopProcessTimeout = tenthsOfASecond


def get_xterm(name, geom="80x30+0+0"):
    """Arranges for a program to run as if in an x-term.

    The program is not run directly within the x-term, but with its input and
    output redirected to the x-term. The `name` specifies the term to use,
    which may already be running.

    :Param name:
        A name for the x-term. This is also used to set the term's title.

    :Param geom:
        This may be supplied to define the x-term's position and size. This has
        the format ``CxC+W+H``. The ``C`` values are the position for the top
        left corner in pixels; 0x0 means top left of the screen. The ``WxH``
        defines the width and height in characters.

    :Return:
        The ``subprocess.Popen`` instance for the newly spawned process.
    """
    if name in _terminals:
        p, (files, stdin, stdout, stderr) = _terminals[name]
    else:
        p, files = start_display_xterm(name, geom)
        stdin = open(files[0])
        stdout = open(files[1], "w")
        stderr = open(files[2], "w")
        _terminals[name] = (p, (files, stdin, stdout, stderr))

    return p, (files, stdin, stdout, stderr)


def _run(*args, **kwargs):
    p = subprocess.Popen(*args, **kwargs)
    _running.append(p)
    return p


if platformType == "windows":
    import win32con
    import win32process
    def run_in_xterm(name, cmd, geom="80x30+0+0", cwd=None):
        p = _run(args="%s" % cmd, close_fds=close_fds,
                cwd=cwd, creationflags=win32con.CREATE_NEW_CONSOLE)
        return p
else:
    def run_in_xterm(name, cmd, geom="80x30+0+0", cwd=None,
            useStdin=False):
        """Start a process within a terminal.

        This starts a separate process so that its output and appears in a
        separate terminal. If necessary an Xterm will be started, but if the
        `name` refers to an Xterm that ProcMan has already started then that
        terminal is reused.

        :Param name:
            The name assigned to the Xterminal. This will typically appear in
            the terminal's title bar.
        :Param cmd:
            The command to execute. This will be executed by the normal shell,
            much in the same as ``os.command``.
        :Param geom:
            An X geometry string, which defaults to '80x30+0+0'.
        :Param cwd:
            The directory to switch to before the new process is started.
        :Param useStdin:
            If True, the process's STDIN is a pipe rather than the Xterminal.
            This allows you to write to the process using ``p.stdin``, where
            ``p`` is the return from this function.

        :Return:
            A ``subprocess.Popen`` instance for the process.
        """
        p, (files, stdin, stdout, stderr) = get_xterm(name, geom)
        if useStdin:
            stdin = subprocess.PIPE
        args = (cmd,) + files
        p = _run(args="exec %s" % cmd, shell=True, stdin=stdin, stdout=stdout,
                stderr=stderr, close_fds=close_fds, cwd=cwd)
        return p


def stopProcesses(*args):
    """Stops all processes that have been started using run_in_xterm.

    :Note: Any x-terms that have been started are not stopped.
    """
    _stopProcessSet(_running)


def _findChildOf(pid, bins):
    # for path in glob.glob("/proc/[0-9]*[0-9]/stat"):
    for path in glob.glob("/proc/[0-9]*[0-9]/exe"):
        try:
            exe = os.readlink(path)
        except OSError:
            continue
        if exe not in bins:
            continue
        statPath = os.path.join(os.path.dirname(path), "stat")
        try:
            text = open(statPath).read()
        except IOError:
            continue

        a, b = text.split("(")
        cmd, c = b.split(")")
        parts = (a + c).split()
        ppid = int(parts[2])
        if ppid == pid:
            return parts[0]


def start_display_xterm(title, geom="120x50+0+0"):
    """Starts an X-term that can be used for redirection.

    The approach that we use is to run an XTerm with 'sleep 10d' as the program
    it should execute (i.e. we give it '-e sleep 10d'. This means that there
    should be a ``/usr/bin/sleep`` running as the child of the XTerm, which
    will have its STDIN, STDOUT and STDERR attaced to the terminal. Since these
    are available as ``/proc/NNNNN/fd/[012]``, we can easily effectively attach
    the input and ourput of other processes to the terminal.

    The slight wrinkle to all of this is that the XTerm program does not start
    the sub process as a direct child; I do not know why. However it does mean
    that on an unloaded system if the XTerm has process number M then the sleep
    process will have M+2. There is a mystery process with number M+1, which we
    **must** ignore. This is why we explicitly use ``/usr/bin/sleep`` and look
    for a process which has that specific executable.

    NOTE: We used to use 'sleep 99d' but under my Cygwin installation that
    causes sleep to use 100% CPU!

    :Return:
        A tuple of (stdin, stdout, stderr), being the filenames of the pseudo
        ttys of the idle.py process.
    """
    # Run sleep as the xterm's process rather than the normal shell.
    # NOTE: Anything that last for more than 10 days will break ;)
    p = subprocess.Popen(args=("xterm",
        "-T", title,
        "-geometry", geom,
        # "-l", "-lf", "%s.log" % (title.replace(" ", "-")),
        "-e", _sleepProg, "10d"), close_fds=close_fds)

    for i in range(150):
        child = _findChildOf(p.pid, _sleepPaths)
        if child is not None:
            break
        time.sleep(0.1)
    else:
        # TODO: Error, no child appeared in the x-term
        print("No XTerm child (sleep 10d) appeared to start")
        print("This really should not happen!")
        sys.exit(0)

    fmt = "/proc/%s/fd/%%d" % child
    stdin, stdout, stderr = tuple([fmt % n for n in [0, 1, 2]])

    # A nasty gotcha is that the /proc/NNNNN/fd/N files appear before they
    # become openable (probably start off owned by root). So we have a second
    # loop that waits until the permissions have been sorted out.
    for i in range(150): # Try for about 15 seconds.
        try:
            f = open(stdout)
            f.close()
            break
        except IOError:
            pass
        time.sleep(0.1)
    else:
        # TODO: Error, never seemed to be allowed to open the file
        print("Could not open %r, to connect to x-term" % stdout)
        print("This really should not happen!")

    p.children = [int(child)]
    return p, (stdin, stdout, stderr)


def _stopProcessSet(procSet):
    """Stop all the processes that are in the `procSet`.

    First any still running processes are sent SIGTERM then, if still running
    after 3 seconds, a SIGKILL is delivered.

    :Param procSet:
        A list of subprocess.Popen instances for the processes to be stopped.
        This list is emptied, so you may wish to pass a copy.
    """
    # Send a SIGTERM to all (still running) processes.
    finished = {}
    needToWait = False
    for i, p in enumerate(procSet):
        if p.poll() is not None:
            finished[p] = None
            continue

        needToWait = True
        try:
            if platformType == "windows":
                win32process.TerminateProcess(p._handle, 0)
            else:
                os.kill(p.pid, signal.SIGTERM)
                if i == 0:
                    children = getattr(p, "children", [])
                    for cpid in children:
                        os.kill(cpid, signal.SIGTERM)
        except OSError:
            # This can happen if the process has died before the call to kill, so
            # we ignore it.
            pass

    if needToWait:
        # At least one process has been signalled, so wait for about
        # _stopProcessTimeout * 0.1 seconds or until all the processes have
        # died.
        for i in range(_stopProcessTimeout):
            done = True
            for p in procSet:
                # print(">>", p.poll())
                if p.poll() is not None:
                    finished[p] = None
                    continue
                done = False

            if done:
                break
            else:
                time.sleep(0.1)

        # Now use SIGKILL on any processes still running.
        for p in procSet:
            if p not in finished:
                try:
                    if platformType == "windows":
                        win32process.TerminateProcess(p._handle, 0)
                    else:
                        os.kill(p.pid, signal.SIGKILL)
                except OSError:
                    # Process may have died before the call to kill.
                    pass

        # Wait again for all the processes to die. If they do not then
        # something really horrid has happened.
        for i in range(_stopProcessTimeout):
            done = True
            for p in procSet:
                if p.poll() is not None:
                    finished[p] = None
                    continue
                done = False

            if done:
                break
            else:
                time.sleep(0.1)

    for p in procSet:
        if p.poll() is None:
            print("Heck! Could not stop process with ID = %d" % p.pid)

    # Clear the list of processes.
    procSet[:] = []


def _stopTerminals(*args):
    """Stops all the currently running x-terms."""
    procSet = [p for p, x in _terminals.values()]
    _stopProcessSet(procSet)
    _terminals.clear()


def _killGrp(p):
    now = time.time()
    while p.poll() is None and time.time() - now < 5:
        try:
            os.killpg(p.pid, signal.SIGINT)
        except OSError as exc:
            pass
        if p.poll() is not None:
            break
        time.sleep(0.1)

    # Just to be sure, issue KILL in case any child processes have not
    # died.
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except OSError:
        pass


def system_grp(cmd):
    """An alternative to os.system that runs in a new process group

    This uses the subprocess module to run a command in a similar manner to
    os.system, but the sub-process runs in its own process group. There are
    other differences:

    - This does not block signals.
    - When the main process finishes the process group is killed. So
      this is no good for starting up background processes.
    """
    p = subprocess.Popen(cmd, shell=True, preexec_fn=lambda:os.setpgrp())
    try:
        return os.waitpid(p.pid, 0)
    finally:
        _killGrp(p)


# Make sure that the x-terms are stopped when the program exits along with any
# other processes.
atexit.register(_stopTerminals)
atexit.register(stopProcesses)
