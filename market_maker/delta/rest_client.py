import requests
import time
import datetime
from time import sleep
from decimal import *


class DeltaRestClient:

    def __init__(self, base_url,
                 username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.token = None
        self.authenticate()

    def authenticate(self):
        response = requests.post(
            '%s/login' % self.base_url,
            json={'email': self.username, 'password': self.password})
        token = str(response.json()['token'])
        self.token = token

    def get_username(self):
        return self.username

    def get_product(self, product_id, retry_count=3):
        while retry_count > 0:
            response = requests.get(
                "%s/products" % self.base_url)
            retry_count -= 1
            if response.status_code == 200:
                response = response.json()
                products = list(
                    filter(lambda x: x['id'] == product_id, response))
                return products[0] if len(products) > 0 else None
            elif response.status_code == 401:
                self.authenticate()
            elif int(response.status_code / 100) == 4:
                sleep(2)

        raise Exception('Error.%d Try again later' % response.status_code)

    def batch_create(self, orders, retry_count=3):
        if not self.token:
            raise Exception('Need to authenticate first')

        while retry_count > 0:
            response = requests.post(
                "%s/orders/batch" % self.base_url,
                json={'orders': orders},
                headers={'Authorization': 'Bearer %s' % self.token})
            retry_count -= 1
            if response.status_code == 200:
                return response
            elif response.status_code == 401:
                self.authenticate()
            elif int(response.status_code / 100) == 4:
                sleep(2)

        raise Exception('Error.%d Try again later' % response.status_code)

    def create_order(self, order, retry_count=3):
        if not self.token:
            raise Exception('Need to authenticate first')

        while retry_count > 0:
            response = requests.post(
                "%s/orders" % self.base_url,
                json=order,
                headers={'Authorization': 'Bearer %s' % self.token})
            retry_count -= 1
            if response.status_code == 200:
                return response
            elif response.status_code == 401:
                self.authenticate()
            elif int(response.status_code / 100) == 4:
                sleep(2)

        raise Exception('Error.%d Try again later' % response.status_code)

    def batch_cancel(self, orders, retry_count=3):
        if not self.token:
            raise Exception('Need to authenticate first')

        while retry_count > 0:
            response = requests.delete(
                "%s/orders/batch" % self.base_url,
                json={'orders': orders},
                headers={'Authorization': 'Bearer %s' % self.token})
            retry_count -= 1
            if response.status_code == 200:
                return response
            elif response.status_code == 401:
                self.authenticate()
            elif int(response.status_code / 100) == 4:
                sleep(2)

        raise Exception('Error.%d Try again later' % response.status_code)

    def get_orders(self, query, retry_count=3):
        if not self.token:
            raise Exception('Need to authenticate first')

        while retry_count > 0:
            response = requests.get(
                "%s/orders" % self.base_url,
                params=query,
                headers={'Authorization': 'Bearer %s' % self.token})
            retry_count -= 1
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                self.authenticate()
            elif int(response.status_code / 100) == 4:
                sleep(2)

        raise Exception('Error.%d Try again later' % response.status_code)

    def get_L2_orders(self, product_id, retry_count=3):

        while retry_count > 0:
            response = requests.get(
                "%s/orderbook/%s/l2" % (self.base_url, product_id))
            retry_count -= 1
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                self.authenticate()
            elif int(response.status_code / 100) == 4:
                sleep(2)

        raise Exception('Error.%d Try again later' % response.status_code)

    def get_ticker(self, product_id):
        l2_orderbook = self.get_L2_orders(product_id)
        best_sell_price = Decimal(l2_orderbook['sell_book'][0]['price']) if len(
            l2_orderbook['sell_book']) > 0 else Decimal('inf')
        best_buy_price = Decimal(l2_orderbook['buy_book'][0]['price']) if len(
            l2_orderbook['buy_book']) > 0 else 0
        return (best_buy_price, best_sell_price)

    def get_wallet(self, retry_count=3):
        if not self.token:
            raise Exception('Need to authenticate first')

        while retry_count > 0:
            response = requests.get(
                "%s/wallet/balance" % self.base_url,
                headers={'Authorization': 'Bearer %s' % self.token})
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                self.authenticate()
            elif int(response.status_code / 100) == 4:
                sleep(2)

        raise Exception('Error.%d Try again later' % response.status_code)

    def get_availableMargin(self, retry_count=3):
        if not self.token:
            raise Exception('Need to authenticate first')

        while retry_count > 0:
            response = requests.get(
                "%s/wallet/balance" % self.base_url,
                headers={'Authorization': 'Bearer %s' % self.token})
            if response.status_code == 200:
                response = response.json()
                availableMargin = Decimal(
                    response['balance']) - Decimal(response['position_margin'])
                return availableMargin
            elif response.status_code == 401:
                self.authenticate()
            elif int(response.status_code / 100) == 4:
                sleep(2)

        raise Exception('Error.%d Try again later' % response.status_code)

    def get_price_history(self, symbol, duration=5, resolution=1, retry_count=3):
        if not self.token:
            raise Exception('Need to authenticate first')
        if duration/resolution >= 500:
            raise Exception('Too many Data points')

        current_timestamp = time.mktime(datetime.datetime.today().timetuple())
        last_timestamp = current_timestamp - duration*60
        query = {
            'symbol': symbol,
            'from': last_timestamp,
            'to': current_timestamp,
            'resolution': resolution
        }

        while retry_count > 0:
            response = requests.get(
                "%s/chart/history" % self.base_url,
                params=query,
                headers={'Authorization': 'Bearer %s' % self.token})
            retry_count -= 1
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                self.authenticate()
            elif int(response.status_code / 100) == 4:
                sleep(2)

        raise Exception('Error.%d Try again later' % response.status_code)

    def get_marked_price(self, product_id, retry_count=3):
        if not self.token:
            raise Exception('Need to authenticate first')

        while retry_count > 0:
            response = requests.get(
                "%s/orderbook/%s/l2" % (self.base_url, product_id),
                headers={'Authorization': 'Bearer %s' % self.token})
            if response.status_code == 200:
                response = response.json()
                return float(response['mark_price'])
            elif response.status_code == 401:
                self.authenticate()
            elif int(response.status_code / 100) == 4:
                sleep(2)

        raise Exception('Error.%d Try again later' % response.status_code)

    def get_leverage(self):
        raise Exception('Method not implemented')

    def close_position(self, product_id, retry_count=3):
        if not self.token:
            raise Exception('Need to authenticate first')

        while retry_count > 0:
            response = requests.get(
                "%s/positions" % self.base_url,
                headers={'Authorization': 'Bearer %s' % self.token})
            retry_count -= 1
            if response.status_code == 200:
                response = response.json()
                current_position = list(
                    filter(lambda x: x['product']['id'] == product_id, response))
                if len(current_position) > 0:
                    size = current_position[0]['size']
                    if size > 0:
                        order = {
                            'product_id': product_id,
                            'size': size,
                            'side': 'sell',
                            'order_type': 'market_order'
                        }
                    else:
                        order = {
                            'product_id': product_id,
                            'size': abs(size),
                            'side': 'buy',
                            'order_type': 'market_order'
                        }
                    self.create_order(order=order)
                return
            elif response.status_code == 401:
                self.authenticate()
            elif int(response.status_code / 100) == 4:
                sleep(2)

        raise Exception('Error.%d Try again later' % response.status_code)

    def get_position(self, product_id, retry_count=3):
        if not self.token:
            raise Exception('Need to authenticate first')

        while retry_count > 0:
            response = requests.get(
                "%s/positions" % self.base_url,
                headers={'Authorization': 'Bearer %s' % self.token})
            retry_count -= 1
            if response.status_code == 200:
                response = response.json()
                if response:
                    current_position = list(
                        filter(lambda x: x['product']['id'] == product_id, response))
                    return current_position[0] if len(current_position) > 0 else None

                else:
                    return None
            elif response.status_code == 401:
                self.authenticate()
            elif int(response.status_code / 100) == 4:
                sleep(2)

        raise Exception('Error.%d Try again later' % response.status_code)

    def set_leverage(self, product_id, leverage, retry_count=3):
        if not self.token:
            raise Exception('Need to authenticate first')

        data = {
            'product_id': product_id,
            'leverage':  leverage
        }
        while retry_count > 0:
            response = requests.post(
                "%s/orders/leverage" % self.base_url,
                data=data,
                headers={'Authorization': 'Bearer %s' % self.token})
            retry_count -= 1
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                self.authenticate()
            elif int(response.status_code / 100) == 4:
                sleep(2)

        raise Exception('Error.%d Try again later' % response.status_code)
