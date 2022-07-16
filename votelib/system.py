from fractions import Fraction
from typing import Dict, Any, Optional

import votelib.convert
import votelib.evaluate
import votelib.component.rankscore
import votelib.evaluate.approval
import votelib.evaluate.cardinal
import votelib.evaluate.condorcet
import votelib.evaluate.proportional
import votelib.evaluate.sequential
from votelib.candidate import Candidate
from votelib.persist import simple_serialization    # noqa: F401
from votelib.vote import ApprovalVoteType, RankedVoteType, ScoreVoteType


@simple_serialization
class VotingSystem:
    """A named voting system. Wraps an election evaluator.

    :param name: Name of the system; usually mainly includes the body or
        position to be elected.
    :param evaluator: Evaluator representing the system. Can be combined with
        the validator and nominator by machinery in the :mod:`evaluate`
        subpackage.
    """
    def __init__(self, name: str, evaluator: votelib.evaluate.Evaluator):
        self.name = name
        self.evaluator = evaluator

    def evaluate(self, *args, **kwargs):
        """Return the evaluator's results of the system for the votes given."""
        return self.evaluator.evaluate(*args, **kwargs)


def _ranked_condorcet(condorcet_evaluator: votelib.evaluate.condorcet.Selector,
                      ) -> votelib.evaluate.Selector:
    return votelib.evaluate.core.PreConverted(
        converter=votelib.convert.RankedToCondorcetVotes(),
        evaluator=condorcet_evaluator,
    )


SIMPLE_SELECTION_SYSTEMS = {
    "plurality": VotingSystem('Plurality', votelib.evaluate.Plurality()),
}
SIMPLE_DISTRIBUTION_SYSTEMS = {
    "quota_hare": VotingSystem(
        'Hare Quota',
        votelib.evaluate.proportional.LargestRemainder(quota_function='hare')
    ),
    "quota_droop": VotingSystem(
        'Droop Quota',
        votelib.evaluate.proportional.LargestRemainder(quota_function='droop')
    ),
    "quota_hb": VotingSystem(
        'Hagenbach-Bischoff Quota',
        votelib.evaluate.proportional.LargestRemainder(quota_function='hagenbach_bischoff')
    ),
    "quota_imperiali": VotingSystem(
        'Imperiali Quota',
        votelib.evaluate.proportional.LargestRemainder(quota_function='imperiali')
    ),
    "d_hondt": VotingSystem(
        'D\'Hondt Divisor',
        votelib.evaluate.proportional.HighestAverages(divisor_function='d_hondt')
    ),
    "sainte_lague": VotingSystem(
        'Sainte-Lague Divisor',
        votelib.evaluate.proportional.HighestAverages(divisor_function='sainte_lague')
    ),
    "imperiali": VotingSystem(
        'Imperiali Divisor',
        votelib.evaluate.proportional.HighestAverages(divisor_function='imperiali')
    ),
}
APPROVAL_SELECTION_SYSTEMS = {
    "av": VotingSystem('Approval', votelib.evaluate.core.PreConverted(
        converter=votelib.convert.ApprovalToSimpleVotes(),
        evaluator=votelib.evaluate.Plurality(),
    )),
    "pav": VotingSystem('Proportional Approval', votelib.evaluate.approval.ProportionalApproval()),
    "spav": VotingSystem('Sequential Proportional Approval', votelib.evaluate.approval.SequentialProportionalApproval()),
    "sav": VotingSystem('Satisfaction Approval', votelib.evaluate.core.PreConverted(
        converter=votelib.convert.ApprovalToSimpleVotes(split=True),
        evaluator=votelib.evaluate.Plurality(),
    )),
}
RANKED_SELECTION_SYSTEMS = {
    "borda": VotingSystem('Borda', votelib.evaluate.PreConverted(
        converter=votelib.convert.RankedToPositionalVotes(rank_scorer=votelib.component.rankscore.Borda()),
        evaluator=votelib.evaluate.Plurality(),
    )),
    "ranked_pairs": VotingSystem('Ranked Pairs', _ranked_condorcet(votelib.evaluate.condorcet.RankedPairs())),
    "copeland": VotingSystem('Copeland', _ranked_condorcet(votelib.evaluate.condorcet.Copeland(second_order=False))),
    "copeland_2o": VotingSystem('Second order Copeland', _ranked_condorcet(votelib.evaluate.condorcet.Copeland())),
    "schulze": VotingSystem('Schulze', _ranked_condorcet(votelib.evaluate.condorcet.Schulze())),
    "kemeny_young": VotingSystem('Kemeny-Young', _ranked_condorcet(votelib.evaluate.condorcet.KemenyYoung())),
    "minimax": VotingSystem('Minimax', _ranked_condorcet(votelib.evaluate.condorcet.MinimaxCondorcet())),
    "stv_hare": VotingSystem('Hare STV', votelib.evaluate.sequential.TransferableVoteSelector(transferer='Hare')),
    "stv_gregory": VotingSystem('Gregory STV', votelib.evaluate.sequential.TransferableVoteSelector(transferer='Gregory')),
    "bucklin": VotingSystem('Bucklin', votelib.evaluate.sequential.PreferenceAddition()),
    "oklahoma": VotingSystem('Oklahoma', votelib.evaluate.sequential.PreferenceAddition(lambda ord: Fraction(1, ord+1))),
    "tideman_alt": VotingSystem('Tideman Alternative', votelib.evaluate.sequential.TidemanAlternative()),
    "benham": VotingSystem('Benham', votelib.evaluate.sequential.Benham()),
    "baldwin": VotingSystem('Baldwin', votelib.evaluate.sequential.Baldwin()),
    # "smith_stv": VotingSystem('Smith/STV', votelib.evaluate.Conditioned(
    #     eliminator=_ranked_condorcet(votelib.evaluate.condorcet.SmithSet()),
    #     evaluator=votelib.evaluate.sequential.TransferableVoteSelector(transferer='Gregory'),
    # )),
}
RANKED_DISTRIBUTION_SYSTEMS = {
    "stv_hare": VotingSystem('Hare STV', votelib.evaluate.sequential.TransferableVoteDistributor(transferer='Hare')),
    "stv_gregory": VotingSystem('Gregory STV', votelib.evaluate.sequential.TransferableVoteDistributor(transferer='Gregory')),
}
SCORE_SELECTION_SYSTEMS = {
    "score_mean": VotingSystem('Mean Score', votelib.evaluate.cardinal.ScoreVoting('mean')),
    "score_sum": VotingSystem('Sum Score', votelib.evaluate.cardinal.ScoreVoting('sum')),
    "score_median": VotingSystem('Median Score', votelib.evaluate.cardinal.ScoreVoting('median')),
    "mj": VotingSystem('Majority Judgment', votelib.evaluate.cardinal.MajorityJudgment()),
    "mjplus": VotingSystem('Majority Judgment Plus', votelib.evaluate.cardinal.MajorityJudgment(tie_breaking='plus')),
    "star": VotingSystem('STAR', votelib.evaluate.cardinal.STAR()),
    "allocated_score": VotingSystem('Allocated Score', votelib.evaluate.cardinal.AllocatedScoreSelector()),
}
SCORE_DISTRIBUTION_SYSTEMS = {
    "allocated_score": VotingSystem('Allocated Score', votelib.evaluate.cardinal.AllocatedScoreDistributor()),
}
SCORE_TO_RANKED_CONVERTERS = {
    None: votelib.convert.ScoreToRankedVotes(),
    "zero": votelib.convert.ScoreToRankedVotes(unscored_value=0),
}
SCORE_TO_SIMPLE_CONVERTERS = {
    None: votelib.convert.Chain([
        votelib.convert.ScoreToRankedVotes(),
        votelib.convert.RankedToFirstPreference()
    ]),
    "score": votelib.convert.ScoreToSimpleVotes(function="sum"),
}
RANKED_TO_APPROVAL_CONVERTERS = {
    None: votelib.convert.RankedToApprovalVotes(),
}
APPROVAL_TO_SIMPLE_CONVERTERS = {
    None: votelib.convert.ApprovalToSimpleVotes(),
    "split": votelib.convert.ApprovalToSimpleVotes(split=True),
}
RANKED_TO_SIMPLE_CONVERTERS = {
    None: votelib.convert.RankedToFirstPreference(),
}


