import os
import random
from time import sleep
from decimal import Decimal
from market_maker.base import BaseMarketMaker
from clients.delta import Delta, OrderState, OrderType
from delta_rest_client import cancel_order_format
from utils.alerts import slack
from utils.utility import round_price_by_tick_size
from utils.margin_helper import calculateMarginFromLiquidationPrice, funding_dampener
import operator

import json


class UnhedgedMarketMaker(BaseMarketMaker):
    def __init__(self):
        self.max_leverage = int(os.getenv('MAX_LEVERAGE'))
        self.auto_topup_threshold = Decimal(os.getenv('AUTO_TOPUP_THRESHOLD'))
        self.min_level_size = int(os.getenv('MIN_LEVEL_SIZE'))
        self.max_level_size = int(os.getenv('MAX_LEVEL_SIZE'))
        super().__init__()

    def delta_setup(self):
        channels = ['trading_notifications', 'l2_orderbook', 'positions']
        super().delta_setup(channels=channels)
        self.delta.subscribeChannel(
            'mark_price', "MARK:%s" % (self.product['symbol']))
        self.delta.subscribeChannel(
            'spot_price', self.product['spot_index']['symbol'])

    def exit(self, signum, frame):
        self.delta.disconnect()
        super().exit(signum, frame)

    # Get impact squareoff
    def get_impact_squareoff(self, size, orders):
        fills = []
        for order in orders:
            fill_size = min(size, order['size'])
            size = size - fill_size
            fills.append([order['price'], fill_size])
            if size == 0:
                break
        avg_price = sum(map(
            lambda x: x[0] * x[1], fills
        )) / sum(map(lambda x: x[1], fills))
        return avg_price

    def apply_risk_limits(self, buy_orders, sell_orders):
        return buy_orders, sell_orders

    def check_for_position_auto_topup(self):
        current_delta_position = self.delta_position()
        if current_delta_position['size'] != 0:
            current_liquidation_price = current_delta_position['liquidation_price']
            current_mark_price = self.delta.mark_price(self.product_id)
            distance = abs(current_liquidation_price -
                           current_mark_price) * 100 / current_mark_price
            if distance < self.auto_topup_threshold:
                if current_delta_position['size'] > 0:
                    new_liquidation_price = current_mark_price * \
                        (1 - self.auto_topup_threshold/100)
                else:
                    new_liquidation_price = current_mark_price * \
                        (1 + self.auto_topup_threshold/100)
                margin = calculateMarginFromLiquidationPrice(
                    current_delta_position['size'] *
                    Decimal(self.product['contract_value']),
                    current_delta_position['entry_price'],
                    new_liquidation_price,
                    Decimal(self.product['maintenance_margin']),
                    isInverse=self.is_inverse_future()
                )
                delta_margin = margin - current_delta_position['margin']
                if delta_margin > 0:
                    funds = self.delta.available_funds()
                    if funds > delta_margin:
                        self.logger.info(
                            'Liquidation price too close, Auto Top up trigger')
                        self.delta.addPositionMargin(
                            self.product_id, str(delta_margin))
                        self.logger.info('Auto Top up complete')
                    else:
                        message = "Liquidation price too close, but not enough balance for auto top up"
                        self.logger.info(message)
                        if os.getenv('SEND_ALERTS').lower() == 'true':
                            # TODO: Send alert
                            pass

    def sanity_check(self):
        super().sanity_check()
        self.logger.info('Sanity check')
        if not self.delta.isConnected():
            self.delta.reconnect()
        self.check_for_position_auto_topup()

    def pause_trading(self, halt_message=None, halting_time=10, send_email=True):
        self.trading_paused = True
        if halt_message:
            self.logger.info("Trading paused: " + halt_message)
        self.cancel_open_orders()
        if send_email and os.getenv('SEND_ALERTS').lower() == 'true':
            # TODO: send alert
            pass
        self.logger.info('Sleeping for %d seconds' % halting_time)
        sleep(halting_time)
        self.trading_paused = False

    def generate_orders(self):
        delta_spot_price = self.delta.spot_price(
            self.product['spot_index']['symbol'], self.product_id)
        buy_orders = []
        sell_orders = []
        for i in range(1, self.num_levels + 1):
            buy_orders.append({
                'price': delta_spot_price - i * self.tick_size,
                'size': random.randint(self.min_level_size, self.max_level_size)
            })
            sell_orders.append({
                'price': delta_spot_price + i * self.tick_size,
                'size': random.randint(self.min_level_size, self.max_level_size)
            })
        return True, buy_orders, sell_orders
