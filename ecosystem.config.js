module.exports = {
  "apps": [{
    "name": "MyBot",
    "script": "strategy_runner.py",
    "env": {
      "DOTENVS": "sample",
      "BOT": "MyBot",
      "DELTA_ACCOUNTS": "delta@account.com",
      "STRATEGY": "unhedged",
      "DELTA_PRODUCT_ID": 24,
      "DELTA_PRODUCT_SYMBOL": "BTCUSD_28Jun",
      "MAX_LEVERAGE": 1,
      "IMPACT_SIZE": 1000,
      "LOOP_INTERVAL": 3,
      "NUM_LEVELS": 5,
      "NUM_LEVELS": 6,
      "DIFF_SIZE_PERCENT": 0,
      "MIN_NUM_LEVELS": 5,
      "DIFF_PRICE_PERCENT": 0,
      "BUY_PRICE_SCALING_FACTOR": 1.0000,
      "SELL_PRICE_SCALING_FACTOR": 1.0000,
      "LOG_FILE": "log/MyBot-unhedged.log",
      "MIN_LEVEL_SIZE": 100,
      "MAX_LEVEL_SIZE": 1000,
      "AUTO_TOPUP_THRESHOLD": 10
    }
  }]
};