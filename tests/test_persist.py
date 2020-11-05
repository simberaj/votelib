
import sys
import os
import json
import decimal
import importlib

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import votelib
import votelib.convert
import votelib.evaluate
import votelib.evaluate.auxiliary
import votelib.evaluate.condorcet
import votelib.evaluate.core
import votelib.evaluate.proportional
import votelib.evaluate.sequential
import votelib.evaluate.threshold

sys.path.append(os.path.join(os.path.dirname(__file__)))
import test_score

sys.path.append(os.path.join(os.path.dirname(__file__), 'real'))
import test_real_listbased
import test_real_mmp
import test_real_proportional


CONDORCET_EVALUATORS = list(votelib.evaluate.condorcet.EVALUATORS.values())
SIMPLE_EVALUATORS = [
    votelib.evaluate.core.Conditioned(
        votelib.evaluate.threshold.RelativeThreshold(decimal.Decimal('.05')),
        votelib.evaluate.proportional.PureProportionality(),
    ),
    votelib.evaluate.Plurality(),
]
RANKED_EVALUATORS = [
    votelib.evaluate.core.PostConverted(
        votelib.evaluate.sequential.PreferenceAddition(),
        votelib.convert.SelectionToDistribution()
    ),
]
SCORE_EVALUATORS = [
    votelib.evaluate.core.PreConverted(
        votelib.convert.ScoreToRankedVotes(),
        votelib.evaluate.sequential.TransferableVoteSelector(
            quota_function='droop',
            retainer=votelib.evaluate.core.TieBreaking(
                votelib.evaluate.Plurality(),
                votelib.evaluate.auxiliary.InputOrderSelector(),
            )
        ),
    ),
] + list(test_score.EVALS.values())


@pytest.mark.parametrize('evaluator',
    SIMPLE_EVALUATORS
    + RANKED_EVALUATORS
    + SCORE_EVALUATORS
    + CONDORCET_EVALUATORS
    + test_real_listbased.get_evaluators()
    + test_real_mmp.get_evaluators()
    + test_real_proportional.get_evaluators()
)
def test_roundtrip(evaluator):
    dict_form = votelib.persist.to_dict(evaluator)
    serial = json.dumps(dict_form)
    print(serial)
    roundtrip_dict_form = votelib.persist.from_dict(json.loads(serial)).to_dict()
    roundtrip = json.dumps(roundtrip_dict_form)
    assert dict_form == roundtrip_dict_form
    assert serial == roundtrip


def test_score_equal():
    for ev in SCORE_EVALUATORS:
        roundtripped = votelib.persist.from_dict(
            json.loads(json.dumps(votelib.persist.to_dict(ev)))
        )
        print(ev, roundtripped)
        print(ev.to_dict())
        print(roundtripped.to_dict())
        for votes_name, votes in test_score.VOTES.items():
            assert ev.evaluate(votes, 1) == roundtripped.evaluate(votes, 1)
