import logging
from time import sleep
import websocket
import datetime
import signal
import sys
import os
import random
import pprint
import dateparser
import json
import traceback
from decimal import *

from market_maker.delta.rest_client import DeltaRestClient
from market_maker.delta.utility import *
from market_maker.delta.socket import DeltaWebSocket

import market_maker.settings


class MarketMaker:
    def __init__(self):
        self.trading_paused = False

        self.delta_base_url = os.getenv('DELTA_REST_URL')
        self.delta_ws_url = os.getenv('DELTA_WS_URL')
        self.delta_username = os.getenv('DELTA_USERNAME')
        self.delta_password = os.getenv('DELTA_PASSWORD')

        self.delta_client = DeltaRestClient(
            base_url=self.delta_base_url,
            username=self.delta_username,
            password=self.delta_password
        )

        self.delta_ws = DeltaWebSocket(
            ws_endpoint=self.delta_ws_url,
            base_url=self.delta_base_url,
            username=self.delta_username,
            password=self.delta_password
        )

        self.product_id = int(os.getenv('DELTA_PRODUCT_ID'))
        self.product = self.delta_client.get_product(self.product_id)
        self.setup_logger('log/market_maker_bot.log')

        self.num_levels = int(os.getenv('NUM_LEVELS') or 20)
        self.diff_size_percent = 5
        self.diff_price_percent = 0.005

        self.order_price_interval = float(
            os.getenv('ORDER_PRICE_INTERVAL') or 0.003)
        self.level_size = int(os.getenv('LEVEL_SIZE') or 100)
        self.loop_interval = int(os.getenv('LOOP_INTERVAL') or 5)

        self.max_position = int(os.getenv('MAX_POSITION') or 100000)
        self.min_position = int(os.getenv('MIN_POSITION') or -100000)

        self.delta_ws.connect()
        signal.signal(signal.SIGINT, self.exit)

    def setup_logger(self, logfile):
        # Remove old logger handlers if any
        if hasattr(self, 'logger'):
            getattr(self, 'logger').handlers = []
        # Prints logger info to terminal
        logging.basicConfig(filename=logfile, level=logging.INFO)
        self.logger = logging.getLogger()
        ch = logging.StreamHandler()
        # create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        # add formatter to ch
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def diff(self, old_order, new_order):
        # TODO : handle sign for buy/sell
        # TODO : handle change in quantity

        change_price = (takePrice(new_order) -
                        takePrice(old_order)) * 100.0000 / takePrice(old_order)
        change_size = (new_order['size'] - old_order['size']
                       ) * 100.0000 / old_order['size']

        if abs(change_size) > self.diff_size_percent and abs(change_price) < self.diff_price_percent:
            return 2    # Size has changed significantly, price is same
        elif abs(change_price) > self.diff_price_percent:
            return 1    # Price has changed significantly
        else:
            return 0    # Levels are same, no need to recreate

    def calculate_orders_diff(self, side, old_orders, new_orders):
        orders_to_create = []
        orders_to_delete = []

        ops = {
            "<": operator.lt,
            ">": operator.gt
        }

        if side == 'buy':
            comparision = "<"
        else:
            comparision = ">"

        i = 0
        j = 0
        level_index = 0

        while i < len(old_orders) and j < len(new_orders) and level_index < self.num_levels:
            diff_level = self.diff(
                old_order=old_orders[i], new_order=new_orders[j])
            if diff_level == 2:
                # Size has changed
                orders_to_create.append(new_orders[j])
                orders_to_delete.append(old_orders[i])
                level_index += 1
                i += 1
                j += 1
            elif diff_level == 1:
                if ops[comparision](takePrice(old_orders[i]), takePrice(new_orders[j])):
                    orders_to_create.append(new_orders[j])
                    level_index += 1
                    j += 1
                else:
                    orders_to_delete.append(old_orders[i])
                    i += 1
            else:
                j += 1
                i += 1
                level_index += 1
        while i < len(old_orders):
            orders_to_delete.append(old_orders[i])
            i += 1
        while j < len(new_orders) and level_index < self.num_levels:
            orders_to_create.append(new_orders[j])
            level_index += 1
            j += 1

        return (orders_to_create, orders_to_delete)

    def converge_orders(self, buy_orders, sell_orders):
        # Get all open orders from delta
        query = {
            'product_id': self.product_id,
            'state': 'open',
            'page_num': 1,
            'page_size': 500
        }
        old_open_orders = self.delta_client.get_orders(query)
        for order in old_open_orders:
            order['size'] = order['unfilled_size']

        # filter current asks and bids from open orders
        old_sell_orders = list(
            filter(lambda x: x['side'] == 'sell', old_open_orders))
        old_sell_orders.sort(key=takePrice)
        old_buy_orders = list(
            filter(lambda x: x['side'] == 'buy', old_open_orders))
        old_buy_orders.sort(key=takePrice, reverse=True)

        # Using L2 order book to get best bid and best ask price
        best_buy_price, best_sell_price = self.delta_client.get_ticker(
            self.product_id)

        # Remove all orders which are worse than best bid and best ask
        buy_orders = list(filter(lambda x: takePrice(
            x) <= best_sell_price,  buy_orders))
        sell_orders = list(
            filter(lambda x: takePrice(x) >= best_buy_price,  sell_orders))

        buy_create, buy_delete = self.calculate_orders_diff(
            side='buy',
            old_orders=old_buy_orders,
            new_orders=buy_orders
        )

        sell_create, sell_delete = self.calculate_orders_diff(
            side='sell',
            old_orders=old_sell_orders,
            new_orders=sell_orders
        )

        orders_to_create = sell_create + buy_create
        orders_to_delete = sell_delete + buy_delete

        self.logger.info('Orders to be created %d' % len(orders_to_create))
        self.logger.info('Orders to be deleted %d' % len(orders_to_delete))

        if len(orders_to_delete) > 0:
            self.delta_client.batch_cancel(
                list(map(cancel_order_format, orders_to_delete)))
        if len(orders_to_create) > 0:
            self.delta_client.batch_create(orders_to_create)

    def generate_orders(self):
        # TODO : Don't consider my own orders
        current_position_delta = self.delta_client.get_position(
            product_id=self.product_id)
        if current_position_delta == None:
            current_delta_size = 0
        else:
            current_delta_size = current_position_delta['size']

        best_buy_price, best_sell_price = self.delta_client.get_ticker(
            self.product_id)
        buy_orders = []
        sell_orders = []
        for i in range(1, self.num_levels + 1):
            if best_buy_price > 0 and current_delta_size < self.max_position:
                buy_orders.append(
                    order_convert_format(
                        price=round_by_tick_size(
                            Decimal(best_buy_price) * (1 - (i-1)*Decimal(self.order_price_interval)), Decimal(self.product['tick_size']), 'floor'),
                        size=self.level_size,
                        side='buy',
                        product_id=self.product_id)
                )
            if best_sell_price < Decimal('inf') and current_delta_size > self.min_position:
                sell_orders.append(
                    order_convert_format(
                        price=round_by_tick_size(
                            Decimal(best_sell_price) * (1 + (i-1)*Decimal(self.order_price_interval)), Decimal(self.product['tick_size']), 'ceil'),
                        size=self.level_size,
                        side='sell',
                        product_id=self.product_id)
                )
        return (buy_orders, sell_orders)

    def cancel_open_orders(self):
        query = {
            'product_id': self.product_id,
            'state': 'open',
            'page_num': 1,
            'page_size': 500
        }
        open_orders = self.delta_client.get_orders(query)
        self.logger.info('Cancelling %d open order on delta' %
                         len(open_orders))
        if len(open_orders) > 0:
            self.delta_client.batch_cancel(
                list(map(cancel_order_format, open_orders)))

    def stop_trading(self, halt_message=None, send_email=True):
        self.cancel_open_orders()
        if halt_message:
            self.logger.info("Trading stopped: " + halt_message)
        if send_email and os.getenv('SEND_ALERTS'):
            emailer(message=halt_message,
                    recipient=self.delta_client.get_username())
        sys.exit()

    def pause_trading(self, halt_message=None, halting_time=30, send_email=True):
        self.trading_paused = True
        # TODO : Avoid race conditions with loop
        self.cancel_open_orders()
        if halt_message:
            self.logger.info("Trading paused: " + halt_message)
        if send_email and os.getenv('SEND_ALERTS'):
            emailer(message=halt_message,
                    recipient=self.delta_client.get_username())
        self.logger.info('Sleeping for %d seconds' % halting_time)
        sleep(halting_time)
        self.trading_paused = False

    def exit(self, signum, frame):
        self.stop_trading("Manual Termination", send_email=False)

    def sanity_check(self):
        if not self.delta_ws.isConnected():
            self.delta_ws.reconnect()

    def run_loop(self):
        while True:
            # try:
            if not self.trading_paused:
                sleep(self.loop_interval)
                self.sanity_check()
                buy_orders, sell_orders = self.generate_orders()
                self.converge_orders(buy_orders, sell_orders)
            # except Exception as e:
            #     traceback.print_exc()
            #     self.pause_trading(
            #         halt_message=str(e))
