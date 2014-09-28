import json

from contextlib import contextmanager
from unittest.mock import patch

import jwt

from tornado import gen
from tornado.concurrent import Future
from tornado.httpclient import HTTPRequest, HTTPError
# from tornado.options import options
from tornado.testing import AsyncHTTPTestCase, LogTrapTestCase, gen_test
from tornado.websocket import websocket_connect

from ..app import ShoestringApplication


class BaseAppTestCase(AsyncHTTPTestCase, LogTrapTestCase):
    """Base class for testing ShoestringApplication and handlers."""

    def get_app(self):
        return ShoestringApplication(secret='XXXX', debug=False, allowed_hosts=['example.com', ])

    def assertJSON(self, response, expected_status=200):
        """Return context manager for asserting JSON responses."""
        self.assertEqual(response.code, expected_status)
        try:
            result = json.loads(response.body.decode('utf-8'))
        except:
            self.fail('Received non-JSON response.')
        else:
            @contextmanager
            def json_context():
                yield result
        return json_context()


class RoomHandlerTestCase(BaseAppTestCase):
    """URL for creating and fetching rooms."""

    @patch('shoestring.backends.memory.Backend.create_room')
    def test_create_room(self, mock_create):
        """Create a new room."""
        mock_create.return_value = '1234'
        response = self.fetch('/rooms', method='POST', body='')
        self.assertTrue(mock_create.called)
        with self.assertJSON(response) as result:
            self.assertEqual(result['room'], '1234')

    @patch('shoestring.backends.memory.Backend.create_room')
    def test_new_room_socket(self, mock_create):
        """Creating a room should return info to connect to the websocket."""
        mock_create.return_value = '1234'
        response = self.fetch('/rooms', method='POST', body='')
        with self.assertJSON(response) as result:
            protocol = 'ws' if self.get_protocol() == 'http' else 'wss'
            expected = '{}://localhost:{}/socket'.format(protocol, self.get_http_port())
            self.assertEqual(result['socket'], expected)
            self.assertIn('user', result)
            self.assertIn('token', result)
            user, token = result['user'], result['token']
            info = jwt.decode(token, 'XXXX')
            self.assertEqual(info['uuid'], user)
            self.assertEqual(info['room'], '1234')

    @patch('shoestring.backends.memory.Backend.join_room')
    def test_existing_room(self, mock_join):
        """Join an existing room."""
        mock_join.return_value = '1234'
        response = self.fetch('/rooms/1234', method='GET')
        self.assertTrue(mock_join.called)
        with self.assertJSON(response) as result:
            self.assertEqual(result['room'], '1234')

    @patch('shoestring.backends.memory.Backend.join_room')
    def test_join_room_socket(self, mock_join):
        """Joining a room should return info to connect to the websocket."""
        mock_join.return_value = '1234'
        response = self.fetch('/rooms/1234', method='GET')
        self.assertTrue(mock_join.called)
        with self.assertJSON(response) as result:
            protocol = 'ws' if self.get_protocol() == 'http' else 'wss'
            expected = '{}://localhost:{}/socket'.format(protocol, self.get_http_port())
            self.assertEqual(result['socket'], expected)
            self.assertIn('user', result)
            self.assertIn('token', result)
            user, token = result['user'], result['token']
            info = jwt.decode(token, 'XXXX')
            self.assertEqual(info['uuid'], user)
            self.assertEqual(info['room'], '1234')

    @patch('shoestring.backends.memory.Backend.join_room')
    def test_missing_room(self, mock_join):
        """Try to join a non-existant room."""
        mock_join.side_effect = KeyError('Unknown room.')
        response = self.fetch('/rooms/1234', method='GET')
        self.assertTrue(mock_join.called)
        self.assertEqual(response.code, 404)


