import os
import random


class BaseBackend(object):
    """Base class for defining the backend API."""

    def _get_random_name(self, length=5):
        lower = 10 ** (length - 1)
        upper = 10 ** length - 1
        return '{}'.format(random.SystemRandom().randint(lower, upper))

    def create_room(self, owner):
        raise NotImplementedError('Define in a subclass.')

    def join_room(self, name, user):
        raise NotImplementedError('Define in a subclass.')

    def get_room(self, name):
        raise NotImplementedError('Define in a subclass.')

    def add_subscriber(self, channel, subscriber):
        raise NotImplementedError('Define in a subclass.')

    def remove_subscriber(self, channel, subscriber):
        raise NotImplementedError('Define in a subclass.')

    def get_subscribers(self, channel=None):
        raise NotImplementedError('Define in a subclass.')

    def broadcast(self, message, channel, sender):
        raise NotImplementedError('Define in a subclass.')

    def shutdown(self, graceful=True):
        for subscriber in self.get_subscribers():
            code = 4200 if graceful else 4100
            subscriber.close(code=code, reason='Server shutdown.')
