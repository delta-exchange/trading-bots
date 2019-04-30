# Delta Trading Bots

Collection of publicly available strategies and trading bots for trading bitcoin futures on delta.

## Compatibility

This module supports Python 3.5 and later.

## Disclaimer

Delta is not responsible for any losses incurred when using this code. This code is intended for sample purposes ONLY - do not use this code for real trades unless you fully understand what it does and what its caveats are.

Develop on Testnet first!

## Project Setup

1.  Create a [Testnet Delta account](https://testnet.delta.exchange) and deposit some BTC

2.  Create a new virtualenv and install dependencies

```
virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements.txt
```

3.  create a log folder

```
mkdir log
```

## Market Making Bot

Market Makers profit by charging higher offer prices than bid prices. The difference is called the ‘spread’. The spread compensates the market makers for the risk inherited in such trades. The risk is the price movement against the market makers trading position.

### How to run

1.  You can create multiple configurations for multiple running instances. Lets create a configuration for running the bot on testnet

2.  Copy `config/.env.sample` to `config/.env.testnet`. You can tweak settings here.

3.  Edit `config/accounts.json` to enter your account credentials.

4.  From the root folder, Pass the environment and run `strategy_runner.py` 

5.  You can also run your strategy from pm2, add your bot configurations in `ecosystem.config.js` 
```
pm2 start ecosystem.config.js --only
```

### How to customize

1.  Writing your own custom strategy is super easy. Just refer to `market_maker/custom_strategy.py`
2.  Once you define your custom_strategy, you can run it like

```
from market_maker.custom_strategy import CustomStrategy
mm = CustomStrategy()
mm.run_loop()
```
