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


class BackendMixin(object):
    """Mixin class for accepting the backend on creation."""

    def initialize(self, backend):
        self.backend = backend


class SocketHandler(BackendMixin, WebSocketHandler):
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
                self.backend.add_subscriber(self.channel, self)

    def on_message(self, message):
        """Broadcast updates to other interested clients."""
        if self.channel is not None and self.uuid is not None:
            self.backend.broadcast(message, channel=self.channel, sender=self.uuid)

    def on_close(self):
        """Remove subscription."""
        if self.channel is not None:
            self.backend.remove_subscriber(self.channel, self)


class RoomHandlerMixin(object):
    """Helper methods for handling rooms."""

    def build_room_token(self, room, user):
        """Build a JSON web token for the room/user."""
        return jwt.encode({
            'room': room,
            'uuid': user,
            'exp': datetime.datetime.utcnow() +  datetime.timedelta(minutes=10)
        }, self.settings['secret'])

    def build_socket_url(self, room, user):
        """Build socket url for connecting to the given room."""
        token = self.build_room_token(room, user)
        protocol = 'wss' if self.request.protocol == 'https' else 'ws'
        return url_concat('{}://{}/socket'.format(protocol, self.request.host), {'token': token})


class CreateRoomHandler(BackendMixin, RoomHandlerMixin, RequestHandler):
    """Create rooms."""

    def post(self):
        user = uuid.uuid4().hex
        room = self.backend.create_channel(user)
        result = {
            'room': room,
            'socket': self.build_socket_url(room, user)
        }
        self.write(result)


class GetRoomHandler(BackendMixin, RoomHandlerMixin, RequestHandler):
    """Join room."""

    def get(self, room):
        user = uuid.uuid4().hex
        room = self.backend.get_channel(room, user)
        result = {
            'room': room,
            'socket': self.build_socket_url(room, user)
        }
        self.write(result)


class IndexHandler(RequestHandler):
    """Render the homepage."""

    def get(self):
        self.render('index.html')
