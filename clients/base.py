from abc import ABC, abstractmethod
from decimal import Decimal


class BaseClient(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def connect_rc(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def reconnect(self):
        pass

    @abstractmethod
    def isConnected(self):
        pass

    @abstractmethod
    def subscribeChannel(self, channel_name, symbol, callback):
        pass

    @abstractmethod
    def unsubscribeChannel(self, channel_name, callback):
        pass

    @abstractmethod
    def market_depth(self, symbol):
        pass

    @abstractmethod
    def funds(self, symbol):
        pass

    @abstractmethod
    def position(self, symbol):
        pass
