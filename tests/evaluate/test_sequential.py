
import sys
import os

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.evaluate.sequential
import votelib.evaluate.core
import votelib.evaluate.condorcet
from votelib.evaluate.core import Tie

DEFAULT_STV = votelib.evaluate.sequential.TransferableVoteSelector(
    quota_function='droop'
)

def test_food():
    # from wikipedia (https://en.wikipedia.org/wiki/Single_transferable_vote)
    votes = {
        ('Orange',): 4,
        ('Pear', 'Orange'): 2,
        ('Chocolate', 'Strawberry'): 8,
        ('Chocolate', 'Burger'): 4,
        ('Strawberry',): 1,
        ('Burger',): 1,
    }
    assert DEFAULT_STV.evaluate(votes, 3) == ['Chocolate', 'Orange', 'Strawberry']


def test_rv_stv():
    # https://rangevoting.org/STVPRunger
    votes = {
        tuple('ABCD'): 20,
        tuple('BDEF'): 20,
        tuple('FAC'): 20,
        tuple('DCEF'): 20,
        tuple('CDB'): 19,
    }
    result = DEFAULT_STV.evaluate(votes, 3)
    assert result[0] == 'D'
    assert set(result) == {'D', 'B', 'F'}


def test_rv_irv_nightmare_12():
    # https://rangevoting.org/rangeVirv.html#nightmare
    votes = {
        tuple('ABCDE'): 50,
        tuple('BACDE'): 51,
        tuple('CDBEA'): 100,
        tuple('DECBA'): 53,
        tuple('EDCBA'): 49,
    }
    assert DEFAULT_STV.evaluate(votes, 1) == ['D']


def test_rv_irv_revfail():
    votes = {
        tuple('BCA'): 9,
        tuple('ABC'): 8,
        tuple('CAB'): 7,
    }
    assert DEFAULT_STV.evaluate(votes, 1) == ['A']
    assert DEFAULT_STV.evaluate({tuple(reversed(vote)): n for vote, n in votes.items()}, 1) == ['A']


def test_bucklin_tennessee():
    votes = {
        ('M', 'N', 'C', 'K'): 42,
        ('N', 'C', 'K', 'M'): 26,
        ('C', 'K', 'N', 'M'): 15,
        ('K', 'C', 'N', 'M'): 17,
    }
    bucklin = votelib.evaluate.sequential.PreferenceAddition()
    assert bucklin.evaluate(votes, 1) == ['N']
    assert bucklin.evaluate(votes, 2) == ['N', 'C']


def test_stv_equalrank():
    # constructed by author
    votes = {
        ('A', frozenset(['B', 'C']), 'D'): 20,
        ('D', 'A', 'B', 'C'): 4,
    }
    for tr in ('Hare', 'Gregory'):
        eval = votelib.evaluate.sequential.TransferableVoteSelector(
            quota_function='droop', transferer=tr
        )
        result = eval.evaluate(votes, 3)
        assert set(result) == {'A', 'B', 'C'}
        assert result[0] == 'A'


def test_stv_equalrank_first():
    # constructed by author
    votes = {
        (frozenset(['B', 'C']), 'A', 'D'): 20,
        ('D', 'A', 'B', 'C'): 4,
    }
    for tr in ('Hare', 'Gregory'):
        eval = votelib.evaluate.sequential.TransferableVoteSelector(
            quota_function='droop', transferer=tr
        )
        result = eval.evaluate(votes, 3)
        assert set(result) == {'A', 'B', 'C'}
        assert set(result[:2]) == {'B', 'C'}


def test_bucklin_equalrank_split():
    # constructed by author
    votes = {
        ('A', frozenset(['B', 'C']), 'D'): 20,
        ('D', 'A', 'B', 'C'): 4,
    }
    eval = votelib.evaluate.sequential.PreferenceAddition()
    result = eval.evaluate(votes, 3)
    assert result == ['A', 'B', 'C']


