import datetime
import logging
import os
import random
import uuid

from urllib.parse import urlparse

import jwt

from tornado.httputil import url_concat
from tornado.options import options
from tornado.web import RequestHandler, HTTPError
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
            self.close(code=4000, reason='Missing token.')
        else:
            try:
                info = jwt.decode(token, self.settings['secret'])
            except (jwt.DecodeError, jwt.ExpiredSignature):
                self.close(code=4000, reason='Invalid token.')
            else:
                channel = self.get_argument('channel', None)
                if channel is None or channel == info['room']:
                    self.channel = info['room']
                elif channel == info['uuid']:
                    self.channel = info['uuid']
                elif channel in self.backend.get_members(info['room']):
                    # Validate the channel as another user's uuid
                    self.channel = channel
                else:
                    self.close(code=4000, reason='Invalid channel.')
                self.uuid = info['uuid']
                try:
                    self.backend.add_subscriber(self.channel, self)
                except ValueError:
                    self.close(code=4000, reason='Invalid token.')

    def on_message(self, message):
        """Broadcast updates to other interested clients."""
        if self.channel is not None and self.uuid is not None:
            logging.info('Message %s', message)
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
            'exp': datetime.datetime.utcnow() +  datetime.timedelta(hours=8)
        }, self.settings['secret']).decode('utf-8')

    def build_socket_url(self):
        """Build socket url."""
        protocol = 'wss' if self.request.protocol == 'https' else 'ws'
        return '{}://{}/socket'.format(protocol, self.request.host)


class CreateRoomHandler(BackendMixin, RoomHandlerMixin, RequestHandler):
    """Create rooms."""

    def post(self):
        user = uuid.uuid4().hex
        room = self.backend.create_channel(user)
        result = {
            'room': room,
            'user': user,
            'token': self.build_room_token(room, user),
            'socket': self.build_socket_url()
        }
        self.write(result)


class GetRoomHandler(BackendMixin, RoomHandlerMixin, RequestHandler):
    """Join room."""

    def get(self, room):
        user = uuid.uuid4().hex
        try:
            room = self.backend.get_channel(room, user)
        except KeyError:
            raise HTTPError(404)
        result = {
            'room': room,
            'user': user,
            'token': self.build_room_token(room, user),
            'socket': self.build_socket_url()
        }
        self.write(result)


class IndexHandler(RequestHandler):
    """Render the homepage."""

    def get(self):
        self.render('index.html')
