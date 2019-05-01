from decimal import Decimal


def round_price_by_tick_size(number, tick_size, floor_or_ceil=None):
    tick_size = Decimal(tick_size)
    number = Decimal(number)
    remainder = number % tick_size
    if remainder == 0:
        number = number
    if floor_or_ceil is None:
        floor_or_ceil = 'ceil' if (remainder >= tick_size / 2) else 'floor'
    if floor_or_ceil == 'ceil':
        number = number - remainder + tick_size
    else:
        number = number - remainder
    number_of_decimals = len(
        format(Decimal(repr(float(tick_size))), 'f').split('.')[1])
    number = round(number, number_of_decimals)
    return number


def get_position(size=0, entry_price=None, liquidation_price=None):
    return {
        'size': size,
        'entry_price': entry_price,
        'liquidation_price': liquidation_price
    }


def takePrice(elem):
    return Decimal(elem['limit_price'])


def takeFirst(elem):
    return elem[0]
