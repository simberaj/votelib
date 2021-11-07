import sys
import os

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import votelib.crit.proportionality

CANADA_2015_VOTES = {
    'Liberal': 6943276,
    'Conservative': 5613614,
    'New Democratic': 3470350,
    'Bloc Québécois': 821144,
    'Green': 602944,
    'Other': 91837,
}

CANADA_2015_SEATS = {
    'Liberal': 184,
    'Conservative': 99,
    'New Democratic': 44,
    'Bloc Québécois': 10,
    'Green': 1,
}

EQUALS_VALUES = {
    'loosemore_hanby': 0,
    'rae': 0,
    'gallagher': 0,
    'regression': 1,
    'rose': 1,
    'sainte_lague': 0,
    'lijphart': 0,
    'd_hondt': 1,
}


@pytest.mark.parametrize('index_name', list(EQUALS_VALUES.keys()))
def test_perfect(index_name):
    equals = {'A': 7, 'B': 5, 'C': 3}
    index_fx = getattr(votelib.crit.proportionality, index_name)
    assert index_fx(equals, equals) == EQUALS_VALUES[index_name]


def test_canada_gallagher():
    # taken from https://iscanadafair.ca/gallagher-index/
    assert abs(votelib.crit.proportionality.gallagher(CANADA_2015_VOTES, CANADA_2015_SEATS) - .12) < .001


def test_rae_kalogirou_1():
    assert round(votelib.crit.proportionality.rae(
        {'A': 6996, 'B': 3004}, {'A': 53, 'B': 25, 'C': 22}
    ), 1) == 7.4


def test_lh_kalogirou_1():
    assert round(votelib.crit.proportionality.loosemore_hanby({'A': 68, 'B': 22}, {'A': 2}), 2) == .24


def test_lh_kalogirou_2():
    assert round(votelib.crit.proportionality.loosemore_hanby(
        {'A': 68, 'B': 22, 'C': 10},
        {'A': 1, 'B': 1}
    ), 2) == .28


def test_d_hondt_kalogirou_italy_1983():
    assert round(votelib.crit.proportionality.d_hondt(
        {'Other': 99924, 'dAosta': 76},
        {'Other': 99841, 'dAosta': 159}
    ), 3) == 2.092


def test_regression_largeparty_bias():
    assert votelib.crit.proportionality.regression(
        {'A': 7, 'B': 5, 'C': 3},
        {'A': 7, 'B': 5, 'C': 2}
    ) > 1


def test_regression_smallparty_bias():
    assert votelib.crit.proportionality.regression(
        {'A': 7, 'B': 5, 'C': 3},
        {'A': 7, 'B': 5, 'C': 4}
    ) < 1
