"""Communications support for test mocking.

This module provides support for dgram and streaming socket comminucations. It
is designed to be used within code controlled by the
`cleversheep3.Test.PollManager`.

"""
from __future__ import print_function
__docformat__ = "restructuredtext"

import errno
import os
import socket
import ssl
import struct
import weakref

from cleversheep3.Test import Net, PollManager
from cleversheep3.Test.Struct import Struct, Format, Type

CallbackRef = PollManager.CallbackRef

readBlockSize = 4096 * 8
writeBlockSize = 4096 * 8

# TODO: Retire this.
class _PollManagedComms: #pragma: unsupported
    """A mix-in for comms objects that use the `PollManager`.

    TODO
    """
    def __init__(self, pollManager):
        """Constructor:

        :Param pollManager:
            This is typically a `PollManager` instance, but could be something
            that provides the same interface.
        """
        self.pollManager = pollManager
        self.onReceiveCB = CallbackRef()
        self.onClose = CallbackRef()

    def setCallbacks(self, onReceive, onClose):
        """Set the calbacks for new connections.

        :Param onReceive, onClose:
            The bound or unbound functions to be called back.
        """
        self.onReceiveCB = CallbackRef(onClose)
        self.onCloseCB = CallbackRef(onReceive)


class Dgram:
    """A class to use datagrams communications.

    This basically wraps a ``socket.socket`` instance that is configured for
    datagrams (typically UDP) communications, to provide better support for
    mock objects.

    """
    #{ Construction
    def __init__(self, pollManager, peerName, bindAddr=None, peerAddr=None,
            onReceive=None):
        """Constructor:

        :Parameters:
          pollManager
            This is typically a `cleversheep3.Test.PollManager` instance, but
            could be something that provides the same interface.
          peerName
            The name of the peer entity that is expected to send or receive
            datagrams.
          bindAddr
            The address to bind to before starting to listen. This is a tuple
            of ``(ip-address, port)``. The ip-address may be an empty string,
            meaning 'localhost'.
          peerAddr
            The address of the peer entity that is expected to send or receive
            datagrams.
          onReceive
            An optional function to be invoked when input is received. The
            function is invoked as ``onReceive(self)``.
        """
        self.pollManager = pollManager
        self.peerName = peerName
        self.bindAddr = bindAddr
        self.peerAddr = peerAddr
        self.onReceiveCB = CallbackRef(onReceive)

        # TODO: Add error handling
        self.s = s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self.bindAddr is not None:
            s.bind(bindAddr)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.s.setblocking(0)
            self.pollManager.addInputCallback(s, self.onReceive)
        self._fileno = self.s.fileno()

    def onReceive(self, fd, ev):
        """Invoked when a socket has received bytes.

        This simple invokes the ``onReceiveCB`` callback function, as
        ``onReceiveCB(self)``.

        """
        self.onReceiveCB(self)

    def read(self):
        """Read s single datagram."""
        try:
            p, self.lastAddr = self.s.recvfrom(65536)
        except socket.error as exc:
            if exc.args[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                p = None

        return p

    def send(self, bytes, count=None):
        """Send data to the peer.

        This simply sends the the string `bytes` to the peer.

        :Param bytes:
            The string containing the bytes to send.
        :Param count:
            If supplied and non-zero then only the first `count` bytes will be
            sent.
        """
        if self.s is None:
            return
        count = count or len(bytes)
        self.s.sendto(bytes[:count], self.peerAddr)

    def shutDown(self):
        # Remove the callback and close the listening socket.
        self.pollManager.removeInputCallback(self._fileno)
        self.s.close()


class Listener:
    """A class to listen for connections on a socket

    This basically wraps a ``socket.socket`` instance to provide better support
    for mock objects.

    Currently only AF_INET address family sockets are supported.
    """
    #{ Construction
    def __init__(self, pollManager, peerName, bindAddr, onConnect=None):
        """Constructor:

        :Param pollManager:
            This is typically a `PollManager` instance, but could be something
            that provides the same interface.
        :Param peerName:
            A name for the peer that is expected to connect this socket.
        :Param bindAddr:
            The address to bind to before starting to listen. This is a tuple
            if (ip-address, port). The ip-address may be an empty string, meaning
            'localhost'.
        :Param onConnect:
            A function to be invoked when a new connection is established.
        """
        self.pollManager = pollManager
        self.peerName = peerName
        self.bindAddr = bindAddr
        self.onConnectCB = CallbackRef(onConnect)

        # TODO: Add error handling
        self.s = s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(bindAddr)
        except socket.error:
            raise
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.listen(1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.pollManager.addInputCallback(s, self.onConnect)
        self._sslParams = None
        self._fileno = self.s.fileno()

    def isSslConnection(self):
        return bool(self._sslParams)

    def useSSL(self, *args, **kwargs):
        kwargs['do_handshake_on_connect'] = False
        self._sslParams = (args, kwargs)

    def shutDown(self):
        # Remove the callback and close the listening socket.
        self.pollManager.removeInputCallback(self._fileno)
        self.s.shutdown(socket.SHUT_RDWR)
        self.s.close()

    def onConnect(self, fd, ev):
        """Handle a client trying to connect.

        This is invoked by the `PollManager` when a client tries to connect.
        """
        # TODO: Add error handling
        s, addr = self.s.accept()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self._sslParams is not None:
            args, kwargs = self._sslParams
            kwargs['do_handshake_on_connect'] = False
            kwargs['server_side'] = True
            s = ssl.wrap_socket(s, *args, **kwargs)

            # Do the handshaking while the socket is in blocking mode. In
            # theory you can do it in non-blocking mode, but I think there
            # is a nasty timing bug in Python's wrapper or some versions of
            # the SSL library itself.
            s.do_handshake()

        active, ret = self.onConnectCB(s, self.peerName, addr, self)
        if not active:
            # There is nothing to handle the new connection so we immediately
            # shut it down and close it.
            # TODO: Add error handling
            s.shutdown(socket.SHUT_RDWR)
            s.close()


class Connecter:
    """A class to establish a connections on a socket

    Currently only AF_INET address family sockets are supported.
    """
    #{ Construction
    def __init__(self, pollManager, peerName, peerAddr, connectTimes,
                 onConnect=None, bindAddress=None):
        """Constructor:

        :Param pollManager:
            This is typically a `PollManager` instance, but could be something
            that provides the same interface.
        :Param peerAddr:
            The address to bind to before starting to listen. This is a tuple
            if (ip-address, port). The ip-address may be an empty string, meaning
            'localhost'.
        """
        self.pollManager = pollManager
        self.peerName = peerName
        self.peerAddr = peerAddr
        self.onConnectCB = CallbackRef(onConnect)
        self._sslHandshaker = None
        self._useSSL = False

        delay, self.retryPeriod = connectTimes
        self.s = s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.setblocking(0)
        if bindAddress:
            s.bind(bindAddress)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tid = self.pollManager.addTimeout(delay, self.onTryconnect)
        self.tid = self.pollManager.addRepeatingTimeout(
                self.retryPeriod, self.onTryconnect)
        self._fileno = self.s.fileno()

    def isSslConnection(self):
        return bool(self._sslHandshaker is not None)

    def useSSL(self, *args, **kwargs):
        kwargs['do_handshake_on_connect'] = False
        self.s = ssl.wrap_socket(self.s, *args, **kwargs)
        self._useSSL = True

    def onTryconnect(self):
        """Invoked by the `PollManager` when input is available."""
        try:
            self.s.connect(self.peerAddr)
        except socket.error as exc:
            code = exc.args[0]
            if code == errno.EINPROGRESS:
                return

        self.pollManager.removeTimeout(self.tid)
        self.tid = None

        if self._useSSL:
            # Do the handshaking while the socket is in blocking mode. In
            # theory you can do it in non-blocking mode, but I think there
            # is a nasty timing bug in Python's wrapper or some versions of
            # the SSL library itself.
            self.s.setblocking(1)
            self.s.do_handshake()
            self.s.setblocking(0)

        active, ret = self.onConnectCB(self.peerName, self)
        if not active:
            # TODO: Should we shutdown the connection.
            pass

    def shutDown(self):
        # Remove the callbacks and close the socket.
        self.pollManager.removeTimeout(self.tid)
        self.s.close()


class SocketConn:
    """A class to manage a socket connection.

    This basically wraps a ``socket.socket`` instance to provide better support
    for mock objects.

    Currently only AF_INET address family sockets are supported.
    """
    #{ Construction
    def __init__(self, s, peerName, pollManager, onReceive=None, onClose=None,
                 onError=None, native=False, addr=None, isSSL=False):
        """Constructor:

        :Parameters:
          s
            The active socket, as obtained from a call to the standard
            ``socket.socket``.
          peerName
            This should be a plain text string used to represent the peer
            entity at the other end of the socket. This name tends to get
            used in logging.
          pollManager
            The instance of `cleversheep3.Test.PollManager` to use provide
            events.
          onReceive
            An optional function to be invoked when input is received. The
            function is invoked as ``onReceive(self)``.
          onClose
            An optional function to be invoked when the socket is
            closed. The function is invoked as ``onClose(self)``.
          addr
            The peer's address if any.
          onError
            An optional function to be invoked when an exception occurs during
            a socket read. The function is invoked as ``onError(self, exc)``.
            Where ``exc`` is the exception that was handled.

            Note that EAGAIN and ECONNRESET do not cause this function to be
            invoked.
          native
            If set `True` then it assumed that the connection transmits in
            native (rather than network) byte order.

        """
        self.pollManager = pollManager
        self.s = s
        self._fileno = self.s.fileno()
        self.s.setblocking(0)
        self.peerName = peerName
        self.addr = addr
        self.onReceiveCB = CallbackRef(onReceive)
        self.onCloseCB = CallbackRef(onClose)
        self.onErrorCB = CallbackRef(onError)
        self.inBuf = ""
        self.outBuf = ""
        self.pollManager.addInputCallback(s, self._onInputActivity,)
        self._eofSeen = False
        self._native = native
        if isSSL:
            self._doRead = self.s.read
        else:
            self._doRead = self.s.recv

        # It seems that if some data has been sucked into the TCP stack quickly
        # enough then we get no file activity reported on the socket. This
        # initial read seems to sort things out.
        #
        # This seems wrong for a standard socket.
        self.pollManager.addCallback(self._doInitialRead, self.s.fileno())

    #{ Reading and writing
    def _handleEOF(self):
        """Handle attempt to read from socket when EOF has occurred.

        This is invoked by the `._read` method when EOF has been seen and
        there is no bufferred input data. It always invokes the onCloseCB and
        the first time it is called will remove callbacks and cleanly shutdown
        the socket.
        """
        self.onCloseCB(self)
        if self.s is not None:
            self.pollManager.removeOutputCallback(self._fileno)
            self.pollManager.removeInputCallback(self._fileno)
            try:
                self.s.shutdown(socket.SHUT_RDWR)
                self.s.close()
            except socket.error:
                pass # We are really beyond caring!
            self.s = None

    def _read(self):
        """Read some or all available data."""
        # Read in a loop until no more input is available. We must do this or
        # an SSLSocket can stop causing select events.
        data = []
        if self.s is None:
            if not self.inBuf:
                self._handleEOF()
            return

        while True:
            gotEOF = error = False
            try:
                s = self._doRead(readBlockSize)
                if not s:
                    gotEOF = True
                    self._eofSeen = True
                    break
                data.append(s)
            except ssl.SSLError as exc:
                if exc.args[0] == ssl.SSL_ERROR_WANT_READ:
                    break
            except socket.error as exc:
                if exc.args[0] == errno.ECONNRESET:
                    gotEOF = True
                elif exc.args[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                    pass
                break

        if data:
            # We read some data, so update the input buffer. If we also got EOF
            # then that will be handled when this gets called next time around.
            self.inBuf += ''.join(data)

        elif gotEOF:
            # The socket has been closed and we have no buffered data.
            if error:
                self.onErrorCB(self, error)
            self._handleEOF()

    def _onInputActivity(self, fd, ev):
        """Invoked when the socket has input activity.

        Basically this either means that there is data to read or the
        connection is shutting down. The latter case is indicated by a read
        attempt returning zero bytes.

        TODO: We can also get EAGAIN, but that is not yet handled.
        """
        self._read()
        if self.inBuf:
            active, ret = self.onReceiveCB(self)
            if not active:
                self.inBuf = ""

    def _doInitialRead(self, fd):
        self._read()
        if self.inBuf:
            active, ret = self.onReceiveCB(self)
            if not active:
                self.inBuf = ""

    def read(self):
        """Read all the data in the input buffer.

        The buffer is cleared.
        """
        s, self.inBuf = self.inBuf, ""
        return s

    def peek(self):
        """Peek at the data in the input buffer."""
        return self.inBuf

    def readMsg(self):
        """Read a complete message from the input buffer.

        The read bytes are removed from the input buffer.
        """
        if len(self.inBuf) < 4:
            return None

        buf = self.inBuf
        if self._native:
            (msgLen,) = struct.unpack("@L", buf[:4])
        else:
            (msgLen,) = struct.unpack("!L", buf[:4])
        if len(buf) < msgLen:
            return None

        msg, self.inBuf = buf[:msgLen], buf[msgLen:]
        return msg

    def send(self, bytes, count=None):
        """Send data to the peer.

        This simply sends (and logs) the the string `bytes` to the peer.

        Currently this only supports TCP. In the future it should support UDP
        as well; there is no plan to add a ``sendto`` method.

        :Param bytes:
            The string containing the bytes to send.
        :Param count:
            If supplied and non-zero then only the first `count` bytes will be
            sent.
        """
        if self.s is None:
            return
        count = count or len(bytes)
        alreadySending = bool(self.outBuf)
        self.outBuf += bytes[:count]
        if not alreadySending:
            ret = self.pollManager.addOutputCallback(self.s, self._onTryToSend)
            if ret == -1:
                # The socket has become unusable - the peer probably shut it
                # down.
                try:
                    self.pollManager.addTimeout(0,0, self.onCloseCB, self)
                    self.s.shutdown(socket.SHUT_RDWR)
                    self.s.close()
                except socket.error:
                    pass # We are really beyond caring!
                self.s = None
                return

        # Try poking things. so we detect socket shutdown earlier rather than
        # later.
        self._onTryToSend(None, None)

    def _doSend(self):
        mustClose = error = False
        sent = 0
        try:
            sent = self.s.send(self.outBuf[:writeBlockSize])
        except socket.error as exc:
            if exc.args[0] == errno.ECONNRESET:
                # A clean close.
                mustClose = True
            elif exc.args[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                pass
            else:
                # A non-clean close. TODO: Log something at least.
                mustClose = True
                error = exc

        if sent:
            self.outBuf = self.outBuf[sent:]
        return sent, mustClose, error

    def _onTryToSend(self, fd, ev):
        while True and self.outBuf:
            sent, mustClose, error = self._doSend()

            if mustClose:
                # If the connection has closed, ...
                if error:
                    self.pollManager.addTimeout(0.0, self.onErrorCB, self,
                            error)
                self.pollManager.addTimeout(0.0, self.onCloseCB, self)
                self.pollManager.removeOutputCallback(self._fileno)
                self.pollManager.removeInputCallback(self._fileno)
                self.outBuf = ""
                try:
                    self.s.shutdown(socket.SHUT_RDWR)
                    self.s.close()
                except socket.error:
                    pass # We are really beyond caring!
                self.s = None

            if sent == 0:
                break

        if not self.outBuf:
            self.pollManager.removeOutputCallback(self._fileno)

    #{ Shutdown and close
    # TODO: Should deregister as well.
    def shutDown(self, v=socket.SHUT_RDWR):
        self.pollManager.removeInputCallback(self._fileno)
        if self.s is None:
            return
        try:
            return self.s.shutdown(v)
        except socket.error:
            pass
        self.s.close()
    shutdown = shutDown

    def close(self):
        try:
            return self.s.close()
        except IOError:
            pass


class PipeConn:
    """A class to manage a pipe connection.

    This basically wraps an open pipe instance to provide better support
    for mock objects.

    """
    #{ Construction
    def __init__(self, isWrite, pipePath, peerName, pollManager,
            onReceive=None, onClose=None, onError=None, native=False):
        """Constructor:

        :Parameters:
          isWrite
            Set to ``True`` if the pipe is to be written to and ``False``
            for a pipe that should be read from.
          pipePath
            The name of the pipe file to be opened.
          peerName
            The name of the peer entity that is expected to send or receive
            data.
          pollManager
            This is typically a `cleversheep3.Test.PollManager` instance, but
            could be something that provides the same interface.
          onReceive
            An optional function to be invoked when input is received. The
            function is invoked as ``onReceive(self)``.
          onClose
            An optional function to be invoked when the socket is closed. The
            function is invoked as ``onClose(self)``.
          onError
            An optional function to be invoked when an exception occurs during
            a socket read. The function is invoked as ``onError(self, exc)``.
            Where ``exc`` is the exception that was handled.

            Note that EAGAIN and ECONNRESET do not cause this function to be
            invoked.
          native
            If set `True` then it assumed that the connection transmits in
            native (rather than network) byte order.

        """
        self.pollManager = pollManager
        self.pipeF = None
        self.pipePath = pipePath
        self.peerName = peerName
        self.isWrite = isWrite
        self.onReceiveCB = CallbackRef(onReceive)
        self.onCloseCB = CallbackRef(onClose)
        self.onErrorCB = CallbackRef(onError)
        self.inBuf = bytes()
        self.outBuf = bytes()
        self._native = native
        self._binary = False
        self.tryOpen()
        self._fileno = self.pipeF.fileno()

    def tryOpen(self):
        if self.pipeF is not None:
            return True
        try:
            if self.isWrite:
                fd = os.open(self.pipePath, os.O_WRONLY | os.O_NDELAY)
                self.pipeF = os.fdopen(fd, "w")
                self._fileno = self.pipeF.fileno()
                return True
            else:
                fd = os.open(self.pipePath, os.O_RDONLY | os.O_NDELAY)
                self.pipeF = os.fdopen(fd, "r")
                self._fileno = self.pipeF.fileno()
                self.pollManager.addInputCallback(self.pipeF,
                        self._onInputActivity,)
                return True
        except (OSError, IOError) as exc:
            pass

    def tryRead(self):
        try:
            s = self.pipeF.read(readBlockSize)
        except (OSError, IOError) as exc:
            if exc.args[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise
            self.pollManager.removeInputCallback(self._fileno)
            s = None
            try:
                self.pipeF.close()
            except (OSError, IOError):
                pass
            self.pipeF = None
        return s

    #{ Reading and writing
    def _onInputActivity(self, fd, ev):
        """Invoked when the socket has input activity.

        Basically this either means that there is data to read or the
        connection is shutting down. The latter case is indicated by a read
        attempt returning zero bytes.

        TODO: We can also get EAGAIN, but that is not yet handled.
        """
        mustClose = error = False
        try:
            s = self.tryRead()
            if not s:
                mustClose = True
        except (IOError, OSError) as exc:
            if exc.args[0] == errno.ECONNRESET:
                mustClose = True

            elif exc.args[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                # This can happen, even though this method is only called
                # when the socket supposedly has data ready to read.
                return

            else:
                # A non-clean close. TODO: Log something at least.
                mustClose = True
                error = exc

        if mustClose:
            # If the connection has closed, ...
            if error:
                self.onErrorCB(self, error)
            self.onCloseCB(self)
            self.pollManager.removeOutputCallback(self._fileno)
            self.pollManager.removeInputCallback(self._fileno)
            self.outBuf = bytes()
            try:
                self.s.shutdown(socket.SHUT_RDWR)
                self.s.close()
            except socket.error:
                pass # We are really beyond caring!
            self.s = None
            return

        self.inBuf += s
        active, ret = self.onReceiveCB(self)
        if not active:
            self.inBuf = ""

    def read(self):
        """Read all the data in the input buffer.

        The buffer is cleared.
        """
        s, self.inBuf = self.inBuf, ""
        return s

    def peek(self):
        """Peek at the data in the input buffer."""
        return self.inBuf

    def readMsg(self):
        """Read a complete message from the input buffer.

        The read bytes are removed from the input buffer.
        """
        if len(self.inBuf) < 4:
            return None

        buf = self.inBuf
        if self._native:
            (msgLen,) = struct.unpack("@L", buf[:4])
        else:
            (msgLen,) = struct.unpack("!L", buf[:4])

        msgLen += 4;
        if len(buf) < msgLen:
            return None

        msg, self.inBuf = buf[:msgLen], buf[msgLen:]
        return msg

    def send(self, bytes, count=None):
        """Send data to the peer.

        This simply sends (and logs) the the string `bytes` to the peer.

        Currently this only supports TCP. In the future it should support UDP
        as well; there is no plan to add a ``sendto`` method.

        :Param bytes:
            The string containing the bytes to send.
        :Param count:
            If supplied and non-zero then only the first `count` bytes will be
            sent.
        """
        count = count or len(bytes)
        if self._binary:
            if self._native:
                hdr = struct.pack("@L", count)
            else:
                hdr = struct.pack("!L", count)
        else:
            hdr = bytes()

        alreadySending = bool(self.outBuf)
        self.outBuf += hdr
        self.outBuf += bytes[:count]
        if not self.tryOpen():
            return

        if not alreadySending:
            ret = self.pollManager.addOutputCallback(self.pipeF,
                    self._onTryToSend)
            if ret == -1:
                # The pipe has become unusable - the peer probably shut it
                # down.
                try:
                    self.pipeF.close()
                except IOError:
                    pass # We are really beyond caring!
                self.s = None
                return

        # Try poking things. so we detect pipe closure earlier rather than
        # later.
        self._onTryToSend(None, None)

    def _onTryToSend(self, fd, ev):
        mustClose = error = False
        try:
            sent = os.write(self.pipeF.fileno(), self.outBuf[:1024])

        except (IOError, OSError) as exc:
            if exc.args[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                return

            else:
                # A non-clean close. TODO: Log something at least.
                mustClose = True
                error = exc

        if mustClose:
            # If the connection has closed, ...
            self.pollManager.removeOutputCallback(self._fileno)
            self.pollManager.removeInputCallback(self._fileno)
            self.outBuf = ""
            try:
                self.pipeF.close()
            except (IOError, OSError):
                pass # We are really beyond caring!
            self.pipeF = None
            return

        self.outBuf = self.outBuf[sent:]
        if not self.outBuf:
            self.pollManager.removeOutputCallback(self.pipeF)

    #{ Shutdown and close
    def shutDown(self, v=socket.SHUT_RDWR):
        self.pollManager.removeInputCallback(self._fileno)
    shutdown = shutDown

    def close(self):
        try:
            return self.pipeF.close()
        except IOError:
            pass


# TODO: Make this a specialisation of SocketConn provide SocketConn with a
#       frame extractor.
class LPSocketConn(SocketConn):
    """A specialisation of `SocketConn` that uses LP style messages.

    TODO: DO NOT USE. I have just left this here so I can copy the diagram to
    a better place.

    This is useful when all messages are a length (L) followed by the payload
    (P), which is a common enough scheme. This class assumes that the length
    is always in the first 4 bytes.::

                     +---+---+---+---+---+--- ... ---+---+
                     |    Length     |      Payload      |
                     +---+---+---+---+---+--- ... ---+---+

                     |<-------------- Length ----------->|
    """


if __name__ == "__main__":
    pollMan = PollManager.PollManager()

    def serve(args):
        port = int(args[0])
        ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ls.bind(('', port))
        ls.listen(1)
        print("Server listening on port %d" % port)

        s, addr = ls.accept()
        print('Received connection from', addr)

        s = LPSocketConn(s, "me", pollMan)
        while True:
            if options.messages:
                msg = s.recvMsg()
                if msg:
                    msg._meta.dump()
                else:
                    break
            else:
                bytes, addr = s.recvfrom()
                if bytes:
                    print(">>", `bytes`)
                else:
                    break


    def beClienty(args):
        port = int(args[0])
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('', port))
        print("Server connected to port %d" % port)

        class Msg(Struct):
            _byteOrder = Format.Network
            length = Type.UnsignedLong
            body = Type.String[1024]

        text = "Hello World"
        m1 = Msg()
        m1.length = len(text) + 4
        m1.body = text

        text = "Goodbye Cruel World"
        m2 = Msg()
        m2.length = len(text) + 4
        m2.body = text

        bytes = m1._meta.bytes[:m1.length]
        bytes += m2._meta.bytes[:m2.length]
        s.send(bytes)
        s.shutdown(socket.SHUT_RDWR)
        s.close()


    import optparse
    usage = "usage: %prog [options] port"
    parser = optparse.OptionParser(usage)

    parser.add_option("--server", action="store_true",
                      help="Run as a TCP server")
    parser.add_option("--messages", action="store_true",
                      help="Send/receive messages")

    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error("Wrong number of arguments")

    if options.server:
        serve(args)
    else:
        beClienty(args)
