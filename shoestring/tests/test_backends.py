import os
import time
import uuid

from contextlib import contextmanager
from unittest.mock import Mock

from tornado import gen
from tornado.websocket import WebSocketClosedError
from tornado.testing import AsyncTestCase, gen_test

from ..backends.memory import Backend as MemoryBackend
from ..backends.redis import Backend as RedisBackend


class BackendAPIMixin(object):
    """Defines tests for the backend API."""

    backend_class = None

    def setUp(self):
        super().setUp()
        self.backend = self.backend_class()

    def get_socket(self):
        return Mock(uuid=uuid.uuid4().hex)

    @contextmanager
    def environ(self, key, value):
        """Helper to temporarily change os.environ values and restore them."""
        original = os.environ.get(key, None)
        if value is None:
            if key in os.environ:
                del os.environ[key]
        else:
            os.environ[key] = value
        try:
            yield
        finally:
            if original is None:
                if key in os.environ:
                    del os.environ[key]
            else:
                os.environ[key] = original

    @gen.coroutine
    def pause(self, seconds=0.1):
        yield gen.Task(self.io_loop.add_timeout, time.time() + seconds)

    def test_create_room(self):
        """Create a new room and return the name."""
        room = self.backend.create_room('XXX')
        self.assertTrue(isinstance(room, str))
        self.assertGreaterEqual(len(room), 5)

    def test_join_room(self):
        """Join an existing room and return the name."""
        room = self.backend.create_room('XXX')
        result = self.backend.join_room(room, 'YYY')
        self.assertEqual(room, result)

    def test_join_room_missing(self):
        """Joining a room which doesn't exist raises a KeyError."""
        with self.assertRaises(KeyError):
            result = self.backend.join_room('123', 'YYY')

    def test_get_room(self):
        """Get a list of members in the room with their subscription status."""
        room = self.backend.create_room('XXX')
        result = self.backend.get_room(room)
        self.assertEqual(result, {'XXX': False})
        self.backend.join_room(room, 'YYY')
        result = self.backend.get_room(room)
        self.assertEqual(result, {'XXX': False, 'YYY': False})

    def test_get_room_missing(self):
        """Getting a room which doesn't exist raises a KeyError."""
        with self.assertRaises(KeyError):
            result = self.backend.get_room('123')

    def test_add_subscriber(self):
        """Subscribe a websocket to a channel."""
        socket = self.get_socket()
        self.backend.add_subscriber('123', socket)
        result = self.backend.get_subscribers(channel='123')
        self.assertEqual(list(result), [socket, ])

    def test_add_room_subscriber(self):
        """Subscribe a websocket to a room channel."""
        socket = self.get_socket()
        room = self.backend.create_room(socket.uuid)
        self.backend.add_subscriber(room, socket)
        result = self.backend.get_room(room)
        self.assertEqual(result, {socket.uuid: True})

    def test_add_already_subscribed(self):
        """Sockets cannot subscribe to a room channel more than once."""
        socket = self.get_socket()
        room = self.backend.create_room(socket.uuid)
        self.backend.add_subscriber(room, socket)
        with self.assertRaises(ValueError):
            self.backend.add_subscriber(room, socket)

    def test_remove_subscriber(self):
        """Remove websocket subscriber."""
        socket = self.get_socket()
        self.backend.add_subscriber('123', socket)
        result = self.backend.get_subscribers(channel='123')
        self.assertEqual(set(result), set([socket, ]))
        self.backend.remove_subscriber('123', socket)
        result = self.backend.get_subscribers(channel='123')
        self.assertEqual(set(result), set([]))

    def test_remove_room_subscriber(self):
        """Remove websocket subscriber to a room channel and update status."""
        socket = self.get_socket()
        room = self.backend.create_room(socket.uuid)
        self.backend.add_subscriber(room, socket)
        result = self.backend.get_room(room)
        self.assertEqual(result, {socket.uuid: True})
        self.backend.remove_subscriber(room, socket)
        result = self.backend.get_room(room)
        self.assertEqual(result, {socket.uuid: False})

    @gen_test
    def test_broadcast(self):
        """Broadcast message to other channel subscribers."""
        socket = self.get_socket()
        peer = self.get_socket()
        self.backend.add_subscriber('123', socket)
        self.backend.add_subscriber('123', peer)
        self.backend.broadcast(message='ping', channel='123', sender=socket.uuid)
        yield self.pause()
        peer.write_message.assert_called_with('ping')
        self.assertFalse(socket.write_message.called)

    @gen_test
    def test_broadcast_alone(self):
        """Broadcast message into single occupied channel."""
        socket = self.get_socket()
        peer = self.get_socket()
        self.backend.add_subscriber('123', socket)
        self.backend.add_subscriber('456', peer)
        self.backend.broadcast(message='ping', channel='123', sender=socket.uuid)
        yield self.pause()
        self.assertFalse(peer.write_message.called)
        self.assertFalse(socket.write_message.called)

    @gen_test
    def test_broadcast_empty(self):
        """Broadcast message into empty channel."""
        socket = self.get_socket()
        peer = self.get_socket()
        self.backend.broadcast(message='ping', channel='123', sender=socket.uuid)
        yield self.pause()
        self.assertFalse(peer.write_message.called)
        self.assertFalse(socket.write_message.called)

    @gen_test
    def test_broadcast_dead_peer(self):
        """Remove dead peers detected on broadcast."""
        socket = self.get_socket()
        peer = self.get_socket()
        peer.write_message.side_effect = WebSocketClosedError('Already closed.')
        self.backend.add_subscriber('123', socket)
        self.backend.add_subscriber('123', peer)
        result = self.backend.get_subscribers(channel='123')
        self.assertEqual(set(result), set([socket, peer]))
        self.backend.broadcast(message='ping', channel='123', sender=socket.uuid)
        yield self.pause()
        result = self.backend.get_subscribers(channel='123')
        self.assertEqual(set(result), set([socket]))

    def test_graceful_shutdown(self):
        """Notify all subscribers when the server is shutting down gracefully."""
        socket = self.get_socket()
        peer = self.get_socket()
        self.backend.add_subscriber('123', socket)
        self.backend.add_subscriber('456', peer)
        self.backend.shutdown(graceful=True)
        socket.close.assert_called_with(code=4200, reason='Server shutdown.')
        peer.close.assert_called_with(code=4200, reason='Server shutdown.')

    def test_fast_shutdown(self):
        """Notify all subscribers when the server is shutting down immediately."""
        socket = self.get_socket()
        peer = self.get_socket()
        self.backend.add_subscriber('123', socket)
        self.backend.add_subscriber('456', peer)
        self.backend.shutdown(graceful=False)
        socket.close.assert_called_with(code=4100, reason='Server shutdown.')
        peer.close.assert_called_with(code=4100, reason='Server shutdown.')


