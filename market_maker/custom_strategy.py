import sys

from market_maker.market_maker import MarketMaker


class CustomStrategy(MarketMaker):
    def __init__(self):
        super().__init__()
        self.setup_logger('log/custom_strategy.log')

    def generate_orders(self):
        buy_orders = []
        sell_orders = []
        return (buy_orders, sell_orders)
