import json

from unittest.mock import patch

from tornado.testing import AsyncHTTPTestCase, LogTrapTestCase

from shoestring.app import ShoestringApplication


class BaseAppTestCase(AsyncHTTPTestCase, LogTrapTestCase):
    """Base class for testing ShoestringApplication and handlers."""

    def get_app(self):
        return ShoestringApplication()


class RoomHandlerTestCase(BaseAppTestCase):
    """URL for creating and fetching rooms."""

    @patch('shoestring.backends.memory.Backend.create_room')
    def test_create_room(self, mock_create):
        """Create a new room."""
        mock_create.return_value = '1234'
        response = self.fetch('/rooms', method='POST', body='')
        self.assertTrue(mock_create.called)
        self.assertEqual(response.code, 200)
        result = json.loads(response.body.decode('utf-8'))
        self.assertEqual(result['room'], '1234')

    @patch('shoestring.backends.memory.Backend.join_room')
    def test_existing_room(self, mock_join):
        """Join an existing room."""
        mock_join.return_value = '1234'
        response = self.fetch('/rooms/1234', method='GET')
        self.assertTrue(mock_join.called)
        self.assertEqual(response.code, 200)
        result = json.loads(response.body.decode('utf-8'))
        self.assertEqual(result['room'], '1234')

    @patch('shoestring.backends.memory.Backend.join_room')
    def test_missing_room(self, mock_join):
        """Try to join a non-existant room."""
        mock_join.side_effect = KeyError('Unknown room.')
        response = self.fetch('/rooms/1234', method='GET')
        self.assertTrue(mock_join.called)
        self.assertEqual(response.code, 404)
