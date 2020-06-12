
import sys
import os

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.evaluate
import votelib.evaluate.core
import votelib.evaluate.threshold


def test_alt_eval():
    class A:
        def evaluate(self, votes):
            return [chr(65 + i) for i in range(4)]
    class B:
        def evaluate(self, votes):
            return [chr(97 + i) for i in range(2)]
    alts = [A(), B()]
    alt = votelib.evaluate.threshold.AlternativeThresholds(alts)
    assert (
        frozenset(alt.evaluate({'a': 1, 'A': 2, 'B': 3, 'b': 4}))
        == frozenset(['A', 'B', 'C', 'a', 'D', 'b'])
    )
    
def test_quota_fail():
    votes = {'A': 100, 'B': 100, 'C': 100, 'D': 80}
    eval = votelib.evaluate.threshold.QuotaSelector(quota_function='imperiali')
    with pytest.raises(votelib.evaluate.VotingSystemError):
        eval.evaluate(votes, 2)

def test_fixed_seats():
    with pytest.raises(ValueError):
        eval = votelib.evaluate.core.FixedSeatCount(
            votelib.evaluate.threshold.RelativeThreshold(.05), 10
        )

def test_prop_bracketer():
    parties = [votelib.candidate.PoliticalParty(c) for c in 'ABCD']
    parties[2].ethnic_minority = True
    votes = dict(zip(parties, [200, 50, 50, 100]))
    thr = votelib.evaluate.threshold.AbsoluteThreshold(75)
    brack = votelib.evaluate.threshold.PropertyBracketer('ethnic_minority',
        {True: None}, default=thr
    )
    assert brack.evaluate(votes) == [parties[i] for i in (0, 3, 2)]
    assert thr.evaluate(votes) == [parties[i] for i in (0, 3)]
