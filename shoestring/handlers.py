import datetime
import os
import random
import uuid

from urllib.parse import urlparse

import jwt

from tornado.httputil import url_concat
from tornado.options import options
from tornado.web import RequestHandler
from tornado.websocket import WebSocketHandler


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
