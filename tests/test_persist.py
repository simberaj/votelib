
import sys
import os
import json
import decimal

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import votelib
import votelib.convert
import votelib.evaluate.condorcet
import votelib.evaluate.core
import votelib.evaluate.proportional
import votelib.evaluate.sequential
import votelib.evaluate.threshold


@pytest.mark.parametrize('evaluator', list(votelib.evaluate.condorcet.EVALUATORS.values()) + [
    votelib.evaluate.core.PreConverted(
        votelib.convert.ScoreToRankedVotes(),
        votelib.evaluate.sequential.TransferableVoteSelector(quota_function='droop'),
    ),
    votelib.evaluate.core.PostConverted(
        votelib.evaluate.sequential.PreferenceAddition(),
        votelib.convert.SelectionToDistribution()
    ),
    votelib.evaluate.core.Conditioned(
        votelib.evaluate.threshold.RelativeThreshold(decimal.Decimal('.05')),
        votelib.evaluate.proportional.PureProportionality(),
    ),
    # TODO add vote checkers and evaluators from the "real" tests folder
])
def test_roundtrip(evaluator):
    dict_form = votelib.persist.to_dict(evaluator)
    serial = json.dumps(dict_form)
    print(serial)
    roundtrip_dict_form = votelib.persist.from_dict(json.loads(serial)).to_dict()
    roundtrip = json.dumps(roundtrip_dict_form)
    assert dict_form == roundtrip_dict_form
    assert serial == roundtrip
