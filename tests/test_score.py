
import sys
import os
import itertools
from fractions import Fraction

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import votelib.evaluate.cardinal

VOTES = dict(
    tennessee = {
        frozenset([('M', 10), ('N', 4), ('C', 2), ('K', 0)]): 42,
        frozenset([('M', 0), ('N', 10), ('C', 4), ('K', 2)]): 26,
        frozenset([('M', 0), ('N', 6), ('C', 10), ('K', 6)]): 15,
        frozenset([('M', 0), ('N', 5), ('C', 7), ('K', 10)]): 17,
    },
    tennessee_trunc = {
        frozenset([('M', 10), ('N', 4), ('C', 2)]): 42,
        frozenset([('N', 10), ('C', 4), ('K', 2)]): 26,
        frozenset([('N', 6), ('C', 10), ('K', 6)]): 15,
        frozenset([('N', 5), ('C', 7), ('K', 10)]): 17,
    },
    tennessee_mj = {
        frozenset([('M', 3), ('N', 1), ('C', 0), ('K', 0)]): 42,
        frozenset([('M', 0), ('N', 3), ('C', 1), ('K', 1)]): 26,
        frozenset([('M', 0), ('N', 1), ('C', 3), ('K', 2)]): 15,
        frozenset([('M', 0), ('N', 1), ('C', 2), ('K', 3)]): 17,
    },
    tennessee_star = {
        frozenset([('M', 5), ('N', 2), ('C', 1), ('K', 0)]): 42,
        frozenset([('M', 0), ('N', 5), ('C', 2), ('K', 2)]): 26,
        frozenset([('M', 0), ('N', 3), ('C', 5), ('K', 4)]): 15,
        frozenset([('M', 0), ('N', 2), ('C', 4), ('K', 5)]): 17,
    },
    mj = {
        frozenset([('EL', 6), ('L', 5), ('CL', 4), ('C', 3), ('CR', 2), ('R', 1), ('ER', 0)]): 101,
        frozenset([('EL', 5), ('L', 6), ('CL', 5), ('C', 4), ('CR', 3), ('R', 2), ('ER', 1)]): 101,
        frozenset([('EL', 4), ('L', 5), ('CL', 6), ('C', 5), ('CR', 4), ('R', 3), ('ER', 2)]): 101,
        frozenset([('EL', 3), ('L', 4), ('CL', 5), ('C', 6), ('CR', 5), ('R', 4), ('ER', 3)]): 50,
        frozenset([('EL', 2), ('L', 3), ('CL', 4), ('C', 5), ('CR', 6), ('R', 5), ('ER', 4)]): 99,
        frozenset([('EL', 1), ('L', 2), ('CL', 3), ('C', 4), ('CR', 5), ('R', 6), ('ER', 5)]): 99,
        frozenset([('EL', 0), ('L', 1), ('CL', 2), ('C', 3), ('CR', 4), ('R', 5), ('ER', 6)]): 99,
    },
)

EVALS = {
    'score': votelib.evaluate.cardinal.ScoreVoting(),
    'score_unsc0': votelib.evaluate.cardinal.ScoreVoting(unscored_value=0),
    'mj': votelib.evaluate.cardinal.MajorityJudgment(),
    'mjplus': votelib.evaluate.cardinal.MajorityJudgment(tie_breaking='plus'),
    'star': votelib.evaluate.cardinal.STAR(),
}

RESULTS = {
    'tennessee': {
        'score': ['N', 'C', 'M', 'K'],
    },
    'tennessee_trunc': {
        'score_unsc0': ['N', 'C', 'M', 'K'],
    },
    'tennessee_mj': {
        'mj': ['N', 'K', 'C', 'M'],
    },
    'tennessee_star': {
        'mj': ['N'],
    },
    'mj': {
        'mj': ['L'],
        'mjplus': ['CL'],
    },
}

@pytest.mark.parametrize(('vote_set_name', 'eval_key', 'n_seats'),
    itertools.product(VOTES.keys(), EVALS.keys(), range(1, 4))
)
def test_score_eval(vote_set_name, eval_key, n_seats):
    expected = None
    if vote_set_name in RESULTS:
        if eval_key in RESULTS[vote_set_name]:
            expected = frozenset(RESULTS[vote_set_name][eval_key][:n_seats])
    elected = EVALS[eval_key].evaluate(VOTES[vote_set_name], n_seats)
    assert len(elected) == n_seats
    if expected and n_seats == len(expected):
        assert frozenset(elected) == expected

FICT_SCORE_VOTES = {
    frozenset([('A', 0), ('B', 5)]): 3,
    frozenset([('A', 2), ('B', 3)]): 16,
    frozenset([('A', 3), ('B', 2)]): 19,
    frozenset([('A', 5), ('B', 0)]): 2,
}
FICT_EVAL_CLS = votelib.evaluate.cardinal.ScoreVoting

def test_score_trunc():
    assert FICT_EVAL_CLS(truncation=4).evaluate(FICT_SCORE_VOTES, 1) == ['A']
    assert (
        FICT_EVAL_CLS(truncation=Fraction(1, 10)).evaluate(FICT_SCORE_VOTES, 1)
        == FICT_EVAL_CLS(truncation=4).evaluate(FICT_SCORE_VOTES, 1)
    )
    assert FICT_EVAL_CLS(truncation=0).evaluate(FICT_SCORE_VOTES, 1) == ['B']


def test_score_bottom():
    lowvotes = FICT_SCORE_VOTES.copy()
    lowvotes[frozenset([('C', 5)])] = 1
    assert FICT_EVAL_CLS().evaluate(lowvotes, 1) == ['C']
    assert FICT_EVAL_CLS(min_count=10).evaluate(lowvotes, 1) == ['B']


def test_lomax_pizza():
    # https://rangevoting.org/MedianVrange.html
    votes = {
        frozenset([('Pepperoni', 9), ('Mushroom', 8)]): 2,
        frozenset([('Pepperoni', 0), ('Mushroom', 9)]): 1,
    }
    assert votelib.evaluate.cardinal.MajorityJudgment().evaluate(votes) == ['Pepperoni']
    assert votelib.evaluate.cardinal.ScoreVoting().evaluate(votes) == ['Mushroom']
