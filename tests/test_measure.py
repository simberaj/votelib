import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import votelib.measure

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


def test_canada_gallagher():
    # taken from https://iscanadafair.ca/gallagher-index/
    assert abs(votelib.measure.gallagher(CANADA_2015_VOTES, CANADA_2015_SEATS) - .12) < .001

