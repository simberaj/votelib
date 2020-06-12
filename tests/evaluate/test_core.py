
import sys
import os

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.evaluate.core

@pytest.mark.parametrize('abstract_cls', [
    votelib.evaluate.core.Evaluator,
    votelib.evaluate.core.Selector,
    votelib.evaluate.core.SeatlessSelector,
    votelib.evaluate.core.Distributor,
])
def test_abstract(abstract_cls):
    with pytest.raises(TypeError):
        eval = abstract_cls()

