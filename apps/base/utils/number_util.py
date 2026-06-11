from decimal import Decimal, ROUND_HALF_UP


def decimalize(value: Decimal, precision: int = 6):
    fmt = f'1.{"0" * precision}'
    return value.quantize(Decimal(fmt), rounding=ROUND_HALF_UP)
