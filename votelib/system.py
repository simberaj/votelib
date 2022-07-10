

from fractions import Fraction

import votelib.convert
import votelib.evaluate
import votelib.component.rankscore
import votelib.evaluate.approval
import votelib.evaluate.cardinal
import votelib.evaluate.condorcet
import votelib.evaluate.proportional
import votelib.evaluate.sequential
from votelib.persist import simple_serialization    # noqa: F401


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


SIMPLE_SELECTION_SYSTEMS = [
    VotingSystem('Plurality', votelib.evaluate.Plurality()),
]
SIMPLE_DISTRIBUTION_SYSTEMS = {
    VotingSystem('Hare Quota', votelib.evaluate.proportional.LargestRemainder(quota_function='hare')),
    VotingSystem('Droop Quota', votelib.evaluate.proportional.LargestRemainder(quota_function='droop')),
    VotingSystem('Imperiali Quota', votelib.evaluate.proportional.LargestRemainder(quota_function='imperiali')),
    VotingSystem('D\'Hondt Divisor', votelib.evaluate.proportional.HighestAverages(divisor_function='d_hondt')),
    VotingSystem('Sainte-Lague Divisor', votelib.evaluate.proportional.HighestAverages(divisor_function='sainte_lague')),
    VotingSystem('Imperiali Divisor', votelib.evaluate.proportional.HighestAverages(divisor_function='imperiali')),
}
APPROVAL_SELECTION_SYSTEMS = [
    VotingSystem('Approval', votelib.evaluate.core.PreConverted(
        converter=votelib.convert.ApprovalToSimpleVotes(),
        evaluator=votelib.evaluate.Plurality(),
    )),
    VotingSystem('PAV', votelib.evaluate.approval.ProportionalApproval()),
    VotingSystem('SPAV', votelib.evaluate.approval.SequentialProportionalApproval()),
]
RANKED_SELECTION_SYSTEMS = [
    VotingSystem('Borda', votelib.evaluate.PreConverted(
        converter=votelib.convert.RankedToPositionalVotes(rank_scorer=votelib.component.rankscore.Borda()),
        evaluator=votelib.evaluate.Plurality(),
    )),
    VotingSystem('Ranked Pairs', _ranked_condorcet(votelib.evaluate.condorcet.RankedPairs())),
    VotingSystem('Copeland', _ranked_condorcet(votelib.evaluate.condorcet.Copeland(second_order=False))),
    VotingSystem('Second order Copeland', _ranked_condorcet(votelib.evaluate.condorcet.Copeland())),
    VotingSystem('Schulze', _ranked_condorcet(votelib.evaluate.condorcet.Schulze())),
    VotingSystem('Kemeny-Young', _ranked_condorcet(votelib.evaluate.condorcet.KemenyYoung())),
    VotingSystem('Minimax', _ranked_condorcet(votelib.evaluate.condorcet.MinimaxCondorcet())),
    VotingSystem('Hare STV', votelib.evaluate.sequential.TransferableVoteSelector(transferer='Hare')),
    VotingSystem('Gregory STV', votelib.evaluate.sequential.TransferableVoteSelector(transferer='Gregory')),
    VotingSystem('Bucklin', votelib.evaluate.sequential.PreferenceAddition()),
    VotingSystem('Oklahoma', votelib.evaluate.sequential.PreferenceAddition(lambda ord: Fraction(1, ord))),
    VotingSystem('Tideman Alternative', votelib.evaluate.sequential.TidemanAlternative()),
    VotingSystem('Benham', votelib.evaluate.sequential.Benham()),
    VotingSystem('Baldwin', votelib.evaluate.sequential.Baldwin()),
    VotingSystem('Smith/IRV', votelib.evaluate.Conditioned(
        eliminator=_ranked_condorcet(votelib.evaluate.condorcet.SmithSet()),
        evaluator=votelib.evaluate.sequential.TransferableVoteSelector(transferer='Gregory'),
    )),
]
SCORE_SELECTION_SYSTEMS = [
    VotingSystem('Mean Score', votelib.evaluate.cardinal.ScoreVoting('mean')),
    VotingSystem('Sum Score', votelib.evaluate.cardinal.ScoreVoting('sum')),
    VotingSystem('Median Score', votelib.evaluate.cardinal.ScoreVoting('median')),
    VotingSystem('Majority Judgment', votelib.evaluate.cardinal.MajorityJudgment()),
    VotingSystem('Majority Judgment Plus', votelib.evaluate.cardinal.MajorityJudgment(tie_breaking='plus')),
    VotingSystem('STAR', votelib.evaluate.cardinal.STAR()),
    VotingSystem('Allocated Score', votelib.evaluate.cardinal.AllocatedScoreSelector()),
]
# TODO also use all downgraded systems via ScoreToRankedVotes,
#  RankedToApprovalVotes and RankedToFirstPreference

