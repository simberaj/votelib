
import sys
import os
import itertools
from fractions import Fraction

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import votelib.evaluate
import votelib.evaluate.core
import votelib.convert
import votelib.component.rankscore

RANK_SCORERS = [
    votelib.component.rankscore.Borda(),
    votelib.component.rankscore.Borda(base=0),
    votelib.component.rankscore.Dowdall(),
]

BORDA_AGGS = [
    votelib.convert.RankedToPositionalVotes(rs)
    for rs in RANK_SCORERS
]

MAX_EVAL = votelib.evaluate.Plurality()

BORDA_EVALS = [
    votelib.evaluate.core.PreConverted(converter=agg, evaluator=MAX_EVAL)
    for agg in BORDA_AGGS
]

VOTES = [
    {
        ('M', 'N', 'C', 'K'): 42,
        ('N', 'C', 'K', 'M'): 26,
        ('C', 'K', 'N', 'M'): 15,
        ('K', 'C', 'N', 'M'): 17,
    },
    {
        ('A', 'C', 'B', 'D'): 51,
        ('C', 'B', 'D', 'A'): 5,
        ('B', 'C', 'D', 'A'): 23,
        ('D', 'C', 'B', 'A'): 21,
    },
]

AGG_RESULTS = [
    {'M': 226, 'N': 294, 'K': 207, 'C': 273},
    {'A': 253, 'B': 251, 'C': 305, 'D': 191},
    {'M': 126, 'N': 194, 'K': 107, 'C': 173},
    {'A': 153, 'B': 151, 'C': 205, 'D': 91},
    {'M': 56+Fraction(1, 2), 'N': 57+Fraction(2, 3), 'K': 43+Fraction(2, 3), 'C': 50+Fraction(1, 2)},
    {'A': 63+Fraction(1, 4), 'B': 49+Fraction(1, 2), 'C': 52+Fraction(1, 2), 'D': 43+Fraction(1, 12)},
]

@pytest.mark.parametrize(('agg', 'votes', 'results'), [
    agg_votes + (results,) for agg_votes, results in zip(
        itertools.product(BORDA_AGGS, VOTES), AGG_RESULTS
    )
])
def test_borda_aggreg(agg, votes, results):
    assert agg.convert(votes) == results


WINNERS = ['N', 'C', 'N', 'C', 'N', 'A']

@pytest.mark.parametrize(('agg', 'votes', 'winner'), [
    agg_votes + (winner,) for agg_votes, winner in zip(
        itertools.product(BORDA_AGGS, VOTES), WINNERS
    )
])
def test_borda_eval(agg, votes, winner):
    assert MAX_EVAL.evaluate(agg.convert(votes), 1) == [winner]


def test_borda_benham():
    votes = {
        ('A', 'B', 'C'): 46,
        ('B', 'C', 'A'): 44,
        ('C', 'A', 'B'): 5,
        ('C', 'B', 'A'): 5,
    }
    agg = votelib.convert.RankedToPositionalVotes(votelib.component.rankscore.Borda(base=0))
    agg_votes = agg.convert(votes)
    assert agg_votes == {'A': 97, 'B': 139, 'C': 64}


def test_chpv():
    # http://www.geometric-voting.org.uk/dsumary1.htm
    votes = {
        tuple('ADBC'): 1,
        tuple('ABCD'): 1,
        tuple('BACD'): 1,
        tuple('CBAD'): 1,
        tuple('CADB'): 1,
        tuple('DCBA'): 1,
        tuple('BADC'): 1,
        tuple('CDAB'): 1,
    }
    eval = votelib.evaluate.core.PreConverted(
        converter=votelib.convert.RankedToPositionalVotes(votelib.component.rankscore.Geometric(base=2)),
        evaluator=MAX_EVAL
    )
    assert eval.evaluate(votes, 1) == ['C']
    assert eval.evaluate(votes, 2) == ['C', 'A']

def test_chpv_vs_borda():
    # http://www.geometric-voting.org.uk/cborda1.htm
    votes = {
        tuple('ACDB'): 24,
        tuple('ADCB'): 4,
        tuple('BCDA'): 22,
        tuple('BDCA'): 4,
        tuple('CDAB'): 12,
        tuple('CDBA'): 12,
        tuple('DABC'): 11,
        tuple('DBAC'): 11,
    }
    assert votelib.evaluate.core.PreConverted(
        converter=votelib.convert.RankedToPositionalVotes(votelib.component.rankscore.Geometric(base=2)),
        evaluator=MAX_EVAL
    ).evaluate(votes, 1) == ['C']
    assert votelib.evaluate.core.PreConverted(
        converter=votelib.convert.RankedToPositionalVotes(votelib.component.rankscore.Borda()),
        evaluator=MAX_EVAL
    ).evaluate(votes, 1) == ['D']
