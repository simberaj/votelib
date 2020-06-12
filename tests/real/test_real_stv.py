
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.candidate
import votelib.evaluate.sequential


def test_ie_pres_1990():
    votes = {
        ('Mary Robinson',): 612265,
        ('Brian Lenihan',): 694484,
        ('Austin Currie', 'Brian Lenihan'): 36789,
        ('Austin Currie', 'Mary Robinson'): 205565,
        ('Austin Currie',): 25548,
    }
    evaluator = votelib.evaluate.sequential.TransferableVoteSelector(
        quota_function='droop',
        transferer='Hare'
    )
    assert evaluator.evaluate(votes) == ['Mary Robinson']
