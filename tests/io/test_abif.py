
import sys
import os
import io
import logging

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.io.abif


DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'abif')

eqr = frozenset

FILES_EXPECTED = {
    'test002': {
        (eqr(['Allie', 'Billy']), 'Candace', eqr(['Dennis', 'Edith']), 'Frank', 'Georgie', 'Harold'): 12,
        ('Georgie', 'Allie', eqr(['Dennis', 'Harold']), 'Candace', 'Edith', eqr(['Billy', 'Frank'])): 7,
        ('Frank', eqr(['Edith', 'Harold']), eqr(['Billy', 'Dennis', 'Georgie']), 'Candace', 'Allie'): 5,
    }
}

@pytest.mark.parametrize('filename, expected', list(FILES_EXPECTED.items()))
def test_files_output(filename, expected):
    with open(os.path.join(DATA_DIR, f'{filename}.abif'), 'r') as infile:
        result = votelib.io.abif.load(infile)
    assert result == expected