class SocketTestCase(BaseAppTestCase):
    """Websocket URL for signal channels."""

    @gen.coroutine
    def ws_connect(self, path):
        ws = yield websocket_connect(
            'ws://localhost:%d%s' % (self.get_http_port(), path))
        raise gen.Return(ws)

    @gen.coroutine
    def close(self, ws):
        """Close a websocket connection and wait for the server side."""
        ws.close()
        yield ws.read_message()

    def assertSocketError(self, ws, code, reason):
        """Assert websocket close error."""
        msg = yield ws.read_message()
        self.assertIsNone(msg)
        self.assertEqual(ws.close_code, 1001)
        self.assertEqual(ws.close_reason, "goodbye")

    @patch('shoestring.backends.memory.Backend.add_subscriber')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_basic_connect(self, mock_get, mock_subscribe):
        """Connect to the default room channel."""
        mock_get.return_value = {'XXX': False}
        token = jwt.encode({'room': '123', 'uuid': 'XXX'}, 'XXXX').decode('utf-8')
        ws = yield self.ws_connect('/socket?token={}'.format(token))
        mock_get.assert_called_with('123')
        self.assertTrue(mock_subscribe.called)
        args, kwargs = mock_subscribe.call_args
        self.assertEqual(args[0], '123')
        self.assertEqual(args[1].uuid, 'XXX')
        yield self.close(ws)

    @patch('shoestring.backends.memory.Backend.add_subscriber')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_explicit_room_channel(self, mock_get, mock_subscribe):
        """Connect to the room channel."""
        mock_get.return_value = {'XXX': False}
        token = jwt.encode({'room': '123', 'uuid': 'XXX'}, 'XXXX').decode('utf-8')
        ws = yield self.ws_connect('/socket?token={}&channel=123'.format(token))
        mock_get.assert_called_with('123')
        self.assertTrue(mock_subscribe.called)
        args, kwargs = mock_subscribe.call_args
        self.assertEqual(args[0], '123')
        self.assertEqual(args[1].uuid, 'XXX')
        yield self.close(ws)

    @patch('shoestring.backends.memory.Backend.add_subscriber')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_user_channel(self, mock_get, mock_subscribe):
        """Connect to a channel for the current user."""
        mock_get.return_value = {'XXX': False}
        token = jwt.encode({'room': '123', 'uuid': 'XXX'}, 'XXXX').decode('utf-8')
        ws = yield self.ws_connect('/socket?token={}&channel=XXX'.format(token))
        mock_get.assert_called_with('123')
        self.assertTrue(mock_subscribe.called)
        args, kwargs = mock_subscribe.call_args
        self.assertEqual(args[0], 'XXX')
        self.assertEqual(args[1].uuid, 'XXX')
        yield self.close(ws)

    @patch('shoestring.backends.memory.Backend.add_subscriber')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_other_user_channel(self, mock_get, mock_subscribe):
        """Connect to a channel for other user in the room."""
        mock_get.return_value = {'XXX': False, 'YYY': False}
        token = jwt.encode({'room': '123', 'uuid': 'XXX'}, 'XXXX').decode('utf-8')
        ws = yield self.ws_connect('/socket?token={}&channel=YYY'.format(token))
        mock_get.assert_called_with('123')
        self.assertTrue(mock_subscribe.called)
        args, kwargs = mock_subscribe.call_args
        self.assertEqual(args[0], 'YYY')
        self.assertEqual(args[1].uuid, 'XXX')
        yield self.close(ws)

    @patch('shoestring.backends.memory.Backend.remove_subscriber')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_unsubscribe(self, mock_get, mock_unsubscribe):
        """Subscription should be removed on close."""
        mock_get.return_value = {'XXX': False}
        token = jwt.encode({'room': '123', 'uuid': 'XXX'}, 'XXXX').decode('utf-8')
        ws = yield self.ws_connect('/socket?token={}'.format(token))
        mock_get.assert_called_with('123')
        self.assertFalse(mock_unsubscribe.called)
        yield self.close(ws)
        self.assertTrue(mock_unsubscribe.called)
        args, kwargs = mock_unsubscribe.call_args
        self.assertEqual(args[0], '123')
        self.assertEqual(args[1].uuid, 'XXX')

    @patch('shoestring.backends.memory.Backend.broadcast')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_broadcast(self, mock_get, mock_broadcast):
        """Messages from the socket should be broadcast by the backend."""
        mock_get.return_value = {'XXX': False}
        token = jwt.encode({'room': '123', 'uuid': 'XXX'}, 'XXXX').decode('utf-8')
        ws = yield self.ws_connect('/socket?token={}'.format(token))
        mock_get.assert_called_with('123')
        ws.write_message('hello')
        yield self.close(ws)
        mock_broadcast.assert_called_with('hello', channel='123', sender='XXX')    

    @patch('shoestring.backends.memory.Backend.add_subscriber')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_missing_token(self, mock_get, mock_subscribe):
        """Connections without a token are immediately closed."""
        ws = yield self.ws_connect('/socket')
        self.assertSocketError(ws, 4300, 'Missing token.')
        self.assertFalse(mock_get.called)
        self.assertFalse(mock_subscribe.called)

    @patch('shoestring.backends.memory.Backend.add_subscriber')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_invalid_token(self, mock_get, mock_subscribe):
        """Try to connect to with an invalid token."""
        token = jwt.encode({'room': '123', 'uuid': 'XXX'}, 'XYYX').decode('utf-8')
        ws = yield self.ws_connect('/socket?token={}'.format(token))
        self.assertSocketError(ws, 4000, 'Invalid token.')
        self.assertFalse(mock_get.called)
        self.assertFalse(mock_subscribe.called)

    @patch('shoestring.backends.memory.Backend.add_subscriber')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_invalid_room(self, mock_get, mock_subscribe):
        """Try to connect to room which doesn't exist."""
        mock_get.side_effect = KeyError('Unknown room.')
        token = jwt.encode({'room': '123', 'uuid': 'XXX'}, 'XXXX').decode('utf-8')
        ws = yield self.ws_connect('/socket?token={}'.format(token))
        self.assertSocketError(ws, 4300, 'Invalid channel.')
        self.assertTrue(mock_get.called)
        self.assertFalse(mock_subscribe.called)

    @patch('shoestring.backends.memory.Backend.add_subscriber')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_invalid_channel(self, mock_get, mock_subscribe):
        """Try to connect to room which doesn't exist."""
        mock_get.return_value = {'XXX': False}
        token = jwt.encode({'room': '123', 'uuid': 'XXX'}, 'XXXX').decode('utf-8')
        ws = yield self.ws_connect('/socket?token={}&channel=ABC'.format(token))
        self.assertSocketError(ws, 4300, 'Invalid channel.')
        self.assertTrue(mock_get.called)
        self.assertFalse(mock_subscribe.called)

    @patch('shoestring.backends.memory.Backend.add_subscriber')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_already_subscribed(self, mock_get, mock_subscribe):
        """Try to connect to channel which the user is already subscribed."""
        mock_get.return_value = {'XXX': True}
        mock_subscribe.side_effect = ValueError('Already subscribed.')
        token = jwt.encode({'room': '123', 'uuid': 'XXX'}, 'XXXX').decode('utf-8')
        ws = yield self.ws_connect('/socket?token={}'.format(token))
        self.assertSocketError(ws, 4300, 'Invalid channel.')
        self.assertTrue(mock_get.called)
        self.assertTrue(mock_subscribe.called)

    @patch('shoestring.backends.memory.Backend.add_subscriber')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_invalid_origin(self, mock_get, mock_subscribe):
        """Invalid origin."""
        mock_get.return_value = {'XXX': False}
        token = jwt.encode({'room': '123', 'uuid': 'XXX'}, 'XXXX').decode('utf-8')
        url = 'ws://localhost:{}/socket?token={}'.format(self.get_http_port(), token)
        headers = {'Origin': 'http://evil.com'}
        with self.assertRaises(HTTPError) as e:
            yield websocket_connect(HTTPRequest(url, headers=headers))
            self.assertEqual(e.exception.code, 403)
        self.assertFalse(mock_get.called)
        self.assertFalse(mock_subscribe.called)

    @patch('shoestring.backends.memory.Backend.add_subscriber')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_default_origina(self, mock_get, mock_subscribe):
        """Current location is an allowed origin."""
        mock_get.return_value = {'XXX': False}
        token = jwt.encode({'room': '123', 'uuid': 'XXX'}, 'XXXX').decode('utf-8')
        url = 'ws://localhost:{}/socket?token={}'.format(self.get_http_port(), token)
        headers = {'Origin': 'http://localhost:{}'.format(self.get_http_port())}
        ws = yield websocket_connect(HTTPRequest(url, headers=headers))
        mock_get.assert_called_with('123')
        self.assertTrue(mock_subscribe.called)
        args, kwargs = mock_subscribe.call_args
        self.assertEqual(args[0], '123')
        self.assertEqual(args[1].uuid, 'XXX')
        yield self.close(ws)

    @patch('shoestring.backends.memory.Backend.add_subscriber')
    @patch('shoestring.backends.memory.Backend.get_room')
    @gen_test
    def test_allowed_origina(self, mock_get, mock_subscribe):
        """Additional servers can be set as allowed hosts."""
        mock_get.return_value = {'XXX': False}
        token = jwt.encode({'room': '123', 'uuid': 'XXX'}, 'XXXX').decode('utf-8')
        url = 'ws://localhost:{}/socket?token={}'.format(self.get_http_port(), token)
        headers = {'Origin': 'http://example.com'}
        ws = yield websocket_connect(HTTPRequest(url, headers=headers))
        mock_get.assert_called_with('123')
        self.assertTrue(mock_subscribe.called)
        args, kwargs = mock_subscribe.call_args
        self.assertEqual(args[0], '123')
        self.assertEqual(args[1].uuid, 'XXX')
        yield self.close(ws)
