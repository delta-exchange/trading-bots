from decimal import Decimal
import operator
import numpy


def calculateMarginFromLiquidationPrice(position_size, entry_price, liquidation_price, maintenance_margin, isInverse=False):
    if isInverse:
        bankruptcy_price = liquidation_price * entry_price / \
            (entry_price + liquidation_price * numpy.sign(position_size)
             * maintenance_margin / Decimal(100))
        return -1 * position_size * (1/entry_price - 1/bankruptcy_price)
    else:
        bankruptcy_price = liquidation_price - \
            numpy.sign(position_size) * entry_price * \
            maintenance_margin / Decimal(100)
        return -1 * position_size * (bankruptcy_price - entry_price)


def funding_dampener(premium):
    return max(Decimal('0.05'), premium) + min(Decimal('-0.05'), premium)


def calculatePremiumFromFunding(funding):
    if funding > 0:
        return funding + Decimal('0.05')
    elif funding < 0:
        return funding - Decimal('0.05')
    else:
        return Decimal(0)
