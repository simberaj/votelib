# coding: utf8

import sys
import os
import io
import logging

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.io.abif


DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'abif')

eqr = lambda *args: frozenset(args)

def nonascii_result(ye_name):
    return {
        ('Doña García Márquez', 'Steven B. Jensen', ye_name, 'Adam Muñoz'): 27,
        ('Steven B. Jensen', eqr('Doña García Márquez', ye_name), 'Adam Muñoz'): 26,
        (ye_name, eqr('Doña García Márquez', 'Adam Muñoz'), 'Steven B. Jensen'): 24,
        ('Adam Muñoz', ye_name, 'Doña García Márquez', 'Steven B. Jensen'): 23,
    }

FILES_EXPECTED = {
    'test001': {
        frozenset([('Allie', 5), ('Billy', 5), ('Candace', 4), ('Dennis', 3), ('Edith', 3), ('Frank', 2), ('Georgie', 1), ('Harold', 0)]): 12,
        frozenset([('Allie', 4), ('Billy', 0), ('Candace', 2), ('Dennis', 3), ('Edith', 1), ('Frank', 0), ('Georgie', 5), ('Harold', 3)]): 7,
        frozenset([('Allie', 0), ('Billy', 3), ('Candace', 2), ('Dennis', 3), ('Edith', 4), ('Frank', 5), ('Georgie', 3), ('Harold', 4)]): 5,
    },
    'test002': {
        (eqr('Allie', 'Billy'), 'Candace', eqr('Dennis', 'Edith'), 'Frank', 'Georgie', 'Harold'): 12,
        ('Georgie', 'Allie', eqr('Dennis', 'Harold'), 'Candace', 'Edith', eqr('Billy', 'Frank')): 7,
        ('Frank', eqr('Edith', 'Harold'), eqr('Billy', 'Dennis', 'Georgie'), 'Candace', 'Allie'): 5,
    },
    'test004': {
        frozenset([('Doña García Márquez', 5), ('Steven B. Jensen', 2), ('Sue Ye (蘇業)', 1), ('Adam Muñoz', 0)]): 27,
        frozenset([('Doña García Márquez', 3), ('Steven B. Jensen', 5), ('Sue Ye (蘇業)', 3), ('Adam Muñoz', 1)]): 26,
        frozenset([('Doña García Márquez', 2), ('Steven B. Jensen', 1), ('Sue Ye (蘇業)', 5), ('Adam Muñoz', 2)]): 24,
        frozenset([('Doña García Márquez', 1), ('Steven B. Jensen', 0), ('Sue Ye (蘇業)', 3), ('Adam Muñoz', 5)]): 23,
    },
    'test007': nonascii_result('Sue Ye (蘇業)'),
    'test008': nonascii_result('蘇業'),
}
FILES_EXPECTED['test003'] = FILES_EXPECTED['test001']
FILES_EXPECTED['test005'] = FILES_EXPECTED['test004']
FILES_EXPECTED['test006'] = FILES_EXPECTED['test004']
FILES_EXPECTED['test009'] = FILES_EXPECTED['test004']

FAILS = [
    ': A>B',    # missing ballot count number
    '0xab: A>B',    # invalid ballot count number
    'A>B \nA>B \nB>A',    # no ballot counts
    'some random text \n3: A>B=C>D',    # free hanging text
    '3: >B>C',    # does not start with candidate token
    '3: A>>C',    # missing candidate token
    '3: A>=C',    # missing candidate token
    '3: A$$>C',    # invalid candidate token
    '2: A > C, B, D',    # mixing commas and rankings in non-score vote
    '2: A, B > C = D',    # mixing commas and rankings in non-score vote
    '1: A/2, B, C, D',    # mixing score vote and other
    '1: A/2, B',    # mixing score vote and other
    '1: A, B/3, C/2, D',    # mixing score vote and other
    '1: A/1 B/3 C/2',    # score vote w/o separator
    '1: A B C',    # approval vote w/o separator
    '1: Á > Č = Ď',    # unbracketed non-ascii
    # TODO add candidate mapping parsing errors after that part of spec is stabilized
]


@pytest.mark.parametrize('filename, expected', list(FILES_EXPECTED.items()))
def test_files_output(filename, expected):
    with open(os.path.join(DATA_DIR, f'{filename}.abif'), 'r', encoding='utf8') as infile:
        result = votelib.io.abif.load(infile)
    assert result == expected


@pytest.mark.parametrize('expected', list(FILES_EXPECTED.values()))
def test_roundtrip(expected):
    roundtripped = votelib.io.abif.loads(votelib.io.abif.dumps(expected))
    assert roundtripped == expected


@pytest.mark.parametrize('abif', FAILS)
def test_fail(abif):
    with pytest.raises(votelib.io.abif.ABIFParseError):
        result = votelib.io.abif.loads(abif)
