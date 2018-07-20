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
virtualenv --python=python3.5 venv
source venv/bin/activate
pip install -r requirements.txt
```

## Market Making Bot

Market Makers profit by charging higher offer prices than bid prices. The difference is called the ‘spread’. The spread compensates the market makers for the risk inherited in such trades. The risk is the price movement against the market makers trading position.

### How to run

1.  You can create multiple configurations for multiple running instances. Lets create a configuration for running the bot on testnet

2.  Copy market_maker/.env.sample to market_maker/.env.testnet

3.  Edit market_maker/.env.testnet to enter your account credentials. You can tweak other settings as well.

4.  From the root folder, Pass the environment and run market_maker.py

```
ENVIRONMENT=testnet python market_maker.py
```
