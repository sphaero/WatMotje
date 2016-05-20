from yowsup.layers.interface                           import YowInterfaceLayer, ProtocolEntityCallback
from yowsup.stacks import  YowStackBuilder
from yowsup.layers.auth import AuthError
from yowsup.layers import YowLayerEvent
from yowsup.layers.network import YowNetworkLayer
from yowsup.layers.axolotl.layer import YowAxolotlLayer
import sys
import asyncore, socket
import time
import json
from BaseHTTPServer import BaseHTTPRequestHandler
from StringIO import StringIO
from websocketserver import *
import logging

msgs = []

# http://stackoverflow.com/questions/4685217/parse-raw-http-headers
class HTTPRequest(BaseHTTPRequestHandler):
    def __init__(self, request_text):
        self.rfile = StringIO(request_text)
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()

    def send_error(self, code, message):
        self.error_code = code
        self.error_message = message


class HTTPHandler(asyncore.dispatcher):
    def __init__(self, client, addr, server):
        asyncore.dispatcher.__init__(self, client)

    def handle_read(self):
        data = self.recv(1024)
        print(data)
        request = HTTPRequest(data)
        print(request.command, request.headers.keys())
        if request.path == '/':
            with open('test.html', 'r+') as f:
                data = f.read()
            self.send('HTTP/1.1 200 OK\n\n{0}'.format(data))
        else:
            ret_msg = json.dumps(msgs)
            self.send('HTTP/1.1 200 OK\nContent-Type: application/json\n\n{0}'.format(json.dumps(msgs)))
        self.close()


class HTTPServer(asyncore.dispatcher):
    def __init__(self, addr):
        self.addr = addr

        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)

        self.set_reuse_addr()
        self.bind(self.addr)
        self.listen(5)
        print('Listening on port %d' % addr[1])

    def handle_accept(self):
        (client, addr) = self.accept()
        print('Request from %s:%s' % (addr[0], addr[1]))
        HTTPHandler(client, addr, self)


class YowsupEchoStack(object):
    def __init__(self, credentials, encryptionEnabled = True):
        stackBuilder = YowStackBuilder()

        self.stack = stackBuilder\
            .pushDefaultLayers(encryptionEnabled)\
            .push(EchoLayer)\
            .build()

        self.stack.setCredentials(credentials)
        self.stack.setProp(YowAxolotlLayer.PROP_IDENTITY_AUTOTRUST, True)

    def start(self):
        self.stack.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))
        try:
            self.stack.loop()
        except AuthError as e:
            print("Authentication Error: %s" % e.message)


class EchoLayer(YowInterfaceLayer):

    @ProtocolEntityCallback("message")
    def onMessage(self, messageProtocolEntity):

        if messageProtocolEntity.getType() == 'text':
            self.onTextMessage(messageProtocolEntity)
        elif messageProtocolEntity.getType() == 'media':
            self.onMediaMessage(messageProtocolEntity)

        #self.toLower(messageProtocolEntity.forward(messageProtocolEntity.getFrom()))
        self.toLower(messageProtocolEntity.ack())
        self.toLower(messageProtocolEntity.ack(True))

    @ProtocolEntityCallback("receipt")
    def onReceipt(self, entity):
        self.toLower(entity.ack())

    def onTextMessage(self,messageProtocolEntity):
        msg = messageProtocolEntity.getBody()
        print("Echoing %s to %s" % (msg, messageProtocolEntity.getFrom(False)))
        msgs.append(msg)
        with open("messages.txt", "a") as f:
            f.write("{0};{1}\n".format(time.time(), msg))

    def onMediaMessage(self, messageProtocolEntity):
        # just print info
        if messageProtocolEntity.getMediaType() == "image":
            print("Echoing image %s to %s" % (messageProtocolEntity.url, messageProtocolEntity.getFrom(False)))

        elif messageProtocolEntity.getMediaType() == "location":
            print("Echoing location (%s, %s) to %s" % (messageProtocolEntity.getLatitude(), messageProtocolEntity.getLongitude(), messageProtocolEntity.getFrom(False)))

        elif messageProtocolEntity.getMediaType() == "vcard":
            print("Echoing vcard (%s, %s) to %s" % (messageProtocolEntity.getName(), messageProtocolEntity.getCardData(), messageProtocolEntity.getFrom(False)))


if __name__ == '__main__':
    #logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

    try:
        with open("messages.txt", "r+") as f:
            data = f.read()
        for msg in data.split('\n'):
            try:
                msgs.append(msg.split(';')[1])
            except IndexError:
                pass
        credentials = ("31644498790", "zbDuAd06fz2nH7QjXpiktwJ3qQY=")
        server = HTTPServer(('', 8080))
        
        # ws server
        host=""
        port=9004
        print("Starting WebSocketServer on %s, port %s" %(host, port))
        wsserver = WebSocketServer(host, port)
        
        #asyncore.loop()
        stack = YowsupEchoStack(credentials, True)
        stack.start()
    except KeyboardInterrupt:
        print("\nYowsdown")
    #finally:
        wsserver.running = False
        wsserver.close()
        #server.close()
        sys.exit(0)