def test_bucklin_equalrank_nosplit():
    # constructed by author
    votes = {
        ('A', frozenset(['B', 'C']), 'D'): 20,
        ('D', 'A', 'B', 'C'): 4,
    }
    eval = votelib.evaluate.sequential.PreferenceAddition(split_equal_rankings=False)
    result = eval.evaluate(votes, 3)
    assert result[0] == 'A'
    assert set(result[1:]) == {'B', 'C'}


def test_stv_distributor():
    votes = {
        ('A', 'B'): 65,
        ('C', 'A', 'B'): 15,
        ('B', 'A'): 28,
        ('C', 'B', 'A'): 12,
    }
    ev = votelib.evaluate.sequential.TransferableVoteDistributor()
    assert ev.evaluate(votes, 3) == {'A': 2, 'B': 1}


SCOTTISH_VOTES = {
    ('Adams', 'Baker'): 35,
    ('Adams', 'Gray', 'Baker'): 84,
    ('Adams', 'Gray', 'Miller'): 267,
    ('Adams', 'Gray'): 49,
    ('Adams', 'Miller'): 78,
    ('Adams',): 37,
    ('Baker',): 377,
    ('Campbell', 'Adams', 'Baker'): 7,
    ('Campbell', 'Adams', 'Gray', 'Baker'): 7,
    ('Campbell', 'Adams', 'Gray', 'Miller'): 19,
    ('Campbell', 'Adams', 'Gray'): 23,
    ('Campbell', 'Adams', 'Miller'): 263,
    ('Campbell', 'Adams'): 38,
    ('Campbell', 'Baker'): 223,
    ('Campbell', 'Gray', 'Baker'): 15,
    ('Campbell', 'Gray', 'Miller'): 58,
    ('Campbell', 'Gray'): 10,
    ('Campbell', 'Miller'): 252,
    ('Campbell',): 57,
    ('Gray', 'Baker'): 54,
    ('Gray', 'Miller'): 96,
    ('Gray',): 17,
    ('Miller',): 331,
}


def test_stv_scottish():
    # https://www2.gov.scot/Resource/0038/00389095.pdf
    # not using exact vote values due to unimplemented rounding rules
    stv = votelib.evaluate.sequential.TransferableVoteSelector(
        quota_function='droop', transferer='Gregory',
    )
    assert stv.quota_function(sum(SCOTTISH_VOTES.values()), 3) == 600
    assert DEFAULT_STV.evaluate(SCOTTISH_VOTES, 3) == ['Campbell', 'Adams', 'Miller']
    first_count_res, first_count_elect = DEFAULT_STV.nth_count(SCOTTISH_VOTES, 3, 1)
    assert first_count_res == {
        'Adams': 550,
        'Baker': 377,
        'Campbell': 972,
        'Gray': 167,
        'Miller': 331,
    }
    assert first_count_elect == ['Campbell']
    second_count_res, second_count_elect = DEFAULT_STV.nth_count(SCOTTISH_VOTES, 3, 2)
    assert {
        c: int(v) for c, v in second_count_res.items() if c is not None
    } == {
        'Adams': 686,
        'Baker': 462,
        'Gray': 198,
        'Miller': 427,
    }
    assert second_count_elect == ['Campbell', 'Adams']
    third_count_res, third_count_elect = DEFAULT_STV.nth_count(SCOTTISH_VOTES, 3, 3)
    assert third_count_elect == second_count_elect
    assert {
        c: int(v) for c, v in third_count_res.items() if c is not None
    } == {
        'Baker': 467,
        'Gray': 251,
        'Miller': 449,
    }
    fourth_count_res, fourth_count_elect = DEFAULT_STV.nth_count(SCOTTISH_VOTES, 3, 4)
    assert fourth_count_elect == ['Campbell', 'Adams', 'Miller']
    assert {
        c: int(v) for c, v in fourth_count_res.items() if c is not None
    } == {
        'Baker': 537,
        'Miller': 602,
    }


