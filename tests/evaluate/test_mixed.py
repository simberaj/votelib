"""Tests for systems combining components from multiple modules."""

import sys
import os
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.convert
import votelib.vote
import votelib.evaluate.core
import votelib.evaluate.cardinal
import votelib.evaluate.condorcet
import votelib.evaluate.proportional


SMITH_SCORE = votelib.evaluate.core.Conditioned(
    evaluator=votelib.evaluate.cardinal.ScoreVoting(),
    eliminator=votelib.evaluate.core.PreConverted(
        converter=votelib.convert.Chain([
            votelib.convert.ScoreToRankedVotes(),
            votelib.convert.RankedToCondorcetVotes(),
        ]),
        evaluator=votelib.evaluate.condorcet.SmithSet(),
    ),
    subsetter=votelib.vote.ScoreSubsetter(),
)
SMITH_SCORE_VOTES = [
    (
        {
            frozenset([('A', 10), ('B', 9), ('C', 8)]): 17,
            frozenset([('B', 10), ('C', 9), ('A', 8)]): 17,
            frozenset([('C', 10), ('A', 9), ('B', 8)]): 18,
            frozenset([('D', 10), ('E', 10)]): 49,
        },
        ['C']
    ),
    (
        {
            frozenset([('A', 5), ('B', 4), ('C', 0)]): 35,
            frozenset([('B', 5), ('A', 4), ('C', 0)]): 25,
            frozenset([('C', 5), ('B', 0), ('A', 0)]): 40,
        },
        ['A']
    ),
    (
        {
            frozenset([('A', 5), ('B', 4), ('C', 0)]): 35,
            frozenset([('B', 5), ('A', 0), ('C', 1)]): 25,
            frozenset([('C', 5), ('B', 0), ('A', 0)]): 40,
        },
        ['B']
    ),
]


@pytest.mark.parametrize('votes, expected_winner', SMITH_SCORE_VOTES)
def test_smith_score(votes, expected_winner):
    winner = SMITH_SCORE.evaluate(votes, n_seats=1)
    assert winner == expected_winner


PROPORT_EVAL = votelib.evaluate.proportional.LargestRemainder(
    quota_function='hare'
)


@pytest.mark.parametrize("system, result", [
    (
        PROPORT_EVAL,
        {'A': 54, 'B': 34, 'C': 7, 'D': 5},
    ),
    (
        votelib.evaluate.core.AdjustedSeatCount(
            votelib.evaluate.core.AllowOverhang(PROPORT_EVAL),
            PROPORT_EVAL,
        ),
        {'A': 54, 'B': 41, 'C': 13, 'D': 5},
    ),
    (
        votelib.evaluate.core.AdjustedSeatCount(
            votelib.evaluate.core.LevelOverhang(PROPORT_EVAL),
            PROPORT_EVAL,
        ),
        {'A': 63, 'B': 60, 'C': 19, 'D': 5},
    )
])
def test_compensatory_systems(system, result):
    # https://en.wikipedia.org/wiki/Additional_member_system
    elect_res = {
        'A': 54,
        'B': 11,
        'C': 0,
        'D': 5,
    }
    party_vote = {
        'A': 43,
        'B': 41,
        'C': 13,
        'D': 3,
    }

    class MockEvaluator:
        def evaluate(self, *args, **kwargs):
            return elect_res

    total_evaluator = votelib.evaluate.core.MultistageDistributor([
        MockEvaluator(),
        system
    ])
    total_res = total_evaluator.evaluate(
        party_vote, 100
    )
    assert total_res == result
