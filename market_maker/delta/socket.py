from actioncable.connection import Connection
from actioncable.subscription import Subscription
import requests
from time import sleep


class DeltaWebSocket:

    def __init__(self, ws_endpoint, base_url, username, password):
        self.ws_endpoint = ws_endpoint
        self.username = username
        self.password = password
        self.base_url = base_url
        self.token = None
        # self.authenticate()

    def authenticate(self):
        response = requests.post(
            '%s/login' % self.base_url,
            json={'email': self.username, 'password': self.password}
        )
        token = str(response.json()['token'])
        self.token = token

    def connect(self):
        self.authenticate()
        self.connection = Connection(
            url=self.ws_endpoint + '/cable?token=' + self.token, origin='https://testnet.delta.exchange')
        connection_timeout = 5
        self.connection.connect()
        while not self.connection.connected and connection_timeout:
            sleep(1)
            connection_timeout -= 1

        if not connection_timeout:
            raise Exception(
                "Couldn't establish connetion with Delta websocket")

    def subscribeUserChannel(self, product_id, callback):
        subscription = Subscription(self.connection,
                                    identifier={
                                        'channel': 'UserChannel',
                                        'product_id': product_id}
                                    )
        subscription.on_receive(callback=callback)
        subscription.create()

    def isConnected(self):
        return self.connection.connected

    def reconnect(self):
        self.connection.disconnect()
        self.connect()

    def disconnect(self):
        self.connection.disconnect()
        print("Delta websocket disconnected")
    # if not self.token:
    #   raise Exception('Need to authenticate first')