def test_top2_irv():
    eval = votelib.evaluate.sequential.TransferableVoteSelector(
        quota_function='droop',
        eliminate_step=2,
    )
    elim_votes, elim_elected = eval.nth_count(SCOTTISH_VOTES, 1, 2)
    assert set(elim_votes.keys()) == {'Adams', 'Campbell', None}
    assert elim_elected == []
    assert eval.evaluate(SCOTTISH_VOTES, 1) == ['Campbell']


def test_top2_irv_badretainer():
    eval = votelib.evaluate.sequential.TransferableVoteSelector(
        quota_function='droop',
        retainer=votelib.evaluate.core.FixedSeatCount(votelib.evaluate.Plurality(), 2)
    )
    with pytest.raises(votelib.evaluate.core.VotingSystemError):
        elim_votes, elim_elected = eval.nth_count(SCOTTISH_VOTES, 1, 2)


def test_noncw_irv():
    # https://en.wikipedia.org/wiki/Condorcet_criterion
    votes = {
        tuple('ABC'): 35,
        tuple('CBA'): 34,
        tuple('BCA'): 31,
    }
    assert DEFAULT_STV.evaluate(votes, 1) == ['C']


GA1_VOTES = {
    tuple('DABC'): 6,
    tuple('BCAD'): 5,
    tuple('CABD'): 4,
}
GA2_VOTES = {
    tuple('CDAB'): 6,
    tuple('BDAC'): 5,
    tuple('ABCD'): 4,
}
TIDALT = votelib.evaluate.sequential.TidemanAlternative()
SMITH_AV = votelib.evaluate.core.Conditioned(
    votelib.evaluate.core.PreConverted(
        votelib.convert.RankedToCondorcetVotes(),
        votelib.evaluate.condorcet.SmithSet()
    ),
    votelib.evaluate.sequential.TransferableVoteSelector(quota_function=None),
    subsetter=votelib.vote.RankedSubsetter(),
)
BENHAM = votelib.evaluate.sequential.Benham()


@pytest.mark.parametrize('ev, votes, expected', [
    (TIDALT, GA1_VOTES, 'A'),
    (SMITH_AV, GA1_VOTES, 'A'),
    (BENHAM, GA1_VOTES, 'B'),
    (TIDALT, GA2_VOTES, 'A'),
    (SMITH_AV, GA2_VOTES, 'B'),
    (BENHAM, GA2_VOTES, 'A'),
])
def test_ga(ev, votes, expected):
    # http://www.votingmatters.org.uk/ISSUE29/I29P1.pdf
    if votelib.evaluate.core.accepts_seats(ev):
        result = ev.evaluate(votes, 1)
    else:
        result = ev.evaluate(votes)
    assert result == [expected]


BALDWIN_VOTES = {
    tuple('ACB'): 5,
    tuple('BAC'): 4,
    tuple('CBA'): 2,
}


def test_baldwin_normal():
    # https://www.mail-archive.com/election-methods@lists.electorama.com/msg00625.html
    assert votelib.evaluate.sequential.Baldwin().evaluate(BALDWIN_VOTES) == ['B']


def test_baldwin_reversed():
    # dtto
    reversed_votes = {
        tuple(reversed(vote)): n_votes
        for vote, n_votes in BALDWIN_VOTES.items()
    }
    assert votelib.evaluate.sequential.Baldwin().evaluate(reversed_votes) == ['B']


TIED_BALDWIN_VOTES = {
    tuple('ACB'): 5,
    tuple('BAC'): 4,
    tuple('CBA'): 2,
    tuple('CB'): 1,
}


def test_baldwin_custom_tie_singlewinner():
    # constructed by author
    assert votelib.evaluate.sequential.Baldwin().evaluate(TIED_BALDWIN_VOTES) == ['A']


def test_baldwin_custom_tie_multiwinner():
    # constructed by author
    assert votelib.evaluate.sequential.Baldwin().evaluate(TIED_BALDWIN_VOTES, n_seats=2) == ['A', Tie(['B', 'C'])]
