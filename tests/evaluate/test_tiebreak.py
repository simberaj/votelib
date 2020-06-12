
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.evaluate.core
from votelib.evaluate.core import Tie
import votelib.evaluate.auxiliary
import votelib.evaluate.proportional


def test_simple():
    votes = {
        'A': 3,
        'B': 2,
        'C': 2,
        'D': 1,
    }
    main_eval = votelib.evaluate.core.Plurality()
    sortitor = votelib.evaluate.auxiliary.Sortitor()
    tb = votelib.evaluate.core.TieBreaking(main_eval, sortitor)
    assert main_eval.evaluate(votes, 2) == ['A', Tie(['B', 'C'])]
    assert tb.evaluate(votes, 2) in (['A', 'B'], ['A', 'C'])


def test_simple_prop():
    votes = {
        'A': 4,
        'B': 3,
        'C': 2,
    }
    main_eval = votelib.evaluate.proportional.HighestAverages()
    breaker = votelib.evaluate.core.Plurality()
    tb = votelib.evaluate.core.TieBreaking(main_eval, breaker)
    assert main_eval.evaluate(votes, 3) == {'A': 1, 'B': 1, Tie(['A', 'C']): 1}
    assert tb.evaluate(votes, 3) == {'A': 2, 'B': 1}
