import sys
import os

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import votelib.coalition


@pytest.fixture
def cz_leg_2021_results():
    return {
        'ANO': 72,
        'SPOLU': 71,
        'PirSTAN': 37,
        'SPD': 20,
    }


@pytest.fixture
def cz_leg_2021_disallowed_links():
    return {'ANO': ['PirSTAN'], 'SPOLU': ['SPD'], 'PirSTAN': ['ANO', 'SPD'], 'SPD': ['PirSTAN']}


def test_minimal_feasible_coalitions_real(cz_leg_2021_results, cz_leg_2021_disallowed_links):
    coals = votelib.coalition.minimal_feasible_coalitions(
        cz_leg_2021_results,
        disallowed_links=cz_leg_2021_disallowed_links
    )
    assert set(coals.keys()) == {('SPOLU', 'PirSTAN'), ('ANO', 'SPOLU')}


def test_minimal_feasible_coalitions_constitution(cz_leg_2021_results):
    coals = list(votelib.coalition.minimal_feasible_coalitions(cz_leg_2021_results, min_seats=2/3))
    assert coals == [('ANO', 'SPOLU')]


def test_minimal_feasible_coalitions_large_margin(cz_leg_2021_results):
    coals = list(votelib.coalition.minimal_feasible_coalitions(cz_leg_2021_results, min_margin=20).keys())
    assert coals == [
        ('ANO', 'SPOLU'),
        ('ANO', 'PirSTAN', 'SPD'),
        ('SPOLU', 'PirSTAN', 'SPD'),
    ]
