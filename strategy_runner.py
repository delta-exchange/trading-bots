import os
import json
import traceback
from raven import Client
from market_maker.unhedged import UnhedgedMarketMaker

from config import dotenv


def main():
    strategy = os.getenv('STRATEGY')
    if strategy is not None:
        strategy_name = strategy.lower()
    else:
        raise BaseException('Please pass STRATEGY environment variable')

    if strategy_name == 'unhedged':
        UnhedgedMarketMaker().run_loop()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        traceback.print_exc()
