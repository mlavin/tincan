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


class TokenError(Exception):

    def __init__(self, code, reason):
        self.code = code
        self.reason = reason
        super().__init__('Invalid Token: {} ({})'.format(reason, code))


class SocketHandler(BackendMixin, WebSocketHandler):
    """Websocket signal handler."""

    def check_origin(self, origin):
        allowed = super().check_origin(origin)
        parsed = urlparse(origin.lower())
        matched = any(parsed.netloc == host for host in options.allowed_hosts)
        return options.debug or allowed or matched

    def _get_channel(self):
        token = self.get_argument('token', None)
        if not token:
            raise TokenError(code=4300, reason='Missing token.')
        try:
            info = jwt.decode(token, self.settings['secret'])
        except (jwt.DecodeError, jwt.ExpiredSignature):
            raise TokenError(code=4000, reason='Invalid token.')
        channel = self.get_argument('channel', None)
        try:
            members = self.backend.get_room(info['room'])
        except KeyError:
            raise TokenError(code=4300, reason='Invalid channel.')
        else:  
            if channel is None or channel == info['room']:
                channel = info['room']
            elif channel == info['uuid']:
                channel = info['uuid']
            elif channel in members:
                channel = channel
            else:
                raise TokenError(code=4300, reason='Invalid channel.')
            uuid = info['uuid']
            return (channel, uuid)

    def open(self):
        """Subscribe to channel updates on a new connection."""
        try:
            self.channel, self.uuid = self._get_channel()
        except TokenError as e:
            self.channel, self.uuid = None, None
            self.close(code=e.code, reason=e.reason)
        else:
            try:
                self.backend.add_subscriber(self.channel, self)
            except ValueError:
                self.channel, self.uuid = None, None
                self.close(code=4300, reason='Invalid channel.')

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
        room = self.backend.create_room(user)
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
            room = self.backend.join_room(room, user)
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
