import logging
from time import sleep
import signal
import sys
import os
import random
import traceback
import requests
from decimal import Decimal
import operator
import socket
from functools import wraps
import math

import json
from clients.delta import Delta
from delta_rest_client import create_order_format, round_by_tick_size

from utils.utility import takePrice, round_price_by_tick_size
from utils.alerts import slack
from abc import ABC, abstractmethod
from config import accounts
import custom_exceptions


class BaseMarketMaker(ABC):
    def __init__(self):
        self.trading_paused = False
        self.exit_run_loop = False
        self.bot_name = os.getenv("BOT")
        logfile = os.getenv('LOG_FILE')
        self.setup_logger(logfile)
        self.num_levels = int(os.getenv('NUM_LEVELS'))
        self.min_levels = int(os.getenv('MIN_NUM_LEVELS'))
        self.diff_size_percent = Decimal(os.getenv('DIFF_SIZE_PERCENT'))
        self.diff_price_percent = Decimal(
            os.getenv('DIFF_PRICE_PERCENT'))
        self.post_only = os.getenv('POST_ONLY')
        self.loop_interval = float(os.getenv('LOOP_INTERVAL'))
        self.buy_price_scale_factor = Decimal(
            os.getenv('BUY_PRICE_SCALING_FACTOR'))
        self.sell_price_scale_factor = Decimal(
            os.getenv('SELL_PRICE_SCALING_FACTOR'))
        self.delta_product_symbol = os.getenv("DELTA_PRODUCT_SYMBOL")
        signal.signal(signal.SIGINT, self.exit)
        self.delta_setup()

    @abstractmethod
    def generate_orders(self):
        raise NotImplementedError

    @abstractmethod
    def sanity_check(self):
        pass

    # Check for risk limits and filter orders as per allowed limits
    @abstractmethod
    def apply_risk_limits(self, buy_orders, sell_orders):
        raise NotImplementedError

    def delta_setup(self, channels=[], callback=None):
        maker_account = accounts.exchange_accounts('delta')[0]
        self.product_id = int(os.getenv('DELTA_PRODUCT_ID'))
        self.delta = Delta(
            account=maker_account,
            channels=channels,
            product_id=self.product_id,
            callback=callback
        )
        self.product = self.delta.get_product(self.product_id)
        self.tick_size = round_price_by_tick_size(
            self.product['tick_size'], self.product['tick_size'])
        self.logger.info(self.tick_size)
        self.cancel_open_orders()

        # Set order leverage on delta
        max_delta_leverage = os.getenv("MAX_LEVERAGE")
        self.delta.set_leverage(
            product_id=self.product_id, leverage=max_delta_leverage)

    def is_inverse_future(self):
        return self.product['product_type'] == 'inverse_future'

    def is_perpetual(self):
        return self.product['contract_type'] == 'perpetual_futures'

    def setup_logger(self, logfile):
        # Remove old logger handlers if any
        if hasattr(self, 'logger'):
            getattr(self, 'logger').handlers = []
        formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(message)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')
        handler = logging.FileHandler(logfile, mode='a')
        handler.setFormatter(formatter)
        screen_handler = logging.StreamHandler(stream=sys.stdout)
        screen_handler.setFormatter(formatter)
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        # if self.logger.handlers:
        #     print('Logger exists-------------------------------------------------')
        self.logger.handlers = []
        self.logger.addHandler(handler)
        self.logger.addHandler(screen_handler)

    def notional(self, size, price):
        if size == 0 or price is None:
            return Decimal(0)
        else:
            return Decimal(size) * (1 / Decimal(price)
                                    if self.is_inverse_future() else Decimal(price))

    def get_open_orders(self):
        return self.delta.get_open_orders(self.product_id)

    def cancel_open_orders(self):
        open_orders = self.get_open_orders()
        self.logger.info('Cancelling %d open order on delta' %
                         len(open_orders))

        self.delta.batch_cancel(self.product_id, open_orders)

    def delta_position(self):
        current_position_delta = self.delta.position(self.product_id)
        size = current_position_delta['size']
        if size != 0:
            size = current_position_delta['size'] * self.delta.contract_size
        current_position_delta['size'] = round_price_by_tick_size(
            size, self.delta.contract_size
        )
        current_position_delta['notional'] = self.notional(
            current_position_delta['size'], current_position_delta['entry_price'])
        return current_position_delta

    def delta_margin(self):
        return self.delta.funds()

    def diff(self, old_order, new_order):
        # TODO : handle sign for buy/sell
        # TODO : handle change in quantity
        if old_order['size'] == 0:
            return 3
        change_price = (takePrice(new_order) -
                        takePrice(old_order)) * Decimal(100.0000) / takePrice(old_order)
        change_size = (new_order['size'] - old_order['size']
                       ) * 100.0000 / old_order['size']

        if abs(change_size) > self.diff_size_percent and abs(change_price) <= self.diff_price_percent:
            return 2    # Size has changed significantly, price is same
        elif abs(change_price) > self.diff_price_percent:
            self.logger.debug('Price diff %s %s' %
                              (change_price, self.diff_price_percent))
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
            self.logger.debug('DIFF %s %s %s %d' %
                              (side, takePrice(old_orders[i]), takePrice(new_orders[j]), diff_level))
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

    def converge_orders(self, buy_orders, sell_orders, max_bid=None, min_ask=None):
        # Get all open orders from delta
        old_open_orders = self.get_open_orders()
        for order in old_open_orders:
            order['size'] = order['unfilled_size']
        # filter current asks and bids from open orders
        old_sell_orders = list(
            filter(lambda x: x['side'] == 'sell', old_open_orders))
        old_sell_orders.sort(key=takePrice)
        old_buy_orders = list(
            filter(lambda x: x['side'] == 'buy', old_open_orders))
        old_buy_orders.sort(key=takePrice, reverse=True)

        orders_to_create = []
        orders_to_delete = []
        orders_to_edit = []

        if max_bid:
            # Collect all old buy orders with price > max_bid and add them to delete list
            while len(old_buy_orders) > 0:
                if Decimal(takePrice(old_buy_orders[0])) > max_bid:
                    orders_to_delete.append(old_buy_orders.pop(0))
                else:
                    break
            # remove all buy orders where price > max_bid
            buy_orders = list(filter(lambda x: Decimal(
                takePrice(x)) <= max_bid, buy_orders))

        if min_ask:
            # Collect all old sell orders with price < min_ask and add them to delete list
            while len(old_sell_orders) > 0:
                if Decimal(takePrice(old_sell_orders[0])) < min_ask:
                    orders_to_delete.append(old_sell_orders.pop(0))
                else:
                    break
            # remove all sell orders where price < min_ask
            sell_orders = list(filter(lambda x: Decimal(
                takePrice(x)) >= min_ask, sell_orders))

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
        if len(sell_create) > 0 and len(sell_delete) > 0:
            trend = self.market_trend(
                sell_create, sell_delete, side='sell')
        elif len(buy_create) > 0 and len(buy_delete) > 0:
            trend = self.market_trend(
                buy_create, buy_delete, side='buy')
        else:
            trend = 0
        buy_edit, buy_create, buy_delete = self.get_orders(
            buy_create, buy_delete)
        sell_edit, sell_create, sell_delete = self.get_orders(
            sell_create, sell_delete)

        # Downtrend
        if trend == -1:
            orders_to_edit = orders_to_edit + buy_edit + sell_edit
        # Uptrend
        elif trend == 1:
            orders_to_edit = orders_to_edit + sell_edit + buy_edit
        else:
            orders_to_edit = orders_to_edit + sell_edit + buy_edit

        orders_to_create = orders_to_create + sell_create + buy_create
        orders_to_delete = orders_to_delete + sell_delete + buy_delete

        self.logger.info('Orders to be deleted %d' % len(orders_to_delete))
        self.logger.info('Orders to be edited %d' % len(orders_to_edit))
        self.logger.info('Orders to be created %d' % len(orders_to_create))

        if orders_to_delete:
            self.delta.batch_cancel(self.product_id, orders_to_delete)
        if orders_to_edit:
            self.delta.batch_edit(self.product_id, orders_to_edit)
        if orders_to_create:
            self.delta.batch_create(self.product_id, orders_to_create)

    def market_trend(self, create_orders, delete_orders, side='sell'):
        if side == 'sell':
            op = min
        else:
            op = max
        old_best_price = Decimal(op(map(
            lambda x: x['limit_price'], delete_orders
        )))
        new_best_price = Decimal(op(map(
            lambda x: x['limit_price'], create_orders
        )))
        price_diff = new_best_price - old_best_price
        if price_diff > 0:
            return 1
        elif price_diff < 0:
            return -1
        else:
            return 0

    def get_orders(self, create_orders, delete_orders):
        orders_to_edit = []
        orders_to_create = []
        orders_to_delete = []

        def edit_append(create_order, delete_order, edit_orders):
            edit_orders.append({
                'id': delete_order['id'],
                'product_id': create_order['product_id'],
                'limit_price': create_order['limit_price'],
                'unfilled_size': create_order['size'],
                'post_only': self.post_only
            })
        delete_orders = list(filter(
            lambda o: o.update(
                {'notional': str(self.notional(o['size'], o['limit_price']))}) or o, delete_orders
        ))
        create_orders = list(filter(
            lambda o: o.update(
                {'notional': str(self.notional(o['size'], o['limit_price']))}) or o, create_orders
        ))
        extra_notional = 0
        while len(create_orders) > 0 and len(delete_orders) > 0:
            delete_order = delete_orders.pop(0)
            create_order = create_orders.pop(0)
            create_order_notional = Decimal(create_order['notional'])
            delete_order_notional = Decimal(delete_order['notional'])
            if create_order_notional > delete_order_notional + extra_notional:
                extra_notional += delete_order_notional
                orders_to_delete.append(delete_order)
                create_orders.insert(0, create_order)
            else:
                edit_append(create_order, delete_order, orders_to_edit)
                extra_notional += delete_order_notional - \
                    create_order_notional

        orders_to_create += create_orders
        orders_to_delete += delete_orders
        return orders_to_edit, orders_to_create, orders_to_delete

    # Create order format for buy and sell orders
    def create_order_format(self, buy_orders, sell_orders):
        buy_price_scale_factor = self.buy_price_scale_factor
        sell_price_scale_factor = self.sell_price_scale_factor
        buy_orders = list(filter(
            lambda x: x['size'] >= self.delta.contract_size, buy_orders))
        sell_orders = list(filter(
            lambda x: x['size'] >= self.delta.contract_size, sell_orders))

        for buy_order in buy_orders:
            buy_order['size'] /= self.delta.contract_size
            buy_order['size'] = int(buy_order['size'])

        for sell_order in sell_orders:
            sell_order['size'] /= self.delta.contract_size
            sell_order['size'] = int(sell_order['size'])

        buy_orders = list(map(
            lambda o: create_order_format(
                price=round_by_tick_size(
                    Decimal(o['price']) *
                    buy_price_scale_factor,
                    self.tick_size,
                    'floor'
                ),
                size=o['size'], side='buy', product_id=self.product_id,
                post_only=self.post_only
            ), buy_orders))
        sell_orders = list(map(
            lambda o: create_order_format(
                price=round_by_tick_size(
                    Decimal(o['price']) *
                    sell_price_scale_factor,
                    self.tick_size,
                    'ceil'
                ),
                size=o['size'], side='sell', product_id=self.product_id,
                post_only=self.post_only
            ), sell_orders))
        return buy_orders, sell_orders

    def stop_trading(self, halt_message=None, send_email=True):
        self.cancel_open_orders()
        if halt_message:
            self.logger.info("Trading stopped: " + halt_message)
        if send_email and os.getenv('SEND_ALERTS'):
            slack(message=halt_message)
        sys.exit()

    def pause_trading(self, halt_message=None, halting_time=10, send_email=True):
        self.trading_paused = True
        # TODO : Avoid race conditions with loop
        if halt_message:
            self.logger.info("Trading paused: " + halt_message)
        self.cancel_open_orders()
        if send_email and os.getenv('SEND_ALERTS').lower() == 'true':
            # TODO: Send alert
            pass
        self.logger.info('Sleeping for %d seconds' % halting_time)
        sleep(halting_time)
        self.trading_paused = False

    def exit(self, signum, frame):
        self.stop_trading("Manual Termination", send_email=False)

    def get_top_orders_by_size(self, orders, size, enforce_min_levels=False):
        min_size_per_level = Decimal(size / self.min_levels)
        selected_orders = []
        leftover_orders = []
        while size > 0 and len(orders) > 0:
            order = orders.pop(0)
            size_limit = min_size_per_level
            level_size = min(size_limit,
                             size) if enforce_min_levels else size
            if order['size'] > level_size:
                selected_orders.append({
                    'price': order['price'],
                    'size': level_size
                })
                order['size'] -= level_size
                size = size - level_size
                leftover_orders.insert(0, order)
            else:
                size = size - order['size']
                selected_orders.append(order)
        for order in leftover_orders:
            orders.insert(0, order)
        return selected_orders

    def get_top_orders_by_notional(self, orders, notional, enforce_min_levels=False):
        max_notional_per_level = notional / self.min_levels
        selected_orders = []
        leftover_orders = []
        while notional > 0 and len(orders) > 0:
            order = orders.pop(0)
            notional_limit = max_notional_per_level
            level_notional = min(notional_limit,
                                 notional) if enforce_min_levels else notional
            order_notional = self.notional(order['size'], order['price'])
            if order_notional > level_notional:
                new_size = order['size'] * level_notional / order_notional
                if new_size > 0:
                    order['size'] -= new_size
                    selected_orders.append({
                        'price': order['price'],
                        'size': new_size
                    })
                    notional = notional - \
                        self.notional(new_size, order['price'])
                if order['size'] > 0:
                    leftover_orders.insert(0, order)
            else:
                notional = notional - order_notional
                selected_orders.append(order)
        for order in leftover_orders:
            orders.insert(0, order)
        return selected_orders, notional

    def merge_levels(self, orders):
        merged_orders = []
        last_order = None
        for order in orders:
            if last_order is None:
                last_order = order
            elif last_order['price'] == order['price']:
                last_order['size'] = last_order['size'] + order['size']
            else:
                merged_orders.append(last_order)
                last_order = order
        if last_order is not None:
            merged_orders.append(last_order)
        return merged_orders

    def run_loop(self):
        while True:
            self.logger.info(
                '----------------Run loop started--------------')
            try:
                if not self.trading_paused:
                    should_update, buy_orders, sell_orders = self.generate_orders()
                    if should_update:
                        buy_orders, sell_orders = self.apply_risk_limits(
                            buy_orders, sell_orders)
                        buy_orders, sell_orders = self.merge_levels(
                            buy_orders), self.merge_levels(sell_orders)
                        buy_orders, sell_orders = self.create_order_format(
                            buy_orders, sell_orders)
                        self.converge_orders(buy_orders, sell_orders)
                sleep(self.loop_interval)
            except socket.timeout as e:
                self.logger.info(str(e))
                sleep(2)
            except custom_exceptions.InsufficientMarginError as e:
                message = '%s exception raised at %s. Insufficient Margin Error, Status: %s' % (
                    self.bot_name, e.client, e.status_code)
                self.pause_trading(halt_message=message, halting_time=5)
            except (custom_exceptions.LowerThanBankruptcyError, custom_exceptions.LowOrderSizeError, custom_exceptions.InvalidOrder, custom_exceptions.EditOrderError) as e:
                message = '%s exception raised at %s. Bad Request Error, Status: %s' % (
                    self.bot_name, e.client, e.status_code)
                self.logger.info(message)
                sleep(self.loop_interval)
            except (custom_exceptions.NonceError, custom_exceptions.AuthenticationError, custom_exceptions.ContractExpiredError) as e:
                message = '%s exception raised at %s. Authentication Error, Status: %s' % (
                    self.bot_name, e.client, e.status_code)
                self.pause_trading(halt_message=message, halting_time=2)
            except custom_exceptions.TooManyRequestsError as e:
                message = '%s exception raised at %s. TooManyRequestsError, Status: %s' % (
                    self.bot_name, e.client, e.status_code)
                self.logger.info(message)
                sleep(20)
            except (custom_exceptions.BadGatewayError, custom_exceptions.ServiceUnavailabeError, custom_exceptions.MarketDisrupted, custom_exceptions.InternalServerError) as e:
                message = '%s exception raised at %s. ServerError, Status: %s' % (
                    self.bot_name, e.client, e.status_code)
                self.logger.info(message)
                sleep(5)
            except custom_exceptions.BadRequestError as e:
                message = '%s exception raised at %s. BadRequestError, Status: %s' % (
                    self.bot_name, e.client, e.status_code)
                self.pause_trading(halt_message=message, halting_time=5)
            except custom_exceptions.UnknownError as e:
                message = '%s exception raised at %s. UnknownError, Status: %s' % (
                    self.bot_name, e.client, e.status_code)
                self.pause_trading(halt_message=message, halting_time=5)
            except Exception as e:
                message = '%s exception raised.Message: %s' % (
                    self.bot_name, str(e))
                traceback.print_exc()
                while True:
                    try:
                        self.pause_trading(
                            halt_message=message, halting_time=5)
                        break
                    except Exception as e1:
                        self.logger.info(
                            'Exception raised while pausing : %s' % str(e1))
                        pass
