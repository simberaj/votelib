
import sys
import os
import itertools

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.evaluate.condorcet
import votelib.convert
import votelib.evaluate.core
from votelib.evaluate.core import Tie


VOTES = {
    'schulze': {
        tuple('ACBED'): 5,
        tuple('ADECB'): 5,
        tuple('BEDAC'): 8,
        tuple('CABED'): 3,
        tuple('CAEBD'): 7,
        tuple('CBADE'): 2,
        tuple('DCEBA'): 7,
        tuple('EBADC'): 8,
    },
    'tennessee': {
        ('M', 'N', 'C', 'K'): 42,
        ('N', 'C', 'K', 'M'): 26,
        ('C', 'K', 'N', 'M'): 15,
        ('K', 'C', 'N', 'M'): 17,
    },
    'noncw1': {
        tuple('AECDB'): 31,
        tuple('BAE'): 30,
        tuple('CDB'): 29,
        tuple('DAE'): 10,
    },
    'noncw_minimax': {
        tuple('ACB'): 47,
        tuple('CBA'): 43,
        (frozenset(['A', 'C']), 'B'): 4,
        ('B', frozenset(['A', 'C'])): 6,
    },
    'noncw_minimax_2': {
        tuple('ACBD'): 30,
        tuple('DBAC'): 15,
        tuple('DBCA'): 14,
        tuple('BCAD'): 6,
        ('D', 'C', frozenset(['A', 'B'])): 4,
        ('C', frozenset(['A', 'B'])): 16,
        tuple('BC'): 14,
        tuple('CA'): 3,
    },
    'cw_wiki': {
        tuple('AB'): 186,
        tuple('AC'): 405,
        tuple('BA'): 305,
        tuple('BC'): 272,
        tuple('CA'): 78,
        tuple('CB'): 105,
    },
    'cw_wiki_mj': {
        tuple('ABC'): 35,
        tuple('CBA'): 34,
        tuple('BCA'): 31,
    },
    'cw_wiki_borda': {
        tuple('ABC'): 3,
        tuple('BCA'): 2,
    }
}

CONDORCET_WINNERS = {
    'tennessee': 'N',
    'noncw_minimax': 'A',
    'cw_wiki': 'B',
    'cw_wiki_mj': 'B',
    'cw_wiki_borda': 'A',
}

NONCONDORCET = ['minimax_pwo']

RESULTS = {
    'schulze': {
        'schulze': ['E', 'A', 'C', 'B', 'D']
    },
    'tennessee': {
        'copeland_raw': ['N', 'C', 'K', 'M'],
        'copeland_2o': ['N', 'C', 'K', 'M'],
        'rankedpairs_winvotes': ['N', 'C', 'K', 'M'],
        'kemeny_young': ['N', 'C', 'K', 'M'],
    },
    'noncw1': {
        'copeland_raw': ['A', Tie(['B', 'C', 'E']), Tie(['B', 'C', 'E']), Tie(['B', 'C', 'E']), 'D'],
        'copeland_2o': ['A', 'B', Tie(['C', 'E']), Tie(['C', 'E']), 'D'],
    },
    'noncw_minimax': {
        'minimax_pwo': ['C', 'A', 'B']
    },
    'noncw_minimax_2': {
        'minimax_winvotes': ['A', 'D', 'C', 'B'],
        'minimax_margins': ['B', 'C', 'D', 'A'],
        'minimax_pwo': ['D', 'A', 'C', 'B'],
    },
}

UNRANKED_AT_BOTTOM = {
    'noncw_minimax_2': False,
}


@pytest.mark.parametrize(('vote_set_name', 'eval_key', 'n_seats'), 
    itertools.product(VOTES.keys(), votelib.evaluate.condorcet.EVALUATORS.keys(), range(1, 4))
)
def test_condorcet_eval(vote_set_name, eval_key, n_seats):
    pair_votes = votelib.convert.RankedToCondorcetVotes(
        unranked_at_bottom=UNRANKED_AT_BOTTOM.get(vote_set_name, True)
    ).convert(VOTES[vote_set_name])
    all_cands = frozenset(cand for pair in pair_votes.keys() for cand in pair)
    elected = votelib.evaluate.condorcet.EVALUATORS[eval_key].evaluate(pair_votes, n_seats)
    wrapped = votelib.evaluate.core.FixedSeatCount(
        votelib.evaluate.condorcet.EVALUATORS[eval_key], n_seats
    )
    assert len(elected) == n_seats
    assert elected == wrapped.evaluate(pair_votes)
    for el in elected:
        if isinstance(el, Tie):
            assert el.issubset(all_cands)
        else:
            assert el in all_cands
    if vote_set_name in CONDORCET_WINNERS and eval_key not in NONCONDORCET:
        assert elected[0] == CONDORCET_WINNERS[vote_set_name]
    if vote_set_name in RESULTS:
        if eval_key in RESULTS[vote_set_name]:
            assert elected == RESULTS[vote_set_name][eval_key][:n_seats]


@pytest.mark.parametrize('vote_set_name', list(VOTES.keys()))
def test_condorcet_winner(vote_set_name):
    pair_votes = votelib.convert.RankedToCondorcetVotes(
        unranked_at_bottom=UNRANKED_AT_BOTTOM.get(vote_set_name, True)
    ).convert(VOTES[vote_set_name])
    result = votelib.evaluate.condorcet.CondorcetWinner().evaluate(pair_votes)
    if vote_set_name in CONDORCET_WINNERS:
        assert result == [CONDORCET_WINNERS[vote_set_name]]
    else:
        assert result == []
