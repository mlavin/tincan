from collections import defaultdict

from tornado.websocket import WebSocketClosedError

from .base import BaseBackend


class Backend(BaseBackend):
    """In memory channel backend."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rooms = defaultdict(dict)
        self._subscriptions = defaultdict(list)

    def create_room(self, user):
        room = self._get_random_name()
        while room in self._rooms:
            room = self._get_random_name()
        self._rooms[room][user] = False
        return room

    def join_room(self, name, user):
        if name in self._rooms:
            self._rooms[name][user] = False
            return name
        else:
            raise KeyError('Unknown room.')

    def get_room(self, name):
        if name in self._rooms:
            return self._rooms[name]
        else:
            raise KeyError('Unknown room.')
        
    def add_subscriber(self, channel, subscriber):
        if self._rooms.get(channel, {}).get(subscriber.uuid, False):
            raise ValueError('Already subscribed.')
        else:
            self._rooms.get(channel, {})[subscriber.uuid] = True
        self._subscriptions[channel].append(subscriber)


    def remove_subscriber(self, channel, subscriber):
        try:
            self._subscriptions[channel].remove(subscriber)
        except ValueError:
            pass
        else:
            self._rooms.get(channel, {})[subscriber.uuid] = False

    def get_subscribers(self, channel=None):
        if channel is not None:
            yield from self._subscriptions[channel]
        else:
            for participants in self._subscriptions.values():
                for p in participants:
                    yield p

    def broadcast(self, message, channel, sender):
        peers = self.get_subscribers(channel)
        for peer in peers:
            if peer != sender:
                try:
                    peer.write_message(message)
                except WebSocketClosedError:
                    # Remove dead peer
                    self.remove_subscriber(channel, peer)
