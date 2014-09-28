import unittest

from unittest.mock import patch

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
