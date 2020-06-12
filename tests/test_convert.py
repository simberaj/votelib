
import sys
import os
import itertools
import decimal
from fractions import Fraction
from decimal import Decimal

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import votelib.convert
import votelib.candidate
import votelib.vote


CANDIDATES = [
    votelib.candidate.Person('a', membership='A', candidacy_for='A'),
    votelib.candidate.Person('b', membership='B', candidacy_for='B'),
    votelib.candidate.Person('c', membership='C', candidacy_for='C'),
    votelib.candidate.Person('d', membership='D', candidacy_for='D'),
    votelib.candidate.Person('e', membership=None, candidacy_for='A'),
    votelib.candidate.Person('f', membership=None, candidacy_for='C'),
    votelib.candidate.Person('g', membership=None, candidacy_for=None),
    votelib.candidate.Person('h', membership=None, candidacy_for=None),
]


@pytest.mark.parametrize('affiliation, independents, results', [
    ('candidacy_for', 'aggregate', {'A': 2, 'B': 1, 'C': 2, 'D': 1, None: 2}),
    ('candidacy_for', 'keep', {
        'A': 2, 'B': 1, 'C': 2, 'D': 1,
        CANDIDATES[-2]: 1, CANDIDATES[-1]: 1
    }),
    ('candidacy_for', 'ignore', {'A': 2, 'B': 1, 'C': 2, 'D': 1}),
    ('candidacy_for', 'error', None),
    ('membership', 'aggregate', {'A': 1, 'B': 1, 'C': 1, 'D': 1, None: 4}),
    ('membership', 'keep', {
        'A': 1, 'B': 1, 'C': 1, 'D': 1,
        CANDIDATES[-4]: 1, CANDIDATES[-3]: 1, CANDIDATES[-2]: 1, CANDIDATES[-1]: 1
    }),
    ('membership', 'ignore', {'A': 1, 'B': 1, 'C': 1, 'D': 1}),
    ('membership', 'error', None),
])
def test_indiv_to_party(affiliation, independents, results):
    mapper = votelib.candidate.IndividualToPartyMapper(affiliation, independents)
    res_agg = votelib.convert.IndividualToPartyResult(mapper)
    vote_agg = votelib.convert.IndividualToPartyVotes(mapper)
    if results is None:
        with pytest.raises(votelib.candidate.CandidateError):
            res_agg.convert(CANDIDATES)
        with pytest.raises(votelib.candidate.CandidateError):
            vote_agg.convert({c: 1 for c in CANDIDATES})
    else:
        assert res_agg.convert(CANDIDATES) == results
        assert vote_agg.convert({c: 1 for c in CANDIDATES}) == results


def test_sel_merger():
    results = {'A': list('abc'), 'B': list('def')}
    expected = ['a', 'd', 'b', 'e', 'c', 'f']
    assert votelib.convert.MergedSelections().convert(results) == expected


def test_invalid_elim():
    validator = votelib.vote.RankedVoteValidator(
        total_vote_count_bounds=(1, 5),
        rank_vote_count_bounds=(1, 2),
    )
    is_valid, vote_list = zip(*[
        (False, tuple()),
        (True,  ('A',)),
        (True,  ('A', 'B')),
        (False, ('A', 'A')),
        (True,  ('C', 'D')),
        (True,  ('g', 'Hah', 'y')),
        (False, ('g', 'Hah', 'y', 'A', 'B', 'C')),
        (True,  (frozenset(['A', 'B']), 'Hah', 'y')),
        (True,  ('Hah', frozenset(['D', 'A']), 'y')),
        (False, ('A', frozenset(['D', 'A']), 'y')),
        (False, (frozenset(['D', 'A']), 'A', 'y')),
        (False, (frozenset(['A', 'B', 'C']), 'Hah', 'y')),
        (False, ('g', 'A', frozenset(['D', 'B', 'C']))),
        (False, (frozenset(['D', 'A']), 'B', 'y', frozenset(['C', 'Hah']))),
        (True,  (frozenset(['D', 'A']), 'B', frozenset(['C', 'Hah']))),
    ])
    votes = dict(zip(vote_list, range(3, len(vote_list)+3)))
    filtered = votelib.convert.InvalidVoteEliminator(validator).convert(votes)
    for vote, is_valid in zip(vote_list, is_valid):
        print(vote, is_valid)
        assert (vote in filtered) == is_valid


def test_rounding():
    votes = {
        'A': 2,
        'B': Fraction(5, 3),
        'C': 0.0001354679,
        'D': 0.00015,
    }
    rdr = votelib.convert.RoundedVotes(decimals=4, round_method=decimal.ROUND_HALF_DOWN)
    rd_votes = rdr.convert(votes)
    assert rd_votes == {
        'A': 2,
        'B': Decimal('1.6667'),
        'C': Decimal('.0001'),
        'D': Decimal('.0001')
    }

def test_rounding_negfail():
    with pytest.raises(ValueError):
        rdr = votelib.convert.RoundedVotes(decimals=-1)
