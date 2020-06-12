
import sys
import os
import itertools
import random
import collections
from decimal import Decimal

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import votelib.candidate


def check_validation(validator, cand, is_ok, error=votelib.candidate.CandidateError):
    if is_ok:
        validator.validate(cand)
    else:
        with pytest.raises(error):
            validator.validate(cand)

PS_SPOLU = votelib.candidate.Coalition([
    votelib.candidate.PoliticalParty('PS'),
    votelib.candidate.PoliticalParty('Spolu'),
])

@pytest.mark.parametrize(('cand', 'is_valid_norm'), [
    (votelib.candidate.NoneOfTheAbove('Nikdo'), True),
    (votelib.candidate.Person('Barack Obama'), True),
    (votelib.candidate.PoliticalParty('Greens'), False),
    (PS_SPOLU, False),
    ('Angela Merkel', False),
])
def test_person_nominator(cand, is_valid_norm):
    check_validation(
        votelib.candidate.PersonNominator(), cand, is_valid_norm
    )

DEMOCRAT_BARACK = votelib.candidate.Person(
    'Barack Obama',
    candidacy_for=votelib.candidate.PoliticalParty('Democrats')
)

@pytest.mark.parametrize(('cand', 'is_valid'), [
    (votelib.candidate.NoneOfTheAbove('Nikdo'), True),
    (DEMOCRAT_BARACK, True),
    (votelib.candidate.Person('Joe Nobody'), False),
])
def test_person_nominator_independent(cand, is_valid):
    check_validation(
        votelib.candidate.PersonNominator(allow_independents=False), cand, is_valid
    )
    
@pytest.mark.parametrize(('cand', 'is_valid'), [
    (votelib.candidate.NoneOfTheAbove('Nikdo'), False),
    (DEMOCRAT_BARACK, True),
    (votelib.candidate.Person('Joe Nobody'), True),
])
def test_person_nominator_blank(cand, is_valid):
    check_validation(
        votelib.candidate.PersonNominator(allow_blank=False), cand, is_valid
    )
    

@pytest.mark.parametrize(('cand', 'is_valid_norm'), [
    (votelib.candidate.NoneOfTheAbove('Žádná'), True),
    (votelib.candidate.Person('Barack Obama'), False),
    (votelib.candidate.PoliticalParty('Greens'), True),
    (PS_SPOLU, True),
    ('Angela Merkel', False),
])
def test_party_nominator(cand, is_valid_norm):
    check_validation(
        votelib.candidate.PartyNominator(), cand, is_valid_norm
    )

@pytest.mark.parametrize(('cand', 'is_valid'), [
    (votelib.candidate.NoneOfTheAbove('Nikdo'), False),
    (votelib.candidate.PoliticalParty('Greens'), True),
    (PS_SPOLU, True),
])
def test_party_nominator_blank(cand, is_valid):
    check_validation(
        votelib.candidate.PartyNominator(allow_blank=False), cand, is_valid
    )

@pytest.mark.parametrize(('cand', 'is_valid'), [
    (votelib.candidate.NoneOfTheAbove('Nikdo'), True),
    (votelib.candidate.PoliticalParty('Greens'), True),
    (PS_SPOLU, False),
])
def test_party_nominator_coalition(cand, is_valid):
    check_validation(
        votelib.candidate.PartyNominator(allow_coalitions=False), cand, is_valid
    )

def test_basic_nominator_blank():
    check_validation(
        votelib.candidate.BasicNominator(allow_blank=False),
        votelib.candidate.NoneOfTheAbove('Nikdo'), False
    )
