import os
import signal
import time
import unittest

from unittest.mock import patch, Mock

from tornado import gen
from tornado.options import options
from tornado.testing import AsyncTestCase, LogTrapTestCase, ExpectLog, gen_test

from ..__main__ import main, shutdown
from ..app import ShoestringApplication
from ..backends.base import BaseBackend
from ..backends.memory import Backend as MemoryBackend


class Backend(BaseBackend):
    """Test backend."""


class ApplicationTestCase(unittest.TestCase):
    """Application configuration and shutdown."""

    def get_app(self, **kwargs):
        """Get application with given settings."""
        return ShoestringApplication(**kwargs)

    def test_defaults(self):
        """Start application with default settings."""
        app = self.get_app()
        self.assertNotIn('debug', app.settings)
        self.assertNotIn('allowed_hosts', app.settings)
        self.assertTrue(isinstance(app.backend, MemoryBackend))

    def test_explicit_backend(self):
        """Explicit default backend."""
        app = self.get_app(backend='shoestring.backends.memory')
        self.assertTrue(isinstance(app.backend, MemoryBackend))

    def test_non_default_backend(self):
        """Use a non default backend."""
        app = self.get_app(backend=__name__)
        self.assertTrue(isinstance(app.backend, Backend))

    def test_invalid_backend_module(self):
        """Invalid module paths with generated ImportErrors on startup."""
        with self.assertRaises(ImportError):
            self.get_app(backend='shoestring.backends.this.does.not.exist')

    def test_no_backend_class(self):
        """If module does not define a backend class it raised as ImportError."""
        with self.assertRaises(ImportError):
            self.get_app(backend='shoestring.backends.base')

    def test_shutdown(self):
        """Shutting down the application should shutdown the backend."""
        app = self.get_app()
        with patch.object(app.backend, 'shutdown') as mock_shutdown:
            app.shutdown()
            mock_shutdown.assert_called_with(graceful=True)
            app.shutdown(False)
            mock_shutdown.assert_called_with(graceful=False)


class MainTestCase(AsyncTestCase, LogTrapTestCase):
    """Test application startup and graceful shutdown."""

    def get_app_defaults(self):
        """Default options for building the application instance."""
        return  {
            'debug': False,
            'backend': 'shoestring.backends.memory',
            'allowed_hosts': [],
        }

    @patch('shoestring.__main__.ShoestringApplication')
    @gen_test
    def test_main(self, mock_app):
        """Start up the server with the default options."""
        with ExpectLog('', 'Starting server on localhost:8080'):
            main(self.io_loop)
        mock_app.assert_called_with(**self.get_app_defaults())

    @patch('shoestring.__main__.ShoestringApplication')
    @gen_test
    def test_debug(self, mock_app):
        """Debug option should be passed from the command line to the application."""
        with patch.object(options.mockable(), 'debug', True):
            with patch('shoestring.__main__.parse_command_line') as mock_parse:
                main(self.io_loop)
                mock_parse.assert_called_with()
            expected = self.get_app_defaults()
            expected['debug'] = True
            mock_app.assert_called_with(**expected)

    @patch('shoestring.__main__.ShoestringApplication')
    @gen_test
    def test_backed(self, mock_app):
        """Backend option should be passed from the command line to the application."""
        with patch.object(options.mockable(), 'backend', __name__):
            with patch('shoestring.__main__.parse_command_line') as mock_parse:
                main(self.io_loop)
                mock_parse.assert_called_with()
            expected = self.get_app_defaults()
            expected['backend'] = __name__
            mock_app.assert_called_with(**expected)

    @patch('shoestring.__main__.ShoestringApplication')
    @gen_test
    def test_allowed_hosts(self, mock_app):
        """Allowed host option should be passed from the command line to the application."""
        with patch.object(options.mockable(), 'allowed_hosts', ['example.com', ]):
            with patch('shoestring.__main__.parse_command_line') as mock_parse:
                main(self.io_loop)
                mock_parse.assert_called_with()
            expected = self.get_app_defaults()
            expected['allowed_hosts'] = ['example.com', ]
            mock_app.assert_called_with(**expected)

    @gen_test
    def test_graceful_shutdown(self):
        """Trigger graceful shutdown of the server and application."""
        server = Mock(_stopping=False)
        application = Mock()
        shutdown(server, application, graceful=True, ioloop=self.io_loop)
        server.stop.assert_called_with()
        application.shutdown.assert_called_with(graceful=True)

    @gen_test
    def test_double_shutdown(self):
        """Mimic a double TERM or INT signal."""
        server = Mock(_stopping=False)
        application = Mock()
        shutdown(server, application, graceful=True, ioloop=self.io_loop)
        shutdown(server, application, graceful=True, ioloop=self.io_loop)
        server.stop.assert_called_with()
        application.shutdown.assert_called_with(graceful=True)

    @gen_test
    def test_fast_shutdown(self):
        """Trigger immediate shutdown of the server and application."""
        server = Mock(_stopping=False)
        application = Mock()
        shutdown(server, application, graceful=False, ioloop=self.io_loop)
        server.stop.assert_called_with()
        application.shutdown.assert_called_with(graceful=False)
