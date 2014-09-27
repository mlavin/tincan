import datetime
import json
import logging
import signal

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
        if not msg:
            return

        if msg.kind == 'message':
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
        elif msg.kind == 'disconnect':
            # Disconnected from the Redis server
            # Trigger a graceful shutdown
            logging.warn('Dropped Redis connection.')
            signal.alarm(1)


class Backend(BaseBackend):
    """Redis channel backend."""

    KEY_FORMAT = 'shoestring-room:{}'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscriber = RedisSubscriber(Client())
        self.publisher = Redis()

    def _room_key(self, name):
        return self.KEY_FORMAT.format(name)

    def create_room(self, owner):
        created = False
        while not created:
            room = self._get_random_name()
            key = self._room_key(room)
            if not self.publisher.exists(key):
                created = True
                self.publisher.hset(key, owner, '')
                # Set the room to expire in an hour
                self.publisher.expire(key, datetime.timedelta(hours=1))
        return room

    def join_room(self, name, user):
        key = self._room_key(name)
        if self.publisher.exists(key):
            self.publisher.hset(key, user, '')
            return name
        else:
            raise KeyError('Unknown room.')

    def get_room(self, name):
        key = self._room_key(name)
        result = self.publisher.hgetall(key)
        if not result:
            raise KeyError('Unknown room.')
        members = {}
        for key, value in result.items():
            members[key.decode('utf-8')] = bool(value)
        return members

    def add_subscriber(self, channel, subscriber):
        self.subscriber.subscribe(channel, subscriber)
        key = self._room_key(channel)
        if self.publisher.exists(key):
            self.publisher.hset(key, subscriber.uuid, 'subscribed')
            # Remove any expiry on the room
            self.publisher.persist(key)

    def remove_subscriber(self, channel, subscriber):
        self.subscriber.unsubscribe(channel, subscriber)
        key = self._room_key(channel)
        if self.publisher.exists(key):
            self.publisher.hset(key, subscriber.uuid, '')
            if not any(self.publisher.hvals(key)):
                # Set the room to expire in an hour
                self.publisher.expire(key, datetime.timedelta(hours=1))

    def get_subscribers(self, channel=None):
        if channel is not None:
            yield from self.subscriber.subscribers[channel].keys()
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
