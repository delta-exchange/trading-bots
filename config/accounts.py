import os
import json

global accounts
accounts = json.loads(open(os.path.join(os.path.dirname(__file__),
                                        'prod_accounts.json')).read())


def exchange_accounts(exchange):
    account_list = os.getenv("%s_ACCOUNTS" % exchange.upper()).split(',')
    return list(map(lambda account: accounts[exchange][account], account_list))
