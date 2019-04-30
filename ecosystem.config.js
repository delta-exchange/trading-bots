module.exports = {
  "apps": [{
    "name": "MyBot",
    "script": "strategy_runner.py",
    "env": {
      "DOTENVS": "market_maker",
      "BOT": "MyBot",
      "DELTA_ACCOUNTS": "delta@account.com",
      "STRATEGY": "unhedged",
      "DELTA_PRODUCT_ID": 16,
      "DELTA_PRODUCT_SYMBOL": "BTCUSD",
      "MAX_LEVERAGE": 1,
      "IMPACT_SIZE": 1000,
      "LOOP_INTERVAL": 3,
      "BALANCE_POSITION_INTERVAL": 2,
      "VOLUME_BOT_MIN_QUANTITY": 10,
      "VOLUME_BOT_MAX_QUANTITY": 100,
      "RUN_VOLUME_BOT": 1,
      "DIFF_PRICE_PERCENT": 0,
      "LOG_FILE": "log/MyBot-unhedged.log",
      "MIN_LEVEL_SIZE": 10000,
      "MAX_LEVEL_SIZE": 100000,
      "AUTO_TOPUP_THRESHOLD": 10
    }
  }]
};