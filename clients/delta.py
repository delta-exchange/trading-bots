from delta_rest_client import DeltaRestClient, create_order_format, round_by_tick_size, cancel_order_format, OrderType
import logging
from decimal import Decimal
import datetime
import time
import threading
import json
import base64
import hmac
import hashlib
from itertools import islice
from time import sleep
import requests
import websocket
from threading import Timer
from enum import Enum

from utils.utility import get_position, round_price_by_tick_size
from clients.base import BaseClient
import custom_exceptions
from utils.decorators import handle_requests_exceptions


def get_time_stamp():
    d = datetime.datetime.utcnow()
    epoch = datetime.datetime(1970, 1, 1)
    return str(int((d - epoch).total_seconds()))


def generate_signature(secret, message):
    message = bytes(message, 'utf-8')
    secret = bytes(secret, 'utf-8')
    hash = hmac.new(secret, message, hashlib.sha256)
    return hash.hexdigest()

# TODO:
# Exception handling in Delta


class OrderState(Enum):
    OPEN = 'open'
    CLOSE = 'closed'
    CANCELLED = 'cancelled'
    PENDING = 'pending'


class Delta(BaseClient):
    def __init__(self, account, channels, product_id, callback=None):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.timer = Timer(40.0, self.ping)
        self.api_key = account['api_key']
        self.api_secret = account['api_secret']
        if account['chain'] == 'testnet':
            self.delta_base_url = "https://testnet-api.delta.exchange"
            self.ws_endpoint = "wss://testnet-api.delta.exchange:2096"
        elif account['chain'] == 'mainnet':
            self.delta_base_url = "https://api.delta.exchange"
            self.ws_endpoint = "wss://api.delta.exchange:2096"
        elif account['chain'] == 'devnet':
            self.delta_base_url = "https://devnet-api.delta.exchange"
            self.ws_endpoint = "wss://devnet-api.delta.exchange:2096"
        else:
            raise Exception('InvalidDeltaChain')

        self.channels = channels
        self.product_id = product_id
        self.callback = callback
        self.callbacks = {}
        self.data = {
            'positions': {},
            'mark_price': {},
            'l2_orderbook': [],
            'spot_price': {}
        }
        self.last_seen = {
            'positions': {},
            'mark_price': {},
            'spot_price': {}
        }
        self.exited = True

        self.delta_client = self.connect_rc()

        self.product = self.get_product(product_id)
        self.contract_size = round_price_by_tick_size(
            self.product['contract_value'], self.product['contract_value'])
        self.tick_size = round_price_by_tick_size(
            self.product['tick_size'], self.product['tick_size'])
        self.isInverse = self.product['product_type'] == 'inverse_future'
        self.isQuanto = self.product['is_quanto']
        self.symbol = self.product['symbol']
        if self.channels:
            self.connect()

    def __auth(self):
        if not self.ws:
            raise Exception('Need to establish a socket connection first')
        method = 'GET'
        timestamp = get_time_stamp()
        path = '/live'
        signature_data = method + timestamp + path
        signature = generate_signature(self.api_secret, signature_data)
        self.ws.send(json.dumps({
            "type": "auth",
            "payload": {
                "api-key": self.api_key,
                "signature": signature,
                "timestamp": timestamp
            }
        }))

    def __on_error(self, error):
        self.logger.info(error)

    def __on_open(self):
        self.logger.info("Delta Websocket Opened.")

    def __on_close(self):
        self.logger.info('Delta Websocket Closed.')
        if not self.exited:
            self.reconnect()

    def __on_message(self, message):
        self.__restart_ping_timer()
        try:
            message = json.loads(message)
            if 'type' in message:
                event = message['type']
                if event == 'l2_orderbook':
                    self.orderbook_updates(message)
                elif event in ['fill', 'self_trade', 'pnl', 'liquidation', 'adl', 'stop_trigger', 'stop_cancel']:
                    if 'trading_notifications' in self.callbacks:
                        self.callbacks['trading_notifications'](message)
                elif event == 'positions':
                    self.position_updates(message)
                elif event == 'mark_price':
                    self.mark_price_update(message)
                elif event == 'spot_price':
                    self.spot_price_update(message)
                else:
                    pass
            elif 'message' in message:
                self.logger.info(message['message'])
        except Exception:
            pass

    def __restart_ping_timer(self):
        if self.timer.isAlive():
            self.timer.cancel()
        self.timer = Timer(40.0, self.ping)
        self.timer.start()

    def connect_rc(self):
        delta_client = DeltaRestClient(
            base_url=self.delta_base_url,
            api_key=self.api_key,
            api_secret=self.api_secret
        )
        return delta_client

    def connect(self):
        self.ws = websocket.WebSocketApp(self.ws_endpoint,
                                         on_message=self.__on_message,
                                         on_close=self.__on_close,
                                         on_open=self.__on_open,
                                         on_error=self.__on_error)

        self.wst = threading.Thread(name='Delta Websocket',
                                    target=lambda: self.ws.run_forever(ping_interval=30, ping_timeout=10))
        self.wst.daemon = True
        self.wst.start()

        conn_timeout = 5
        while not self.ws.sock or not self.ws.sock.connected and conn_timeout:
            sleep(1)
            conn_timeout -= 1
        if not conn_timeout:
            self.logger.debug(
                "Couldn't establish connetion with Delta websocket")
        else:
            self.exited = False
            if self.api_key and self.api_secret:
                self.__auth()
                sleep(2)
            for channel_name in self.channels:
                self.subscribeChannel(channel_name, self.symbol, self.callback)

    def is_thread_alive(self):
        return (self.wst and self.wst.is_alive())

    def disconnect(self):
        self.exited = True
        self.timer.cancel()
        self.ws.close()
        self.callbacks.clear()
        # self.wst.join()
        self.logger.info("Delta Websocket Disconnected.")

    def reconnect(self):
        self.disconnect()
        self.connect()

    def isConnected(self):
        return self.ws.sock and self.ws.sock.connected

    def ping(self):
        self.ws.send(json.dumps({
            "type": "ping"
        }))

    def orderbook_updates(self, result):
        orderbooks = list(filter(
            lambda x: x['symbol'] == result['symbol'], self.data['l2_orderbook']
        ))

        if orderbooks:
            orderbook = orderbooks[0]
            orderbook['last_seen'] = time.time()
            orderbook['bids'] = result['buy']
            orderbook['asks'] = result['sell']
        else:
            orderbook = {
                'last_seen': time.time(),
                'symbol': result['symbol'],
                'asks': result['buy'],
                'bids': result['sell']
            }
            self.data['l2_orderbook'].append(orderbook)

    def position_updates(self, result):
        product_id = result['product_id']
        position = get_position(
            entry_price=round_price_by_tick_size(
                result['entry_price'], self.tick_size),
            size=int(result['size'])
        )
        position['margin'] = Decimal(result['margin'])
        position['liquidation_price'] = Decimal(result['liquidation_price'])
        self.data['positions'][product_id] = position
        self.last_seen['positions'][product_id] = time.time()

    def mark_price_update(self, result):
        product_id = result['product_id']
        self.data['mark_price'][product_id] = Decimal(result['price'])
        self.last_seen['mark_price'][product_id] = time.time()

    def spot_price_update(self, result):
        spot_symbol = result['symbol']
        self.data['spot_price'][spot_symbol] = Decimal(result['price'])
        self.last_seen['spot_price'][spot_symbol] = time.time()

    """     *******     SOCKET METHODS   *******     """

    def subscribeChannel(self, channel_name, symbol, callback=None):
        self.ws.send(json.dumps({
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": channel_name,
                        "symbols": [symbol]
                    }
                ]
            }
        }))
        self.callbacks[channel_name] = callback

    def unsubscribeChannel(self, channel_name):
        self.ws.send(json.dumps({
            "type": "unsubscribe",
            "channels": [
                    {
                        "name": channel_name,
                        "symbols": [self.symbol]
                    }
            ]
        }
        ))
        if channel_name in self.callbacks:
            del self.callbacks[channel_name]

    def market_depth(self, symbol):
        if self.isConnected() and 'l2_orderbook' in self.data:
            orderbooks = list(filter(
                lambda x: x['symbol'] == symbol, self.data['l2_orderbook']
            ))
            if orderbooks and time.time() - orderbooks[0]['last_seen'] < 2:
                asks = list(map(
                    lambda x: {
                        'price': round_price_by_tick_size(x['limit_price'], self.tick_size),
                        'size': int(x['size'])
                    }, orderbooks[0]['asks']
                ))
                bids = list(map(
                    lambda x: {
                        'price': round_price_by_tick_size(x['limit_price'], self.tick_size),
                        'size': int(x['size'])
                    }, orderbooks[0]['bids']
                ))
                bids = list(filter(
                    lambda x: Decimal(x['price']) > self.tick_size,
                    bids
                ))
                asks.sort(key=lambda x: x['price'])
                bids.sort(key=lambda x: x['price'], reverse=True)
                return {'asks': asks, 'bids': bids}
        return self.getorderbook(self.product_id)

    def mark_price(self, product_id):
        if self.isConnected() and 'mark_price' in self.data:
            if product_id in self.data['mark_price'] and time.time() - self.last_seen['mark_price'][product_id] < 15:
                return self.data['mark_price'][product_id]
        return self.get_mark_price(product_id)

    def spot_price(self, spot_symbol, product_id):
        if self.isConnected() and 'spot_price' in self.data:
            if spot_symbol in self.data['spot_price'] and time.time() - self.last_seen['spot_price'][spot_symbol] < 15:
                return self.data['spot_price'][spot_symbol]
        return self.get_spot_price(product_id)

    def position(self, product_id):
        # if self.isConnected():
        #     if product_id in self.data['positions'] and time.time() - self.last_seen['positions'][product_id] < 15:
        #         return self.data['positions'][product_id]
        # Get position from rest and set locally
        position = self.get_position_over_rest(product_id)
        self.data['positions'][product_id] = position
        self.last_seen['positions'][product_id] = time.time()
        return position

    """     *******     HTTP METHODS   *******     """

    @handle_requests_exceptions(client='Delta')
    def getorderbook(self, product_id):
        orderbook = self.delta_client.get_L2_orders(product_id, auth=True)
        asks = list(map(
            lambda x: {
                'price': round_price_by_tick_size(x['price'], self.tick_size),
                'size': int(x['size'])
            }, orderbook['sell_book']
        ))
        bids = list(map(
            lambda x: {
                'price': round_price_by_tick_size(x['price'], self.tick_size),
                'size': int(x['size'])
            }, orderbook['buy_book']
        ))
        asks.sort(key=lambda x: x['price'])
        bids.sort(key=lambda x: x['price'], reverse=True)
        return {'asks': asks, 'bids': bids}

    @handle_requests_exceptions(client='Delta')
    def get_mark_price(self, product_id):
        mark_price = self.delta_client.get_mark_price(product_id, auth=True)
        return Decimal(mark_price)

    @handle_requests_exceptions(client='Delta')
    def get_spot_price(self, product_id):
        orderbook = self.delta_client.get_L2_orders(product_id, auth=True)
        spot_price = orderbook['spot_price']
        return Decimal(spot_price)

    @handle_requests_exceptions(client='Delta')
    def get_position_over_rest(self, product_id):
        positions = self.delta_client.get_position(product_id)
        if positions and int(positions['size']) != 0:
            position = get_position(
                entry_price=round_price_by_tick_size(
                    positions['entry_price'], self.tick_size),
                size=int(positions['size'])
            )
            position['margin'] = Decimal(positions['margin'])
            position['liquidation_price'] = Decimal(
                positions['liquidation_price'])
            return position
        else:
            # RETURN EMPTY POSITION ONLY IF NO OPEN POSITIONS IS FOUND
            position = get_position()
            position['margin'] = 0
            position['liquidation_price'] = None
            self.logger.info(position)
            return position

    @handle_requests_exceptions(client='Delta')
    def addPositionMargin(self, product_id, delta_margin):
        return self.delta_client.change_position_margin(product_id, delta_margin)

    @handle_requests_exceptions(client='Delta')
    def funds(self):
        response = self.delta_client.get_wallet(
            self.product['settling_asset']['id'])
        return Decimal(response['balance']) - Decimal(response['position_margin'])

    @handle_requests_exceptions(client='Delta')
    def available_funds(self):
        response = self.delta_client.get_wallet(
            self.product['settling_asset']['id'])
        return Decimal(response['balance']) - Decimal(response['position_margin']) - Decimal(response['order_margin']) - Decimal(response['commission'])

    @handle_requests_exceptions(client='Delta')
    def get_product(self, product_id):
        response = self.delta_client.request("GET", "products", auth=True)
        response = response.json()
        products = list(
            filter(lambda x: x['id'] == product_id, response))
        return products[0] if len(products) > 0 else None

    @handle_requests_exceptions(client='Delta')
    def get_open_orders(self, product_id, state=OrderState.OPEN, page_num=1, page_size=500):
        query = {
            'product_id': product_id,
            'state': state.value,
            'page_num': page_num,
            'page_size': page_size
        }
        if state.value == 'pending':
            query['stop_order_type'] = 'stop_loss_order'
        response = self.delta_client.get_orders(query)
        return response

    @handle_requests_exceptions(client='Delta')
    def get_ticker(self, product_id):
        response = self.delta_client.get_ticker(product_id)
        return response

    @handle_requests_exceptions(client='Delta')
    def set_leverage(self, product_id, leverage):
        response = self.delta_client.set_leverage(
            product_id=product_id, leverage=leverage)
        return response

    def market_order(self, size, product_id):
        side = 'buy' if size > 0 else 'sell'
        if size != 0:
            order = {
                'size': abs(size),
                'side': side,
                'order_type': 'market_order',
                'product_id': product_id
            }
            self.place_order(order)

    @handle_requests_exceptions(client='Delta')
    def place_order(self, order):
        response = self.delta_client.create_order(order)
        if order['order_type'] == 'market_order' and response['unfilled_size'] != 0:
            self.logger.info('Delta exception: %s' % str(response))
            raise custom_exceptions.PlaceOrderError('Delta')
        else:
            return response

    @handle_requests_exceptions(client='Delta')
    def create_stop_order(self, product_id, size, stop_price):
        side = 'buy' if size > 0 else 'sell'
        response = self.delta_client.place_stop_order(
            product_id=product_id, size=abs(int(size)), side=side, stop_price=str(stop_price), order_type=OrderType.MARKET)
        return response

    @handle_requests_exceptions(client='Delta')
    def edit_order(self, product_id, order_id, size, stop_price):
        order = {
            'id': order_id,
            'product_id': product_id,
            'size': size,
            'stop_price': str(stop_price)
        }
        response = self.delta_client.request("PUT", "orders", order)
        return response

    @handle_requests_exceptions(client='Delta')
    def batch_create(self, product_id, orders):
        create_batches = self.slice_orders(orders)
        for create_order in create_batches:
            self.delta_client.batch_create(
                product_id, list(create_order))
        self.logger.info('Created orders: %s, batch size: %s' %
                         (len(orders), len(create_batches)))

    @handle_requests_exceptions(client='Delta')
    def batch_cancel(self, product_id, orders):
        delete_batches = self.slice_orders(orders)
        for delete_order in delete_batches:
            self.delta_client.batch_cancel(self.product_id,
                                           list(map(
                                                cancel_order_format, list(
                                                    delete_order)
                                                ))
                                           )
        self.logger.info('Deleted orders: %s, batch size: %s' %
                         (len(orders), len(delete_batches)))

    @handle_requests_exceptions(client='Delta')
    def batch_edit(self, product_id, orders):
        edit_batches = self.slice_orders(orders, size=20)
        for edit_order in edit_batches:
            self.delta_client.batch_edit(product_id, list(edit_order))
        self.logger.info('Edited orders: %s' % (len(orders)))

    def slice_orders(self, orders, size=5):
        orders = iter(orders)
        return list(iter(lambda: tuple(islice(orders, size)), ()))
