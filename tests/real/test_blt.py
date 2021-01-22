
import sys
import os
import io
import logging

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.io.blt
import votelib.evaluate.sequential


DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


STV_EVAL = votelib.evaluate.sequential.TransferableVoteSelector()


def test_maemo_blt():
    with open(os.path.join(DATA_DIR, 'maemo.blt'), encoding='utf8') as infile:
        votes, n_seats, cands, name = votelib.io.blt.load(infile)
    assert name == 'Community Council Election Q1 2018'
    assert [cand.name for cand in cands] == [
        'mosen (Timo Könnecke)',
        'sicelo (Sicelo Mhlongo)',
        'juiceme (Jussi Ohenoja)',
        'm4r0v3r (Martin Ghosal)',
        'eekkelund (Eetu Kahelin)',
    ]
    assert not any(cand.withdrawn for cand in cands)
    assert n_seats == 3
    assert sum(
        n_votes for rvote, n_votes in votes.items()
        if rvote and rvote[0].name == 'juiceme (Jussi Ohenoja)'
    ) == 31


def test_rational_blt():
    with open(os.path.join(DATA_DIR, 'rational.blt'), encoding='utf8') as infile:
        votes, n_seats, cands, name = votelib.io.blt.load(infile)
    assert name == 'RationalMedia Board 2020 Election'
    assert [cand.name for cand in cands] == [
        'Dysk',
        'GrammarCommie',
        'LeftyGreenMario',
        'RoninMacbeth',
        'Other',
    ]
    assert not any(cand.withdrawn for cand in cands)
    assert n_seats == 4
    assert sum(
        n_votes for rvote, n_votes in votes.items()
        if rvote and rvote[0].name == 'GrammarCommie'
    ) == 0



def test_atwood_so_blt():
    with open(os.path.join(DATA_DIR, 'atwood_so.blt'), encoding='utf8') as infile:
        votes, n_seats, cands, name = votelib.io.blt.loads(infile.read())
    assert name == 'Gardening Club Election'
    assert [cand.name for cand in cands] == ['Amy', 'Bob', 'Chuck', 'Diane']
    assert all(cand.withdrawn == (cand.name == 'Bob') for cand in cands)
    assert n_seats == 2
    assert sum(
        n_votes for rvote, n_votes in votes.items()
        if rvote and rvote[0].name == 'Amy'
    ) == 3


def test_fail_empty():
    with pytest.raises(ValueError) as excinfo:
        votelib.io.blt.load(io.StringIO())
    assert 'empty' in str(excinfo.value)


def test_maemo():
    with open(os.path.join(DATA_DIR, 'maemo.blt'), encoding='utf8') as infile:
        votes, n_seats, cands, name = votelib.io.blt.load(infile)
    assert [cand.name for cand in STV_EVAL.evaluate(votes, n_seats)] == [
        'juiceme (Jussi Ohenoja)',
        'mosen (Timo Könnecke)',
        'eekkelund (Eetu Kahelin)'
    ]


def test_rational():
    with open(os.path.join(DATA_DIR, 'rational.blt'), encoding='utf8') as infile:
        votes, n_seats, cands, name = votelib.io.blt.load(infile)
    assert set(cand.name for cand in STV_EVAL.evaluate(votes, n_seats)) == {
        'LeftyGreenMario', 'Dysk', 'GrammarCommie', 'RoninMacbeth'
    }
