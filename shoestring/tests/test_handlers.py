import json

from contextlib import contextmanager
from unittest.mock import patch

import jwt

from tornado.testing import AsyncHTTPTestCase, LogTrapTestCase

from shoestring.app import ShoestringApplication


class BaseAppTestCase(AsyncHTTPTestCase, LogTrapTestCase):
    """Base class for testing ShoestringApplication and handlers."""

    def get_app(self):
        return ShoestringApplication(secret='XXXX')

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
