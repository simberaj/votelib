
import sys
import os
import itertools

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.component.transfer as tr

SAMPLE_ALLOC = {
    'A': {
        tuple('AB'): 5,
        tuple('AC'): 3,
        tuple('AD'): 2,
    },
    'B': {
        tuple('BA'): 2,
        tuple('BC'): 1,
        tuple('BD'): 5,
    },
    'C': {
        tuple('CA'): 2,
        tuple('CB'): 1,
        tuple('CD'): 3,
    },
    'D': {
        tuple('DA'): 1,
        tuple('DB'): 1,
        tuple('DC'): 1,
    },
}

TRANSFERERS = [
    tr.Hare(1711),
    tr.Gregory(),
]
