
import sys
import os
from decimal import Decimal
from fractions import Fraction

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.evaluate
import votelib.evaluate.openlist

def test_open_list_elem():
    pref = votelib.evaluate.openlist.ThresholdOpenList(jump_fraction=Decimal('.05'))
    b_elects = pref.evaluate({1: 250, 2: 15, 3: 3, 4: 2, 5: 30}, 3, list(range(1, 6)))
    assert b_elects == [1, 5, 2]


def test_open_list_quota():
    pref = votelib.evaluate.openlist.ThresholdOpenList(quota_function='hare', quota_fraction=Fraction(1, 4))
    votes = {1: 3500, 2: 50, 3: 150, 4: 250, 5: 100, 6: 100, 7: 450, 8: 50}
    cand_list = list(range(1, 9))
    b_elects = pref.evaluate(votes, 5, cand_list)
    assert b_elects == [1, 7, 4, 2, 3]


@pytest.mark.parametrize(('is_list_pref', 'result'), [
    (True, [2, 1]), (False, [4, 3])
])
def test_open_list_quota_listpref(is_list_pref, result):
    pref = votelib.evaluate.openlist.ThresholdOpenList(
        quota_function='hare',
        quota_fraction=Fraction(1, 4),
        accept_equal=True,
        list_precedence=is_list_pref,
    )
    cand_list = list(range(1, 9))
    votes = dict(zip(cand_list, [200, 210, 220, 230, 10, 20, 30, 80]))
    b_elects = pref.evaluate(votes, 2, cand_list)
    assert b_elects == result


def test_open_list_wrapper():
    votes = {
        'A': 4, 'B': 3, 'C': 3, 'D': 2
    }
    party_list = list('ABCD')
    wrapped = votelib.evaluate.openlist.ListOrderTieBreaker(votelib.evaluate.Plurality())
    assert wrapped.evaluate(votes, 2, party_list) == ['A', 'B']
    assert wrapped.evaluate(votes, 2, list(reversed(party_list))) == ['A', 'C']