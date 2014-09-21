from collections import defaultdict

from tornado.websocket import WebSocketClosedError

from .base import BaseBackend


class Backend(BaseBackend):
    """In memory channel backend."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rooms = []
        self._subscriptions = defaultdict(list)

    def create_channel(self, owner):
        room = self._get_random_name()
        while room not in self._rooms:
            room = self._get_random_name()
        self._rooms.append(room)
        return room

    def get_channel(self, name, user):
        if name in self._rooms:
            return name
        else:
            raise KeyError('Unknown room.')

    def remove_channel(self, name):
        try:
            self._rooms.remove(name)
        except ValueError:
            pass

    def add_subscriber(self, channel, subscriber):
        self._subscriptions[channel].append(subscriber)

    def remove_subscriber(self, channel, subscriber):
        self._subscriptions[channel].append(subscriber)
        if len(self.get_subscribers(channel)) == 0:
            self.remove_channel(channel)

    def get_subscribers(self, channel=None):
        if channel is not None:
            return self._subscriptions[channel]
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
