# -*- encoding: utf8 -*-
#
# Simple WebSockets in Python
# By Håvard Gulldahl <havard@gulldahl.no>
#
# Based on example by David Arthur (he did all the hard work :)
# https://gist.github.com/512987
#

import struct
import socket
import hashlib
import sys
import re
import logging
import signal
import asyncore
from base64 import b64encode
from hashlib import sha1
from mimetools import Message
from StringIO import StringIO

logger = logging.getLogger(__name__)

TEXT = 0x01
BINARY = 0x02

class WebSocket(asyncore.dispatcher_with_send):
    handshaken = False
    header = ""
    data = ""
    magic = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

    def _init__(self, client, server):
        asyncore.dispatcher_with_send.__init__(self)
        self.client = client
        self.server = server
        self.handshaken = False
        self.header = ""
        self.data = ""

    def set_server(self, server):
        self.server = server

    def handle_read(self):
        logging.info("Getting data from client")
        data = self.recv(1024)
        if not self.handshaken:
            if self.handshake(data):
                self.handshaken = True
        else:
            #self.read_next_message(data)
            msg = self.decodeCharArray(data)
            self.onmessage("".join(msg).strip()) 
                    
    def handshake(self, data):
        print(data)
        headers = Message(StringIO(data.strip().split('\r\n', 1)[1]))
        if headers.get("Upgrade", None) != "websocket":
            return False
        logging.debug("handshaking...")
        key = headers['Sec-WebSocket-Key']
        digest = b64encode(sha1(key + self.magic).hexdigest().decode('hex'))
        response = 'HTTP/1.1 101 Switching Protocols\r\n'
        response += 'Upgrade: websocket\r\n'
        response += 'Connection: Upgrade\r\n'
        response += 'Sec-WebSocket-Accept: %s\r\n\r\n' % digest
        #self.handshake_done = self.request.send(response)
        self.out_buffer = response
        return True

    # from http://stackoverflow.com/questions/8125507/how-can-i-send-and-receive-websocket-messages-on-the-server-side
    def decodeCharArray(self, stringStreamIn):
    
        # Turn string values into opererable numeric byte values
        byteArray = [ord(character) for character in stringStreamIn]
        datalength = byteArray[1] & 127
        indexFirstMask = 2

        if datalength == 126:
            indexFirstMask = 4
        elif datalength == 127:
            indexFirstMask = 10

        # Extract masks
        masks = [m for m in byteArray[indexFirstMask : indexFirstMask+4]]
        indexFirstDataByte = indexFirstMask + 4
        
        # List of decoded characters
        decodedChars = []
        i = indexFirstDataByte
        j = 0
        
        # Loop through each byte that was received
        while i < len(byteArray):
        
            # Unmask this byte and add to the decoded buffer
            decodedChars.append( chr(byteArray[i] ^ masks[j % 4]) )
            i += 1
            j += 1

        # Return the decoded string
        return decodedChars
        
    def read_next_message(self, data):
        length = ord(data[:2][1]) & 127
        if length == 126:
            length = struct.unpack(">H", self.rfile.read(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self.rfile.read(8))[0]
        masks = [ord(byte) for byte in self.rfile.read(4)]
        decoded = ""
        for char in self.rfile.read(length):
            decoded += chr(ord(char) ^ masks[len(decoded) % 4])
        self.on_message(decoded)

    def sendMessage(self, s):
        """
        Encode and send a WebSocket message
        """

        # Empty message to start with
        message = ""
        
        # always send an entire message as one frame (fin)
        b1 = 0x80

        # in Python 2, strs are bytes and unicodes are strings
        if type(s) == unicode:
            b1 |= TEXT
            payload = s.encode("UTF8")
            
        elif type(s) == str:
            b1 |= TEXT
            payload = s

        # Append 'FIN' flag to the message
        message += chr(b1)

        # never mask frames from the server to the client
        b2 = 0
        
        # How long is our payload?
        length = len(payload)
        if length < 126:
            b2 |= length
            message += chr(b2)
        
        elif length < (2 ** 16) - 1:
            b2 |= 126
            message += chr(b2)
            l = struct.pack(">H", length)
            message += l
        
        else:
            l = struct.pack(">Q", length)
            b2 |= 127
            message += chr(b2)
            message += l

        # Append payload to message
        message += payload

        # Send to the client
        self.out_buffer = str(message)
                                         
    def onmessage(self, data):
        logging.info("Got message: %s" % data)
        self.sendMessage( data + " back")

    def send(self, data):
        logging.info("Sent message: %s" % data)
        self.out_buffer = "\x00%s\xff" % data

class WebSocketServer(asyncore.dispatcher):
    def __init__(self, bind, port, cls=WebSocket):
        asyncore.dispatcher.__init__(self)
        self.port = port
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bind((bind, port))
        self.socketbind = bind
        self.cls = cls
        self.connections = {}
        self.listen(5)
        logging.info("Listening on %s" % self.port)
        self.running = True

    def handle_accept(self):
        logging.debug("New client connection")
        client, address = self.accept()
        fileno = client.fileno()
        self.connections[fileno] = self.cls(client)
        self.connections[fileno].set_server(self)

def SetupWebSocket(host, port):
    logging.info("Starting WebSocketServer on %s, port %s", host, port)
    server = WebSocketServer("localhost", 9004) 
    return server

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
    server = SetupWebSocket("localhost", 9004) 
    def signal_handler(signal, frame):
        logging.info("Caught Ctrl+C, shutting down...")
        server.running = False
        server.close()
        sys.exit()
    signal.signal(signal.SIGINT, signal_handler)
    asyncore.loop()