def get_available_systems(vote_type: type,
                          is_distribution: bool = False,
                          ) -> Dict[str, VotingSystem]:
    if vote_type is Candidate:
        if is_distribution:
            return SIMPLE_DISTRIBUTION_SYSTEMS
        else:
            return SIMPLE_SELECTION_SYSTEMS
    elif vote_type is ApprovalVoteType:
        if is_distribution:
            return preconverted_systems(
                SIMPLE_DISTRIBUTION_SYSTEMS,
                APPROVAL_TO_SIMPLE_CONVERTERS
            )
        else:
            # not using plurality here since the default is directly AV and the split-converted is SAV
            return APPROVAL_SELECTION_SYSTEMS
    elif vote_type is RankedVoteType:
        if is_distribution:
            return {
                **RANKED_DISTRIBUTION_SYSTEMS,
                **preconverted_systems(SIMPLE_DISTRIBUTION_SYSTEMS, RANKED_TO_SIMPLE_CONVERTERS)
            }
        else:
            return {
                **RANKED_SELECTION_SYSTEMS,
                **preconverted_systems(APPROVAL_SELECTION_SYSTEMS, RANKED_TO_APPROVAL_CONVERTERS),
                **preconverted_systems(SIMPLE_SELECTION_SYSTEMS, RANKED_TO_SIMPLE_CONVERTERS),
            }
    elif vote_type is ScoreVoteType:
        if is_distribution:
            return {
                **SCORE_DISTRIBUTION_SYSTEMS,
                **preconverted_systems(RANKED_DISTRIBUTION_SYSTEMS, SCORE_TO_RANKED_CONVERTERS),
                **preconverted_systems(SIMPLE_DISTRIBUTION_SYSTEMS, SCORE_TO_SIMPLE_CONVERTERS),
            }
        else:
            return {
                **SCORE_SELECTION_SYSTEMS,
                **preconverted_systems(RANKED_SELECTION_SYSTEMS, SCORE_TO_RANKED_CONVERTERS),
                **preconverted_systems(SIMPLE_SELECTION_SYSTEMS, SCORE_TO_SIMPLE_CONVERTERS),
            }


def preconverted_systems(systems: Dict[str, VotingSystem],
                         converters: Dict[Optional[str], Any],
                         ) -> Dict[str, VotingSystem]:
    return {
        (f"{sys_key}_{conv_key}" if conv_key else sys_key): VotingSystem(
            name=(f"{sys.name} ({conv_key})" if conv_key else sys.name),
            evaluator=votelib.evaluate.PreConverted(
                converter=conv,
                evaluator=sys.evaluator
            )
        )
        for conv_key, conv in converters.items()
        for sys_key, sys in systems.items()
    }
