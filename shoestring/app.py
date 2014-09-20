import os

from importlib import import_module

from tornado.web import Application

from .handlers import CreateRoomHandler, GetRoomHandler, SocketHandler, IndexHandler


class ShoestringApplication(Application):

    def __init__(self, **kwargs):
        routes = [
            (r'/rooms$', CreateRoomHandler),
            (r'/rooms/(?P<room>[0-9]+)$', GetRoomHandler),
            (r'/socket$', SocketHandler),
            (r'/$', IndexHandler),
        ]
        backend_name = kwargs.pop('backend', 'shoestring.backends.memory')
        backend_module = import_module(backend_name)
        try:
            backend_class = getattr(backend_module, 'Backend')
        except AttributeError as e:
            msg = 'Module "{}" does not define a Backend class.'.format(backend_name)
            raise ImportError(msg) from e
        settings = {
            'template_path': os.path.join(os.path.dirname(__file__), os.pardir, 'templates'),
            'static_path': os.path.join(os.path.dirname(__file__), os.pardir, 'static'),
            'static_url_prefix': '/static/',
            'secret': 'XXXXXXXXX',
        }
        settings.update(kwargs)
        super().__init__(routes, **settings)
        self.backend = backend_class()

    # Pass through methods down to the backend
    def create_channel(self, owner):
        return self.backend.create_channel(owner)

    def get_channel(self, name, user):
        return self.backend.get_channel(name, user)

    def add_subscriber(self, channel, subscriber):
        self.backend.add_subscriber(channel, subscriber)

    def remove_subscriber(self, channel, subscriber):
        self.backend.remove_subscriber(channel, subscriber)

    def broadcast(self, message, channel, sender):
        self.backend.broadcast(message, channel, sender)
