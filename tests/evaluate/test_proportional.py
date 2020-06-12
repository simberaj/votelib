
import sys
import os
from fractions import Fraction

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.evaluate.core
import votelib.evaluate.proportional


def test_max_seats_highav():
    votes = {
        'A': 500,
        'B': 300,
        'C': 160,
    }
    max_seats = {p: 5 for p in votes.keys()}
    dhondt = votelib.evaluate.proportional.HighestAverages()
    dhondt_res = dhondt.evaluate(votes, 10, max_seats=max_seats)
    assert dhondt_res == {'A': 5, 'B': 3, 'C': 2}


def test_max_seats_highav_fix():
    votes = {
        'A': 500,
        'B': 300,
        'C': 160,
    }
    max_seats = {p: 5 for p in votes.keys()}
    dhondt = votelib.evaluate.proportional.HighestAverages()
    dhondt_wrap = votelib.evaluate.core.FixedSeatCount(dhondt, 10)
    dhondt_res = dhondt_wrap.evaluate(votes, max_seats=max_seats)
    assert dhondt_res == dhondt.evaluate(votes, 10, max_seats=max_seats)


def test_pureprop_withmax():
    votes = {
        'A': 500,
        'B': 300,
        'C': 160,
    }
    max_seats = {p: 5 for p in votes.keys()}
    eval = votelib.evaluate.proportional.PureProportionality()
    result = eval.evaluate(votes, 10, max_seats=max_seats)
    assert result == {'A': 5, 'B': 5 * Fraction(300, 460), 'C': 5 * Fraction(160, 460)}


def test_pureprop_withmin():
    votes = {
        'A': 500,
        'B': 300,
        'C': 160,
    }
    prev_gains = {'C': 2, 'A': 3, 'B': 1}
    eval = votelib.evaluate.proportional.PureProportionality()
    result = eval.evaluate(votes, 10, prev_gains=prev_gains)
    assert result == {'A': 2, 'B': 2, 'C': 0}


def test_max_seats_lrem():
    votes = {
        'A': 500,
        'B': 300,
        'C': 160,
    }
    max_seats = {p: 5 for p in votes.keys()}
    eval = votelib.evaluate.proportional.LargestRemainder('droop')
    result = eval.evaluate(votes, 10, max_seats=max_seats)
    assert result == {'A': 5, 'B': 3, 'C': 2}


def test_from_biprop_reg():
    votes = {
        'I': 1347,
        'II': 1014,
        'III': 1444,
    }
    slag = votelib.evaluate.proportional.HighestAverages('sainte_lague')
    assert slag.evaluate(votes, 20) == {'I': 7, 'II': 5, 'III': 8}

def test_from_biprop_party():
    votes = {
        'A': 983,
        'B': 2040,
        'C': 782,
    }
    slag = votelib.evaluate.proportional.HighestAverages('sainte_lague')
    assert slag.evaluate(votes, 20) == {'A': 5, 'B': 11, 'C': 4}
