'''Divisor functions used in highest-averages proportional voting systems.

This provides arguments for the
:class:`votelib.evaluate.proportional.HighestAverages` evaluator. However,
divisors can be used as a component in many other voting systems,
such as biproportional allocation.

A divisor function takes the order number (usually equal to the number of
seats allocated so far) and returns the divisor by which to divide the number
of votes for the given party or candidate. The party or candidate with the
largest result then gets the next seat.

Some systems use a mathematically defined divisor but artificially change the
result for parties with no seats so far (`order == 0`) to make it harder for
parties to get their seats. Use :func:`modified_first_coef` for that.

All supported divisor functions are assembled in the `DIVISORS` dictionary
keyed by their name. `get()` retrieves from this dictionary by string key;
`construct()` also accepts callables and passes them through.
'''

from fractions import Fraction
from decimal import Decimal
from typing import Callable
from numbers import Number

import votelib.component.core


DIVISORS = {}


divisor_mark, get, construct = votelib.component.core.register_functions(
    DIVISORS, 'divisor', Callable[[int], Number]
)


@divisor_mark
def d_hondt(order: int) -> int:
    '''D'Hondt divisor, the most commonly used divisor.

    Forms a simple sequence 1, 2, 3...
    In the United States, this is known as the Jefferson divisor that was used
    for congressional apportionment 1792-1842.

    Known to slightly favor larger parties.
    '''
    return order + 1


@divisor_mark
def sainte_lague(order: int) -> int:
    '''Sainte-Laguë (Webster, Schepers) divisor, a commonly used divisor.

    Forms a sequence 1, 3, 5...

    Known to favor mid-sized parties.
    '''
    return 2 * order + 1


@divisor_mark
def imperiali(order: int) -> Fraction:
    '''Imperiali divisor. Not to be confused with the Imperiali quota.

    Forms a sequence 1, 1.5, 2...

    Known to favor large parties greatly.
    '''
    return Fraction(order, 2) + 1


@divisor_mark
def huntington_hill(order: int) -> Decimal:
    '''Huntington-Hill divisor.

    The divisors are defined by `sqrt(n*(n+1))`. This means the
    divisor is invalid for the zeroth order (passing a zero gives
    a divisor of zero, which raises an error in the subsequent division)
    and can thus only be used in cases where the first seat is already
    guaranteed (use the `prev_gains` argument for that).

    Used for United States congressional apportionment as of 2020.
    '''
    return Decimal(order * (order + 1)).sqrt()


@divisor_mark
def danish(order: int) -> int:
    '''Danish divisor.

    Forms a sequence 1, 4, 7...

    Extremely favors smaller parties.
    '''
    return 3 * order + 1


@divisor_mark
def macau(order: int) -> int:
    '''Macau modified D'Hondt divisor.

    This uses order counts as exponents (1, 2, 4, 8...), and therefore favors
    smaller parties.
    '''
    return 2 ** order


def modified_first_coef(divisor_fx: Callable[[int], Number],
                        first_coef: Decimal = Decimal('1.4'),
                        ) -> Callable[[int], Number]:
    '''Modify the divisor for the zeroth order to an apriori coefficient.

    This can be used to raise the threshold for parties that have not yet
    obtained a seat. This is the case in the Czech regional election
    (Koudelka coefficient 1.42), Nepal, Norway, and Sweden.

    :param divisor_fx: The ordinary divisor function to be wrapped and used for
        the first order and subsequent ones.
    :param first_coef: The coefficient to be used when order == 0.
    '''
    if not isinstance(first_coef, (int, Fraction)):
        first_coef = Fraction(*first_coef.as_integer_ratio())
    def _modified_divisor(order: int) -> Number:
        return divisor_fx(order) if order > 0 else first_coef
    return _modified_divisor
