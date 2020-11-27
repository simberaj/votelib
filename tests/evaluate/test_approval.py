
import sys
import os
from fractions import Fraction

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.evaluate.approval
import votelib.convert

def test_pav():
    # https://en.wikipedia.org/wiki/Proportional_approval_voting
    votes = {
        frozenset('AB'): 5,
        frozenset('AC'): 17,
        frozenset('D'): 8,
    }
    pav = votelib.evaluate.approval.ProportionalApproval()
    expect_winner = ['A', 'C']
    assert pav.evaluate(votes, 2) == expect_winner
    assert pav._satisfaction(frozenset(expect_winner), votes) == 30 + Fraction(1, 2)

def test_pav_tie():
    # https://en.wikipedia.org/wiki/Satisfaction_approval_voting
    votes = {
        frozenset('AB'): 4,
        frozenset('C'): 3,
        frozenset('D'): 3,
    }
    pav = votelib.evaluate.approval.ProportionalApproval()
    # expect_winner = ['A', 'C']
    with pytest.raises(NotImplementedError):
        pav.evaluate(votes, 2)


def test_sav():
    # https://en.wikipedia.org/wiki/Satisfaction_approval_voting
    votes = {
        frozenset('AB'): 4,
        frozenset('C'): 3,
        frozenset('D'): 3,
    }
    agg = votelib.convert.ApprovalToSimpleVotes(split=True)
    satisf = agg.convert(votes)
    assert satisf == {'A': 2, 'B': 2, 'C': 3, 'D': 3}
    eval = votelib.evaluate.Plurality()
    expect_winner = ['C', 'D']
    assert eval.evaluate(satisf, 2) == expect_winner

def test_spav():
    votes = {
        frozenset('A'): 2,
        frozenset('AB'): 5,
        frozenset('AC'): 3,
        frozenset('BC'): 2,
        frozenset('D'): 4,
    }
    spav = votelib.evaluate.approval.SequentialProportionalApproval()
    assert spav.evaluate(votes, 3) == list('ABD')

def test_quota_fail():
    votes = {'A': 100, 'B': 100, 'C': 100, 'D': 80}
    eval = votelib.evaluate.approval.QuotaSelector(quota_function='imperiali')
    with pytest.raises(votelib.evaluate.VotingSystemError):
        eval.evaluate(votes, 2)

def test_quota_select_tie():
    votes = {'A': 100, 'B': 100, 'C': 100, 'D': 80}
    ev = votelib.evaluate.approval.QuotaSelector(
        quota_function='imperiali',
        on_more_over_quota='select',
    )
    assert ev.evaluate(votes, 2) == [votelib.evaluate.core.Tie(['A', 'B', 'C'])] * 2
