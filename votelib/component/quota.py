'''Quota functions used in largest-remainder proportional voting systems.

Quotas can however be used as a component in many other voting systems,
such as transferable vote or open list evaluators.

A quota function takes the total number of votes and the number of seats
to allocate and returns the number of votes required to reach a seat.
The unrounded quota functions return fractions to retain exact values.

All supported quota functions are assembled in the `QUOTAS` dictionary keyed
by their name. `get()` retrieves from this dictionary by string key;
`construct()` also accepts callables and passes them through.
'''

import math
from fractions import Fraction
from typing import Callable
from numbers import Number

import votelib.component.core


QUOTAS = {}


quota_mark, get, construct = votelib.component.core.register_functions(
    QUOTAS, 'quota', Callable[[int, int], Number]
)


@quota_mark
def hare(votes: int, seats: int) -> Fraction:
    '''Hare quota, the most basic one.

    This is the unrounded variant, giving the exact fraction.
    '''
    return Fraction(votes, seats)


@quota_mark
def hare_rounded(votes: int, seats: int) -> int:
    '''Hare quota, the most basic one.

    This is the rounded variant, which is used more often. Half is rounded up.
    '''
    return int(_round_half_up(Fraction(votes, seats)))


@quota_mark
def droop(votes: int, seats: int) -> int:
    '''Droop quota, the most widely used one.

    This it is the smallest integer quota guaranteeing the number of passing
    candidates will not be higher than the number of seats.
    '''
    return int(Fraction(votes, seats + 1)) + 1


@quota_mark
def hagenbach_bischoff(votes: int, seats: int) -> Fraction:
    '''Hagenbach-Bischoff quota.

    This is the unrounded variant, giving the exact fraction.
    '''
    return Fraction(votes, seats + 1)


@quota_mark
def hagenbach_bischoff_ceil(votes: int, seats: int) -> int:
    '''Hagenbach-Bischoff quota, rounding up.

    This is the rounded variant that is identical to the Droop quota in most
    cases.
    '''
    return int(math.ceil(Fraction(votes, seats + 1)))


@quota_mark
def hagenbach_bischoff_rounded(votes: int, seats: int) -> int:
    '''Hagenbach-Bischoff quota, rounding mathematically (round-to-even).

    This is the rounded variant that is used in some rare cases, e.g. old
    Slovak regional apportionment of parliamentary seats. Half is rounded up.
    '''
    return int(_round_half_up(Fraction(votes, seats + 1)))


@quota_mark
def imperiali(votes: int, seats: int) -> Fraction:
    '''Imperiali quota.

    Imperiali quota can produce more candidates than seats to be filled in some
    cases; the results then usually need to be recalculated using a different
    quota.
    '''
    return Fraction(votes, seats + 2)


def _round_half_up(var: Fraction) -> int:
    if var.limit_denominator(2) == var:
        # This concerns halves (rounding up) and integrals (no effect)
        return int(math.ceil(var))
    else:
        return int(round(var))


class constant:
    def __init__(self, quota: Number):
        self.quota = quota

    def __call__(self, votes: int, seats: int) -> Number:
        return self.quota
