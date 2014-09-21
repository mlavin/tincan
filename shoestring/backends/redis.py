import json

from tornado.websocket import WebSocketClosedError

from .base import BaseBackend

try:
    from redis import Redis
    from tornadoredis import Client
    from tornadoredis.pubsub import BaseSubscriber
except ImportError as e:
    msg = 'The redis backend requires installing redis-py and tornado-redis.'
    raise ImportError(msg) from e


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


class Backend(BaseBackend):
    """Redis channel backend."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscriber = RedisSubscriber(Client())
        self.publisher = Redis()

    def create_channel(self, owner):
        room = self._get_random_name()
        return room

    def get_channel(self, name, user):
        return name

    def remove_channel(self, name):
        pass

    def add_subscriber(self, channel, subscriber):
        self.subscriber.subscribe(channel, subscriber)

    def remove_subscriber(self, channel, subscriber):
        self.subscriber.unsubscribe(channel, subscriber)
        if len(self.get_subscribers(channel)) == 0:
            self.remove_channel(channel)

    def get_subscribers(self, channel=None):
        if channel is not None:
            return list(self.subscriber.subscribers[channel].keys())
        else:
            for subscribers in self.subscriber.subscribers.values():
                for s in subscribers:
                    yield s

    def broadcast(self, message, channel, sender):
        message = json.dumps({
            'sender': sender,
            'message': message
        })
        self.publisher.publish(channel, message)

    def shutdown(self, graceful=True):
        super().shutdown(graceful=graceful)
        self.subscriber.close()
        self.publisher.connection_pool.disconnect()
