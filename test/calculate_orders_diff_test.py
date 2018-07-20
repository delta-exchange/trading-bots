import sys
import os
from decimal import *

sys.path.append(os.path.join(sys.path[0], '..'))

from market_maker.market_maker import MarketMaker

mm = MarketMaker()


def delta_format_order(side, level):
    order = {
        'limit_price': Decimal(level[0]),
        'side': side,
        'order_type': 'limit_order',
        'size': level[1],
        'product_id': 2
    }
    return order


# # ########################################################
# Blank initialization.
print("Testcase 1 : Blank state/Initialization")
side = 'sell'
old_orders = []
new_orders = list(map(lambda x: delta_format_order(
    side, x), [[6630, 12248], [6630.5, 3000]]))

orders_to_create, orders_to_delete = mm.calculate_orders_diff(
    side=side,
    old_orders=old_orders,
    new_orders=new_orders
)

expected_create = [
    {'order_type': 'limit_order', 'limit_price': Decimal(
        '6630'), 'size': 12248, 'product_id': 2, 'side': 'sell'},
    {'order_type': 'limit_order', 'limit_price': Decimal(
        '6630.5'), 'size': 3000, 'product_id': 2, 'side': 'sell'},
]
expected_delete = []
assert (orders_to_create == expected_create), "Orders to create failed"
assert (orders_to_delete == expected_delete), "Orders to remove failed"

# # ########################################################

# Random different sizes
print("Testcase 2 : Random different sizes")
side = 'sell'
old_orders = list(
    map(lambda x: delta_format_order(side, x), [[6630, 500], [6630.5, 300]]))
new_orders = list(
    map(lambda x: delta_format_order(side, x), [[6630, 12248], [6630.5, 300], [6631, 30105]]))

orders_to_create, orders_to_delete = mm.calculate_orders_diff(
    side=side,
    old_orders=old_orders,
    new_orders=new_orders
)


expected_create = [
    {'product_id': 2, 'limit_price': Decimal(
        '6630'), 'order_type': 'limit_order', 'side': 'sell', 'size': 12248},
    {'product_id': 2, 'limit_price': Decimal(
        '6631'), 'order_type': 'limit_order', 'side': 'sell', 'size': 30105},
]

expected_delete = [
    {'product_id': 2, 'limit_price': Decimal(
        '6630'), 'order_type': 'limit_order', 'side': 'sell', 'size': 500}
]

assert (orders_to_create == expected_create), "Orders to create failed"
assert (orders_to_delete == expected_delete), "Orders to remove failed"


# # #######################################################################

# This is when all levels are same
print("Testcase 3 : All levels are same.")
side = 'buy'
old_orders = list(
    map(lambda x: delta_format_order(side, x), [[6630, 12248], [6630.5, 300], [6631, 30105]]))
new_orders = list(
    map(lambda x: delta_format_order(side, x), [[6630, 12248], [6630.5, 300], [6631, 30105]]))


orders_to_create, orders_to_delete = mm.calculate_orders_diff(
    side=side,
    old_orders=old_orders,
    new_orders=new_orders
)


expected_create = []
expected_delete = []

assert (orders_to_create == expected_create), "Orders to create failed"
assert (orders_to_delete == expected_delete), "Orders to remove failed"

# ######################################################

# one of the level is eaten up ( order deletion and creation is done again)
print("Testcase 4 : One of the level is eaten up")

side = 'sell'
old_orders = list(
    map(lambda x: delta_format_order(side, x), [[6630, 2448], [6630.5, 600], [6631, 600],
                                                [6632, 6000]]))

new_orders = list(
    map(lambda x: delta_format_order(side, x), [[6630.5, 600], [6631, 600],
                                                [6632, 6000]]))

orders_to_create, orders_to_delete = mm.calculate_orders_diff(
    side=side,
    old_orders=old_orders,
    new_orders=new_orders
)

expected_create = []
expected_delete = [{'order_type': 'limit_order', 'limit_price': Decimal(6630), 'side': 'sell',
                    'size': 2448, 'product_id': 2}]
assert (orders_to_create == expected_create), "Orders to create failed"
assert (orders_to_delete == expected_delete), "Orders to remove failed"


# ######################################################

# Taking the case when an additional level is Added
print("Testcase 6 : An additional level is added")
side = 'sell'
old_orders = list(
    map(lambda x: delta_format_order(side, x), [[6630, 2448], [6631, 6020],
                                                [6632, 6000], [6633.5, 35]]))
new_orders = list(
    map(lambda x: delta_format_order(side, x), [[6630, 2448], [6630.5, 3000], [6631, 6020],
                                                [6632, 6000], [6633.5, 35]]))


orders_to_create, orders_to_delete = mm.calculate_orders_diff(
    side=side,
    old_orders=old_orders,
    new_orders=new_orders
)


expected_create = [{'size': 3000, 'order_type': 'limit_order',
                    'product_id': 2, 'limit_price': Decimal('6630.5'), 'side': 'sell'}]
expected_delete = []
assert (orders_to_create == expected_create), "Orders to create failed"
assert (orders_to_delete == expected_delete), "Orders to remove failed"
