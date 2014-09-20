import json
import os

from redis import Redis
from tornado.web import Application
from tornado.websocket import WebSocketClosedError
from tornadoredis import Client
from tornadoredis.pubsub import BaseSubscriber

from .handlers import CreateRoomHandler, GetRoomHandler, SocketHandler, IndexHandler


class RedisSubscriber(BaseSubscriber):

    def on_message(self, msg):
        """Handle new message on the Redis channel."""
        if msg and msg.kind == 'message':
            try:
                message = json.loads(msg.body)
                sender = message['sender']
                message = message['message']
            except (ValueError, KeyError):
                logging.warning('Invalid channel mesage: {}'.format(msg.body))
            else:
                subscribers = list(self.subscribers[msg.channel].keys())
                for subscriber in subscribers:
                    if sender != subscriber.uuid:
                        try:
                            subscriber.write_message(message)
                        except tornado.websocket.WebSocketClosedError:
                            # Remove dead peer
                            self.unsubscribe(msg.channel, subscriber)
        super().on_message(msg)


class ShoestringApplication(Application):

    def __init__(self, **kwargs):
        routes = [
            (r'/rooms$', CreateRoomHandler),
            (r'/rooms/(?P<room>[0-9]+)$', GetRoomHandler),
            (r'/socket$', SocketHandler),
            (r'/$', IndexHandler),
        ]
        settings = {
            'template_path': os.path.join(os.path.dirname(__file__), os.pardir, 'templates'),
            'static_path': os.path.join(os.path.dirname(__file__), os.pardir, 'static'),
            'static_url_prefix': '/static/',
            'secret': 'XXXXXXXXX',
        }
        settings.update(kwargs)
        super().__init__(routes, **settings)
        self.subscriber = RedisSubscriber(Client())
        self.publisher = Redis()

    def add_subscriber(self, channel, subscriber):
        self.subscriber.subscribe(channel, subscriber)

    def remove_subscriber(self, channel, subscriber):
        self.subscriber.unsubscribe(channel, subscriber)

    def broadcast(self, message, channel, sender):
        message = json.dumps({
            'sender': sender,
            'message': message
        })
        self.publisher.publish(channel, message)
