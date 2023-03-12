
import sys
import os
import csv
import collections

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.candidate
import votelib.component.transfer
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


@pytest.fixture(scope="module")
def dublin_north_leg_2002_data():
    inpath = os.path.join(os.path.dirname(__file__), "data", "dublin_north_leg_2002.csv")
    votes = collections.defaultdict(int)
    with open(inpath, encoding='utf8') as infile:
        reader = csv.DictReader(infile, delimiter=";")
        for vote_ordering in reader:
            int_ordering = {cand: int(order) for cand, order in vote_ordering.items() if order}
            vote = tuple(cand for cand in sorted(int_ordering, key=int_ordering.get))
            votes[vote] += 1
    return dict(votes)


def test_dublin_north_leg_2002(dublin_north_leg_2002_data):
    # https://www.electionsireland.org/result.cfm?election=2002&cons=96
    evaluator = votelib.evaluate.sequential.TransferableVoteSelector(
        quota_function='droop',
        transferer=votelib.component.transfer.Hare(seed=0),
    )
    elected = evaluator.evaluate(dublin_north_leg_2002_data, 4)
    first_two_expected = ['Sargent,Trevor,G.P.', 'Ryan,Seán,Lab']
    # In the Irish result, no further recount is performed when all candidates remaining after elimination would be
    # elected, which results in a different ordering (the transfer of votes of the final eliminated candidate
    # changes the order of the last two elected candidates).
    assert elected[:2] == first_two_expected
    assert frozenset(elected) == frozenset(first_two_expected + ['Glennon,Jim,F.F.', 'Wright,G.V.,F.F.'])
