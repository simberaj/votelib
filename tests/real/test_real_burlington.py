
import sys
import os

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.convert
import votelib.evaluate
import votelib.evaluate.condorcet
import votelib.evaluate.sequential

# Burlington 2009 mayoral election, a common point of discussion around non-FPTP method advocates.
# Data taken from https://rangevoting.org/Burlington.html

BURL_2009_VOTES = {
    ('Montroll', 'Kiss', 'Wright'): 1332,
    ('Montroll', 'Wright', 'Kiss'): 767,
    ('Montroll',): 455,
    ('Kiss', 'Montroll', 'Wright'): 2043,
    ('Kiss', 'Wright', 'Montroll'): 371,
    ('Kiss',): 568,
    ('Wright', 'Montroll', 'Kiss'): 1513,
    ('Wright', 'Kiss', 'Montroll'): 495,
    ('Wright',): 1289,
}

def test_burl_2009_plurality():
    fptp = votelib.evaluate.core.PreConverted(
        votelib.convert.RankedToSimpleVotes(),
        votelib.evaluate.Plurality()
    )
    assert fptp.evaluate(BURL_2009_VOTES, 1) == ['Wright']


def test_burl_2009_irv():
    irv = votelib.evaluate.sequential.TransferableVoteSelector(quota_function='droop')
    assert irv.evaluate(BURL_2009_VOTES, 1) == ['Kiss']


def test_burl_2009_bucklin():
    bucklin = votelib.evaluate.sequential.PreferenceAddition()
    assert bucklin.evaluate(BURL_2009_VOTES, 1) == ['Montroll']


@pytest.mark.parametrize('eval_name', list(votelib.evaluate.condorcet.EVALUATORS.keys()))
def test_burl_2009_condorcet(eval_name):
    e = votelib.evaluate.core.PreConverted(
        votelib.convert.RankedToCondorcetVotes(),
        votelib.evaluate.condorcet.EVALUATORS[eval_name],
    )
    assert e.evaluate(BURL_2009_VOTES, 1) == ['Montroll']
