
import sys
import os
import decimal
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


def test_votes_per_seat():
    votes = {
        'A': 983,
        'B': 2040,
        'C': 782,
    }
    vps = votelib.evaluate.proportional.VotesPerSeat(100)
    assert vps.evaluate(votes) == {'A': 9, 'B': 20, 'C': 7}

def test_votes_per_seat_round_math():
    votes = {
        'A': 983,
        'B': 2040,
        'C': 782,
        'D': 1050,
    }
    vps = votelib.evaluate.proportional.VotesPerSeat(100, rounding=decimal.ROUND_HALF_UP)
    assert vps.evaluate(votes) == {'A': 10, 'B': 20, 'C': 8, 'D': 11}


def test_biprop_custom():
    votes = \
        {'A': {'I': 123, 'II': 45, 'III': 815},
         'B': {'I': 912, 'II': 714, 'III': 414},
         'C': {'I': 312, 'II': 255, 'III': 15}}
    expected = \
        {'A': {'I': 1, 'III': 5},
         'B': {'I': 5, 'III': 2, 'II': 4},
         'C': {'I': 1, 'II': 2}}
    ev = votelib.evaluate.proportional.BiproportionalEvaluator('sainte_lague')
    assert ev.evaluate(votes, 20) == expected


def test_biprop_pukelsheim():
    votes_2 = {
        'A': {'1': 20, '2': 50, '3': 50},
        'B': {'1': 50, '2': 20, '3': 20},
        'C': {'1': 50, '2': 20, '3': 20},
    }
    ev = votelib.evaluate.proportional.BiproportionalEvaluator('sainte_lague')
    assert ev.evaluate(votes_2, 3) == {'A': {'3': 1}, 'B': {'1': 1}, 'C': {'2': 1}}


def test_biprop_zurich_2002():
    votes = {
        "1": {"SP": 3516, "SVP": 1709, "FDP": 2413, "Gre": 1080, "CVP": 639, "SenL": 247, "AL": 184},
        "2": {"SP": 4264, "SVP": 1806, "FDP": 1062, "Gre": 860,  "CVP": 539, "SenL": 339, "AL": 503},
        "3": {"SP": 3103, "SVP": 758,  "FDP": 566,  "Gre": 867,  "CVP": 467, "SenL": 137, "AL": 940},
        "4": {"SP": 3626, "SVP": 1349, "FDP": 1487, "Gre": 956,  "CVP": 471, "SenL": 359, "AL": 280},
        "5": {"SP": 4968, "SVP": 2423, "FDP": 4354, "Gre": 1939, "CVP": 968, "SenL": 485, "AL": 411},
        "6": {"SP": 3632, "SVP": 2724, "FDP": 1266, "Gre": 730,  "CVP": 946, "SenL": 482, "AL": 230},
        "7": {"SP": 4103, "SVP": 2135, "FDP": 2066, "Gre": 885,  "CVP": 647, "SenL": 446, "AL": 363},
        "8": {"SP": 4105, "SVP": 3333, "FDP": 1607, "Gre": 771,  "CVP": 949, "SenL": 636, "AL": 247},
        "9": {"SP": 1970, "SVP": 1516, "FDP": 486,  "Gre": 211,  "CVP": 446, "SenL": 344, "AL": 65},
    }
    seats = {
        "1": {"SP": 4, "SVP": 2, "FDP": 3, "Gre": 2, "CVP": 1},
        "2": {"SP": 6, "SVP": 3, "FDP": 2, "Gre": 2, "CVP": 1, "SenL": 1, "AL": 1},
        "3": {"SP": 6, "SVP": 1, "FDP": 1, "Gre": 2, "CVP": 1,            "AL": 2},
        "4": {"SP": 4, "SVP": 2, "FDP": 2, "Gre": 1, "CVP": 1},
        "5": {"SP": 5, "SVP": 2, "FDP": 5, "Gre": 2, "CVP": 1, "SenL": 1, "AL": 1},
        "6": {"SP": 6, "SVP": 5, "FDP": 2, "Gre": 1, "CVP": 1, "SenL": 1},
        "7": {"SP": 5, "SVP": 2, "FDP": 3, "Gre": 1, "CVP": 1},
        "8": {"SP": 7, "SVP": 5, "FDP": 3, "Gre": 1, "CVP": 1, "SenL": 1, "AL": 1},
        "9": {"SP": 4, "SVP": 3, "FDP": 1,           "CVP": 1, "SenL": 1},
    }
    ev = votelib.evaluate.proportional.BiproportionalEvaluator('sainte_lague')
    assert ev.evaluate(votes, dict(zip(
        [str(d) for d in range(1, 10)],
        [12, 16, 13, 10, 17, 16, 12, 19, 10],
    ))) == seats
