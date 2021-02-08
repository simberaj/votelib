
import sys
import os
import itertools
import random
from decimal import Decimal

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.evaluate.auxiliary
from votelib.evaluate.core import Tie

RAND_VOTES = [
    {chr(65 + k): random.randint(0, 1000) for k in range(20)} for i in range(10)
]

STABLE_SORTITORS = [
    votelib.evaluate.auxiliary.RandomUnrankedBallotSelector(seed=1711),
    votelib.evaluate.auxiliary.Sortitor(seed=1711),
    votelib.evaluate.auxiliary.RFC3797Selector(sources=[1.25, [5, 3], 8]),
]

UNSTABLE_SORTITORS = [
    votelib.evaluate.auxiliary.RandomUnrankedBallotSelector(),
    votelib.evaluate.auxiliary.Sortitor(),
]

STABLE_SORTITOR_PARAMS = (('sortitor', 'votes', 'n_seats'), list(itertools.product(
    STABLE_SORTITORS, RAND_VOTES, range(1, 4)
)))

UNSTABLE_SORTITOR_PARAMS = (('sortitor', 'votes', 'n_seats'), list(itertools.product(
    UNSTABLE_SORTITORS, RAND_VOTES, range(1, 4)
)))

@pytest.mark.parametrize(*STABLE_SORTITOR_PARAMS)
def test_sortitor_stable(sortitor, votes, n_seats):
    elected_vars = _generate_variants(sortitor, votes, n_seats)
    assert len(elected_vars) == 1
    var = elected_vars.pop()
    assert len(var) == n_seats
    assert not any(isinstance(elected, Tie) for elected in var)


@pytest.mark.parametrize(*UNSTABLE_SORTITOR_PARAMS)
def test_sortitor_unstable(sortitor, votes, n_seats):
    elected_vars = _generate_variants(sortitor, votes, n_seats)
    assert len(elected_vars) > 1
    for var in elected_vars:
        assert len(var) == n_seats
        assert not any(isinstance(elected, Tie) for elected in var)


def _generate_variants(evaluator, votes, n_seats):
    elected_vars = set()
    for i in range(100):
        random.seed(None)
        elected_vars.add(tuple(evaluator.evaluate(votes, n_seats)))
    return elected_vars


def test_inporder():
    votes = {
        'A': 500,
        'B': 300,
        'C': 160,
    }
    eval = votelib.evaluate.auxiliary.InputOrderSelector()
    result = eval.evaluate(votes, 2)
    assert result == ['A', 'B']


@pytest.mark.parametrize('sources, result', [
    ([1.25, [5, 3], 8], b'1.25/3.5./8./'),
    (['Mažňák', Decimal('0.1'), [4, 6, 9]], b'MAZNAK/0.1/4.6.9./'),
])
def test_rfc3797_sourcecomp(sources, result):
    assert votelib.evaluate.auxiliary.RFC3797Selector.source_bytestring(sources) == result


def test_rfc3797_result():
    sel = votelib.evaluate.auxiliary.RFC3797Selector(['Mažňák', Decimal('0.1'), [4, 6, 9]])
    assert sel.evaluate(dict(zip('ABCDEFGHIJ', [1]*10)), 2) == ['J', 'H']


def test_rfc3797_origex():
    sel = votelib.evaluate.auxiliary.RFC3797Selector([
        9319,
        [2, 5, 12, 8, 10],
        [9, 18, 26, 34, 41, 45],
    ])
    assert sel.seed_bytes == b'9319./2.5.8.10.12./9.18.26.34.41.45./'
    assert sel.evaluate(dict(zip(range(1, 26), [1]*25)), 11) == [
        17, 7, 2, 16, 25, 23, 8, 24, 19, 13, 22
    ]
