#!/usr/bin/env python
"""Classes to mock components for use in system testing.

The main class is the `Component`, which is intended to be used as the base
class for an object that plays the part of a separately running process.
However, a component is actually executed under the control of the
`cleversheep3.Test.PollManager`. This allows its behaviour to be tightly
controlled and tests to be fairly deterministic.

Actually this has become suitably general purpose as to be put somewhere else.
But what I will probably do is keep Component as a mocking class and make it
inherit from some other class, which will contain the bulk of current
Component.

"""
from __future__ import print_function
__docformat__ = "restructuredtext"

import itertools

from cleversheep3.Test.Tester import Logging
from . import Comms


def logComms(logFunc, src, dst, text):
    logFunc("%s -> %s %s", src, dst, text)


class Component:
    """The base class for a mock component in a test scenario.

    The intention for this class is that it should provide most of the
    functionality required to emulate a process. At least well enough for most
    test purposes.

    :Ivariables:
      pollManager
        The ``PollManager`` that is managing the component.
      connections
        One or more active connections managed by the component.
      listeners
        A dict of active listeners being manager by the component. The key is
        the name of the peer that is expected to connect and the value of the
        ``Listener`` managing the listen socket.
      pendingConnections
        A dict of pending outgoing connections. The key is the name of the peer
        that is expected to connect and the value of the ``Connector`` trying
        to connect to the peer.

    """
    _name = "UNKNOWN"
    peerCounter = itertools.count(1)

    #{ Construction
    def __init__(self, pollManager, log=None):
        """Constructor:

        :Parameters:
          pollManager
            This is typically a `PollManager` instance, but could be something
            that provides the same interface.

          log
            A standard ``logging`` object. If omitted, a default logging object
            is used.

            This is likely to disappear, so it is best not to use it. Currently
            the log object is stored, but not used.

        """
        self.log = log or Logging.getLogger(self._name).info
        # self.log = log or getLog(self._name).info
        self.pollManager = pollManager
        self.connections = {}
        self.listeners = {}
        self.pendingConnections = {}

    def shutDown(self):
        for name, conn in self.listeners.items():
            if conn is not None:
                conn.shutDown()
        for name, conn in self.connections.items():
            if conn is not None:
                conn.shutDown()
        for name, conn in self.pendingConnections.items():
            if conn is not None:
                conn.shutDown()
        self.connections = {}
        self.listeners = {}
        self.pendingConnections = {}

    #{ Connection establishment
    def listenFor(self, listenName, bindAddr):
        """Listen for connection from a peer.

        Arranges to start listening for connection from a peer.

        A SOCK_STREAM socket is created and added to a list of listenting
        sockets. Each call to this methods sets up a new listener.

        When a connection request occurs a socket for the connection is
        created (by accepting the request). Then the `onIncomingConnect` method
        is invoked as ``self.onIncomingConnect(s, peerName)``, where ``s`` is
        the new connection socket and ``peerName`` is the ``listenName``
        passed to this ``listenFor`` method.

        :Param listenName:
            The name by which the listener should be known, which is normally
            name of the peer that is expected to try to connect.
        :Param bindAddr:
            The address to bind to for listening. This is a tuple of
            ``(ipAddr, port)`` and the ``ipAddr`` is often an empty string,
            meaning accept connection from any address.

        """
        listenSocket = Comms.Listener(self.pollManager, listenName, bindAddr,
                                      onConnect=self._onIncomingConnect)
        self.listeners[listenName] = listenSocket
        return listenSocket
    addListener = listenFor

    def openDgramSocket(self, peerName, bindAddr=None, peerAddr=None):
        """Open a datagram socket.

        :Param peerName:
            A symbolic name for the communicating peer.
        :Param bindAddr:
            The Taddress to bind to for receiving packets.

        """
        p = Comms.Dgram(self.pollManager, peerName, bindAddr=bindAddr,
                peerAddr=peerAddr, onReceive=self._onReceive)
        self.connections[peerName] = p

    def openInputPipe(self, pipePath, peerName, native=False):
        """Open a named pipe for reading from.

        :Param pipePath:
            The path name of the PIPE.
        """
        p = Comms.PipeConn(False, pipePath, peerName, self.pollManager,
                onReceive=self._onReceive, onClose=self._onClose,
                onError=self._onError, native=native)
        self.connections[peerName] = p

    def openOutputPipe(self, pipePath, peerName, native=False):
        """Open a named pipe for reading from.

        :Param pipePath:
            The path name of the PIPE.
        """
        p = Comms.PipeConn(True, pipePath, peerName, self.pollManager,
                onReceive=self._onReceive, onClose=self._onClose,
                onError=self._onError, native=native)
        self.connections[peerName] = p

    def connectTo(self, peerName, peerAddr, connectTimes=(0.0, 0.5),
                  bindAddress=None):
        """Start trying to connect to a peer.

        :Param peerName:
            The name by which the connection to the peer should be known,
            which is normally the peer's name.
        :Param peerAddr:
            The internet address, i.e. a tuple of ``(ipAddr, port)``, of the
            peer. The ``ipAddr`` may be an empty string, meaning
            ``localhost``.
        :Param connectTimes:
            A tuple of ``(firstDelay, retryDelay)``, each is floating point
            value representing seconds. The first connection attempt will
            be made after ``firstDelay`` seconds. If that fails then
            connection attempts will be made every ``retryDelay`` seconds.
        """
        c = Comms.Connecter(self.pollManager, peerName, peerAddr,
                connectTimes, self._onOutgoingConnect,
                bindAddress=bindAddress)
        self.pendingConnections[peerName] = c
        return c

    def sendTo(self, peerName, bytes, count=None):
        """Send bytes to a named peer.

        :Param peerName:
            The name by which the connection to the peer is known, which is
            normally the peer's name.
        :Param bytes, count:
            The string of bytes to write and how many of those bytes to send.
            The `count` is normally omitted (or ``None``), in which case the
            entire string is sent.
        """
        conn = self.connections.get(peerName)
        if not conn:
            return
        conn.send(bytes, count=count)

    #{ The Component protocol methods.
    def onIncomingConnect(self, s, peerName):
        """Invoked when accepting a connection from a peer."""

    def onOutgoingConnect(self, peerName):
        """Invoked when an outgoing connection is established."""

    def onReceive(self, conn):
        """Invoked when a connection has received bytes."""

    def onClose(self, conn):
        """Invoked when a connection closes."""

    def onError(self, conn, exc):
        """Invoked when a connection has an abnormal error."""

    # TODO: Get a better name.
    def getConnName(self, listenName, peerAddr):
        """Map an incoming connection to a peer name.

        If you listen for multiple clients connecting to a single port then
        you need to over-ride this so that each new connection gets given
        a new name.
        """
        return listenName

    #{ Handling of socket activity.

    def _onIncomingConnect(self, s, listenName, peerAddr, source):
        """This is invoked by a `Listener`, for a new connection."""
        peerName = self.getConnName(listenName, peerAddr)
        if peerName.endswith('%d'):
            peerName = peerName % next(self.peerCounter)
        conn = self.connections[peerName] = Comms.SocketConn(s,
                peerName, self.pollManager,
                onReceive=self._onReceive, onClose=self._onClose,
                onError=self._onError, addr=peerAddr,
                isSSL=source.isSslConnection())
        self.onIncomingConnect(s, peerName)
        return conn

    def _onOutgoingConnect(self, peerName, source):
        """This is invoked by a `Connecter`, for a new connection."""
        # TODO: Make logging controllable.
        # logComms(self.log, self._name, peerName, "<CONNECT>")
        pending = self.pendingConnections.pop(peerName)
        conn = self.connections[peerName] = Comms.SocketConn(pending.s,
                peerName, self.pollManager,
                onReceive=self._onReceive, onClose=self._onClose,
                onError=self._onError,
                isSSL=source.isSslConnection())
        self.onOutgoingConnect(peerName)

    def _onReceive(self, conn):
        self.onReceive(conn)

    def _onClose(self, conn):
        self.onClose(conn)
        # logComms(self.log, conn.peerName, self._name, "<CLOSE>")

    def _onError(self, conn, exc):
        self.onError(conn, exc)
