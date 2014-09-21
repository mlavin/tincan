import logging
import os
import time

from importlib import import_module

from tornado.ioloop import IOLoop
from tornado.web import Application

from .handlers import CreateRoomHandler, GetRoomHandler, SocketHandler, IndexHandler


class ShoestringApplication(Application):

    def __init__(self, **kwargs):
        backend_name = kwargs.pop('backend', 'shoestring.backends.memory')
        backend_module = import_module(backend_name)
        try:
            backend_class = getattr(backend_module, 'Backend')
        except AttributeError as e:
            msg = 'Module "{}" does not define a Backend class.'.format(backend_name)
            raise ImportError(msg) from e
        self.backend = backend_class()
        routes = [
            (r'/rooms$', CreateRoomHandler, {'backend': self.backend}),
            (r'/rooms/(?P<room>[0-9]+)$', GetRoomHandler, {'backend': self.backend}),
            (r'/socket$', SocketHandler, {'backend': self.backend}),
            (r'/$', IndexHandler),
        ]
        settings = {
            'template_path': os.path.join(os.path.dirname(__file__), os.pardir, 'templates'),
            'static_path': os.path.join(os.path.dirname(__file__), os.pardir, 'static'),
            'static_url_prefix': '/static/',
            'secret': os.environ.get('SHOESTRING_SECRET_KEY', str(os.urandom(75))),
        }
        settings.update(kwargs)
        super().__init__(routes, **settings)

    def shutdown(self, graceful=True):
        """Shutdown of the application server. Might be immediate or graceful."""
        self.backend.shutdown(graceful=graceful)
