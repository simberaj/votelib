
import sys
import os
import itertools
import random

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
