import os
import random


class BaseBackend(object):
    """Base class for defining the backend API."""

    def _get_random_name(self, length=5):
        lower = 10 ** (length - 1)
        upper = 10 ** length - 1
        return '{}'.format(random.SystemRandom().randint(lower, upper))

    def create_channel(self, owner):
        raise NotImplementedError('Define in a subclass.')

    def get_channel(self, name, user):
        raise NotImplementedError('Define in a subclass.')

    def add_subscriber(self, channel, subscriber):
        raise NotImplementedError('Define in a subclass.')

    def remove_subscriber(self, channel, subscriber):
        raise NotImplementedError('Define in a subclass.')

    def broadcast(self, message, channel, sender):
        raise NotImplementedError('Define in a subclass.')