class MemoryBackendTestCase(BackendAPIMixin, AsyncTestCase):

    backend_class = MemoryBackend


class RedisBackendTestCase(BackendAPIMixin, AsyncTestCase):

    backend_class = RedisBackend

    def test_default_connection(self):
        """Handle missing connection string."""
        with self.environ('SHOESTRING_REDIS_URL', None):
            self.assertEqual(self.backend.parse_redis_parameters(), {})

    def test_parse_connection(self):
        """Parse connection string from the OS environment."""
        expected = {
            'host': 'example.com',
            'port': 1234,
            'password': 'pass',
            'db': 0
        }
        url = 'redis://:{password}@{host}:{port}'.format(**expected)
        with self.environ('SHOESTRING_REDIS_URL', url):
            self.assertEqual(self.backend.parse_redis_parameters(), expected)

    def test_invalid_connection(self):
        """Raise an error in improperly formatted connection strings."""
        with self.environ('SHOESTRING_REDIS_URL', 'XXXXXXXXX'):
            with self.assertRaises(RuntimeError):
                print(self.backend.parse_redis_parameters())

    def test_optional_db(self):
        """URL path can be used to configure the DB."""
        expected = {
            'host': 'example.com',
            'port': 1234,
            'password': None,
            'db': 2
        }
        url = 'redis://{host}:{port}/{db}'.format(**expected)
        with self.environ('SHOESTRING_REDIS_URL', url):
            self.assertEqual(self.backend.parse_redis_parameters(), expected)

    def test_invalid_db(self):
        """DB must be a integer."""
        with self.environ('SHOESTRING_REDIS_URL', 'redis://example.com:1234/foo'):
            with self.assertRaises(RuntimeError):
                self.backend.parse_redis_parameters()
