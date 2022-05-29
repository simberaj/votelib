
import sys
import os

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.evaluate.core
import votelib.evaluate.proportional

@pytest.mark.parametrize('abstract_cls', [
    votelib.evaluate.core.Evaluator,
    votelib.evaluate.core.Selector,
    votelib.evaluate.core.SeatlessSelector,
    votelib.evaluate.core.Distributor,
])
def test_abstract(abstract_cls):
    with pytest.raises(TypeError):
        eval = abstract_cls()


def test_level_overhang():
    lo = votelib.evaluate.core.LevelOverhang(
        votelib.evaluate.proportional.LargestRemainder('hare')
    )
    assert lo.calculate(
        votes={'A': 500, 'B': 300, 'C': 100},
        n_seats=9,
        prev_gains={'A': 1, 'B': 0, 'C': 2}
    ) == 4
