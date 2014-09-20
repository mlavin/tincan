import datetime
import json
import logging
import os
import random
import signal
import time
import uuid

from urllib.parse import urlparse

import jwt

from redis import Redis
from tornado.httpserver import HTTPServer
from tornado.httputil import url_concat
from tornado.ioloop import IOLoop
from tornado.options import define, parse_command_line, options
from tornado.web import Application, RequestHandler
from tornado.websocket import WebSocketHandler, WebSocketClosedError
from tornadoredis import Client
from tornadoredis.pubsub import BaseSubscriber


define('debug', default=False, type=bool, help='Run in debug mode')
define('port', default=8080, type=int, help='Server port')
define('allowed_hosts', multiple=True, help='Allowed hosts for cross domain connections')


class RedisSubscriber(BaseSubscriber):

    def on_message(self, msg):
        """Handle new message on the Redis channel."""
        if msg and msg.kind == 'message':
            try:
                message = json.loads(msg.body)
                sender = message['sender']
                message = message['message']
            except (ValueError, KeyError):
                logging.warning('Invalid channel mesage: {}'.format(msg.body))
            else:
                subscribers = list(self.subscribers[msg.channel].keys())
                for subscriber in subscribers:
                    if sender != subscriber.uuid:
                        try:
                            subscriber.write_message(message)
                        except tornado.websocket.WebSocketClosedError:
                            # Remove dead peer
                            self.unsubscribe(msg.channel, subscriber)
        super().on_message(msg)


class SocketHandler(WebSocketHandler):
    """Websocket signal handler."""

    def check_origin(self, origin):
        allowed = super().check_origin(origin)
        parsed = urlparse(origin.lower())
        matched = any(parsed.netloc == host for host in options.allowed_hosts)
        return options.debug or allowed or matched

    def open(self):
        """Subscribe to channel updates on a new connection."""
        self.channel = None
        token = self.get_argument('token', None)
        if not token:
            self.close()
        else:
            try:
                info = jwt.decode(token, self.settings['secret'])
            except (jwt.DecodeError, jwt.ExpiredSignature):
                self.close()
            else:
                self.channel = info['room']
                self.uuid = info['uuid']
                self.application.add_subscriber(self.channel, self)

    def on_message(self, message):
        """Broadcast updates to other interested clients."""
        if self.channel is not None and self.uuid is not None:
            self.application.broadcast(message, channel=self.channel, sender=self.uuid)

    def on_close(self):
        """Remove subscription."""
        if self.channel is not None:
            self.application.remove_subscriber(self.channel, self)


class CreateRoomHandler(RequestHandler):
    """Create rooms."""

    def post(self):
        room = '{}'.format(random.SystemRandom().randint(10 ** 4, 10 ** 5 - 1))
        token = jwt.encode({
            'room': room,
            'uuid': uuid.uuid4().hex,
            'exp': datetime.datetime.utcnow() +  datetime.timedelta(minutes=10)
        }, self.settings['secret'])
        result = {
            'room': room,
            'socket': url_concat('ws://{}/socket'.format(self.request.host), {'token': token})
        }
        self.write(result)


class GetRoomHandler(RequestHandler):
    """Join room."""

    def get(self, room):
        token = jwt.encode({
            'room': room,
            'uuid': uuid.uuid4().hex,
            'exp': datetime.datetime.utcnow() +  datetime.timedelta(minutes=10)
        }, self.settings['secret'])
        result = {
            'room': room,
            'socket': url_concat('ws://{}/socket'.format(self.request.host), {'token': token})
        }
        self.write(result)


class IndexHandler(RequestHandler):
    """Render the homepage."""

    def get(self):
        self.render('index.html')


class ShoestringApplication(Application):

    def __init__(self, **kwargs):
        routes = [
            (r'/rooms$', CreateRoomHandler),
            (r'/rooms/(?P<room>[0-9]+)$', GetRoomHandler),
            (r'/socket$', SocketHandler),
            (r'/$', IndexHandler),
        ]
        settings = {
            'template_path': os.path.join(os.path.dirname(__file__), 'templates'),
            'static_path': os.path.join(os.path.dirname(__file__), 'static'),
            'static_url_prefix': '/static/',
            'secret': 'XXXXXXXXX',
        }
        settings.update(kwargs)
        super().__init__(routes, **settings)
        self.subscriber = RedisSubscriber(Client())
        self.publisher = Redis()

    def add_subscriber(self, channel, subscriber):
        self.subscriber.subscribe(channel, subscriber)

    def remove_subscriber(self, channel, subscriber):
        self.subscriber.unsubscribe(channel, subscriber)

    def broadcast(self, message, channel, sender):
        message = json.dumps({
            'sender': sender,
            'message': message
        })
        self.publisher.publish(channel, message)


def shutdown(server):
    ioloop = IOLoop.instance()
    logging.info('Stopping server.')
    server.stop()

    def finalize():
        ioloop.stop()
        logging.info('Stopped.')

    ioloop.add_timeout(time.time() + 1.5, finalize)


if __name__ == "__main__":
    parse_command_line()
    application = ShoestringApplication(debug=options.debug)
    server = HTTPServer(application)
    server.listen(options.port)
    signal.signal(signal.SIGINT, lambda sig, frame: shutdown(server))
    logging.info('Starting server on localhost:{}'.format(options.port))
    IOLoop.instance().start()
