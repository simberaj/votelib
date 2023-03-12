
import sys
import os
import itertools
import decimal
from fractions import Fraction
from decimal import Decimal

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import votelib.system
import votelib.evaluate.proportional


def test_votesys_transp():
    votes = {
        'A': 500,
        'B': 300,
        'C': 160,
    }
    max_seats = {p: 5 for p in votes.keys()}
    dhondt = votelib.evaluate.proportional.HighestAverages()
    votesys = votelib.system.VotingSystem('Tramtarie', dhondt)
    assert votesys.name == 'Tramtarie'
    assert dhondt.evaluate(votes, 10, max_seats=max_seats) == votesys.evaluate(votes, 10, max_seats=max_seats)
