
import sys
import os
import io

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.io.blt
import votelib.evaluate.sequential

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

STV_EVAL = votelib.evaluate.sequential.TransferableVoteSelector()


def test_custom_in():
    votes = {
        ('A', 'B'): 12.5,
        ('B', 'A'): 8.25,
    }
    n_seats = 1
    blt_text = votelib.io.blt.dumps(votes, n_seats)
    assert blt_text.strip() == '2 1\n12.5 1 2 0\n8.25 2 1 0\n0\n"A"\n"B"'


def test_incomplete_header():
    with pytest.raises(votelib.io.blt.BLTParseError):
        votelib.io.blt.loads('2')


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
    with pytest.raises(votelib.io.blt.BLTParseError) as excinfo:
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


def test_gnome_26():
    # https://vote.gnome.org/results.php?election_id=26
    with open(os.path.join(DATA_DIR, 'gnome_26.blt'), encoding='utf8') as infile:
        votes, n_seats, cands, name = votelib.io.blt.load(infile)
    assert set(cand.name for cand in STV_EVAL.evaluate(votes, n_seats)) == {
        'Allan Day', 'Carlos Soriano', 'Ekaterina Gerasimova',
        'Federico Mena Quintero', 'Nuritzi Sanchez', 'Philip Chimento',
        'Robert McQueen',
    }


def test_gnome_26_roundtrip():
    with open(os.path.join(DATA_DIR, 'gnome_26.blt'), encoding='utf8') as infile:
        blt_text = infile.read()
    loaded = votelib.io.blt.loads(blt_text)
    roundtripped = votelib.io.blt.dumps(*loaded)
    assert roundtripped.strip() == blt_text.strip()
    buffer = io.StringIO()
    roundtripped_fileobj = votelib.io.blt.dump(buffer, *loaded)
    assert buffer.getvalue().strip() == blt_text.strip()


def test_nocand():
    TEST_S = '''3 1
    -2
    4 2 1 3 0
    2 3 2 1 0

    1 2 3 0
    0
    '''
    votes, n_seats, cands, name = votelib.io.blt.loads(TEST_S)
    assert len(cands) == 3
    assert cands[1].withdrawn
    assert votes == {
        (cands[1], cands[0], cands[2]): 4,
        (cands[2], cands[1], cands[0]): 2,
        (cands[1], cands[2]): 1,
    }
    assert n_seats == 1
    assert name is None


def test_incomplete_body():
    TEST_S = '''3 1
    -2
    4 2 1 3 0
    '''
    with pytest.raises(votelib.io.blt.BLTParseError) as excinfo:
        votelib.io.blt.loads(TEST_S)
    assert 'incomplete' in str(excinfo.value)

def test_incomplete_row():
    TEST_S = '''3 1
    -2
    4 2 1 3
    0
    '''
    with pytest.raises(votelib.io.blt.BLTParseError) as excinfo:
        votelib.io.blt.loads(TEST_S)
    assert 'must be zero-terminated' in str(excinfo.value)

def test_incomplete_row():
    TEST_S = '''3 1
    -2
    4 2 1 3.5 0
    0
    '''
    with pytest.raises(votelib.io.blt.BLTParseError) as excinfo:
        votelib.io.blt.loads(TEST_S)

