"""Cardinal voting systems - systems that use score votes.

These systems have the most complicated input - each voter can assign a range
of scores to candidates - but are claimed to circumvent the Arrow's
impossibility theorem and Gibbard-Satterthwaite theorem (but not the more
general Gibbard's theorem) that only hold generally for ordinal (ranked) voting
systems.
"""
import collections
import logging
import math
from fractions import Fraction
from typing import Any, List, Dict, Union, Callable, Optional, Tuple
from numbers import Number

import votelib.convert
import votelib.persist
import votelib.util
import votelib.component.quota
import votelib.evaluate.core
import votelib.evaluate.condorcet
from votelib.candidate import Candidate
from votelib.vote import ScoreVoteType
from votelib.persist import simple_serialization


class ScoreVoting:
    """Evaluate ordinary score voting (range voting) systems.

    With the aggregation function set to sum, it also evaluates cumulative
    voting systems.

    This is essentially just a :class:`votelib.convert.ScoreToSimpleVotes`
    (to which all parameters are passed to) followed by a
    :class:`votelib.evaluate.core.Plurality` evaluator that selects the highest
    aggregate score.
    """
    def __init__(self,
                 function: Union[
                     Callable[[List[Number]], Number], str
                 ] = 'mean',
                 unscored_value: Union[
                     Callable[[List[Number]], Number], str, Number, None
                 ] = None,
                 min_count: int = 0,
                 truncation: Number = 0,
                 bottom_value: Number = 0,
                 ):
        self._agg = votelib.convert.ScoreToSimpleVotes(
            function=function,
            unscored_value=unscored_value,
            min_count=min_count,
            truncation=truncation,
            bottom_value=bottom_value,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self._agg.to_dict(),
            'class': votelib.persist.scoped_class_name(self)
        }

    def evaluate(self,
                 votes: Dict[ScoreVoteType, int],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        """Select candidates by highest score.

        :param votes: Score votes.
        :param n_seats: Number of candidates to select.
        """
        return votelib.evaluate.core.get_n_best(
            self._agg.convert(votes),
            n_seats
        )


class MajorityJudgment:
    """Majority Judgment, a median-based cardinal voting system.

    Parameters other than tie_breaking are passed to
    :class:`votelib.convert.ScoreToSimpleVotes`.

    Note: This evaluator does not return elected candidates in order of
    precedence (it does not resolve their exact ordering).

    :param tie_breaking: Method of breaking ties for candidates with equal
        median ranking. The `'default'` method (original by Balinski) removes
        median votes until a group of N winners has a higher ranking
        (known to be susceptible to electing candidates with consolidated bases
        rather than candidates with broad support),
        the `'plus'` method by Bosworth selects N candidates with the greatest
        number of scores equal or higher than the median (which claims to
        address the above shortcoming).
    :param unscored_value: Score to give to a candidate that was not assigned
        a score by the voter. None means such ballots will not be considered
        for the candidate. A function can be specified to determine the value
        from all assigned scores (such as assigning the minimum). Builtin
        functions and functions from the statistics stdlib module can be
        specified by their names.
    :param min_count: Minimum count of voter scores for the candidate to be
        considered. Candidates below this threshold will be assigned
        bottom_value.
    :param truncation: Fraction (if lower than 1) or count (if at least 1)
        of lowest and highest scores to disregard before aggregating, to
        stabilize the result. (Both ends are trimmed using this, so the
        number/fraction of scores disregarded is twice the count/fraction.)
    :param bottom_value: Value to assign to candidates with less voter scores
        than min_count. This would usually be the lowest possible aggregate
        score.
    """

    def __init__(self,
                 tie_breaking: str = 'default',
                 unscored_value: Union[
                     Callable[[List[Number]], Number], str, Number, None
                 ] = None,
                 min_count: int = 0,
                 truncation: Number = 0,
                 bottom_value: Number = 0,
                 ):
        self._agg = votelib.convert.ScoreToSimpleVotes(
            function='median_low',
            unscored_value=unscored_value,
            min_count=min_count,
            truncation=truncation,
            bottom_value=bottom_value,
        )
        self.tie_breaking = tie_breaking
        self.tie_breaker = getattr(self, '_tiebreak_' + tie_breaking)

    def to_dict(self) -> Dict[str, Any]:
        out = {
            'class': votelib.persist.scoped_class_name(self),
            'tie_breaking': self.tie_breaking,
        }
        for key, val in self._agg.to_dict().items():
            if key not in ('function', 'class'):
                out[key] = val
        return out

    def evaluate(self,
                 votes: Dict[Candidate, Dict[Number, int]],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        """Select candidates by Majority Judgment (appx. highest median score).

        :param votes: Score votes.
        :param n_seats: Number of candidates to select.
        """
        corrected_scores = self._agg.corrected_scores(votes)
        order = votelib.evaluate.core.get_n_best(
            self._agg.aggregate(corrected_scores),
            n_seats
        )
        if isinstance(order[-1], votelib.evaluate.core.Tie):
            n_tied_seats = order.count(order[-1])
            return order[:-n_tied_seats] + self.tie_breaker({
                cand: corrected_scores[cand] for cand in order[-1]
            }, n_tied_seats)
        else:
            return order

    def _tiebreak_default(self,
                          scores: Dict[Candidate, Dict[Any, int]],
                          n_seats: int,
                          ) -> List[Candidate]:
        """Perform Majority Judgment tiebreaking by removing median scores.

        This removes median scores from tied candidates until the median of the
        remaining scores differs among them, and then selects the one with the
        highest new median score.
        """
        scores = {cand: cscores.copy() for cand, cscores in scores.items()}
        while max(sum(cscores.values()) for cscores in scores.values()):
            medians = self._agg.aggregate(scores)
            best = votelib.evaluate.core.get_n_best(medians, n_seats)
            for i, result in enumerate(best):
                if isinstance(result, votelib.evaluate.core.Tie):
                    if i > 0:
                        winners = best[:i]
                        return winners + self._tiebreak_default({
                            cand: scores[cand] for cand in scores.keys()
                            if cand not in winners
                        }, n_seats - i)
                    else:
                        break
            else:
                return best
            closest_change = self._closest_median_change(scores, medians)
            if closest_change == 0:
                closest_change = 1
            for cand, cscores in scores.items():
                cscores[medians[cand]] -= closest_change
        raise votelib.evaluate.core.VotingSystemError(
            'cannot determine clear cutoff'
        )

    @staticmethod
    def _closest_median_change(scores: Dict[Candidate, Dict[Any, int]],
                               medians: Dict[Candidate, Any],
                               ) -> int:
        closest_change = float('inf')
        for cand, cscores in scores.items():
            lower, upper = 0, 0
            half = Fraction(sum(cscores.values()), 2)
            cur_median = medians[cand]
            for score, count in cscores.items():
                if score >= cur_median:
                    lower += count
                if score > cur_median:
                    upper += count
            cand_closest = int(min(
                math.ceil(abs(lower - half)),
                math.ceil(abs(upper - half))
            ))
            if cand_closest < closest_change:
                closest_change = cand_closest
        return closest_change

    def _tiebreak_plus(self,
                       scores: Dict[Candidate, Dict[Number, int]],
                       n_seats: int,
                       ) -> List[Candidate]:
        """Perform Majority Judgment Plus tiebreaking.

        This takes the candidates with the highest amount of scores higher or
        equal to the median, as suggested by Bosworth.
        """
        # select the one with largest majority with the largest median grade
        # so we need to find out the median grade again
        majorities = self._counts_over_score(
            scores, self._shared_median(scores), strict=False
        )
        return votelib.evaluate.core.get_n_best(majorities, n_seats)

    def _shared_median(self,
                       scores: Dict[Candidate, Dict[Number, int]]
                       ) -> Number:
        return self._agg.aggregate_one(next(iter(scores.values())))

    def _counts_over_score(self,
                           scores: Dict[Candidate, Dict[Number, int]],
                           threshold: Number,
                           strict: bool = False
                           ) -> Dict[Candidate, int]:
        return {
            cand: sum(
                count for score, count in cscores.items()
                if score > threshold or (not strict and score == threshold)
            ) for cand, cscores in scores.items()
        }


class STAR:
    """Score Then Automatic Run-Off (STAR) cardinal voting system.

    A score-based voting system that aims to reduce suceptibility to tactical
    voting by forcing a run-off between the highest-ranked candidates.

    STAR voting is normally specified for single-winner elections only, with
    two candidates in the run-off, but here it is extended:

    -   To enable multi-winner selections (n_seats more than 1), the run-off is
        performed using a selected Condorcet evaluator based on pairwise score
        preferences. This gives an identical result to simple plurality
        evaluation with only two candidates in the run-off, but also creates a
        robust result when there are more.
    -   Finer control over the run-off size is allowed; you can specify more
        than one extra candidate in the run-off, or specify the run-off size
        as a fraction of the number of seats to be filled.

    For single-winner elections, keep the runoff_added_* parameters at their
    defaults; then, the choice of runoff_evaluator does not matter because all
    Condorcet evaluators behave the same for two-candidate elections.

    :param runoff_added_count: Number of extra candidates in the run-off (added
        to the number of seats to be filled) as an absolute number.
    :param runoff_added_fraction: Number of extra candidates in the run-off
        (added to the number of seats to be filled) as a fraction of the number
        of seats to be filled.
    :param runoff_evaluator: Name of the Condorcet evaluator to use for the
        run-off (references `votelib.evaluate.condorcet.EVALUATORS`),
        or an instance of such a selector (must accept votes in pairwise win
        format).
    :param unscored_value: Score to give to a candidate that was not assigned
        a score by the voter. None means such ballots will not be considered
        for the candidate. A callable is not accepted.
    :param min_count: Minimum count of voter scores for the candidate to be
        considered. Candidates below this threshold will be assigned
        bottom_value.
    :param truncation: Fraction (if lower than 1) or count (if at least 1)
        of lowest and highest scores to disregard before aggregating, to
        stabilize the result. (Both ends are trimmed using this, so the
        number/fraction of scores disregarded is twice the count/fraction.)
    :param bottom_value: Value to assign to candidates with less voter scores
        than min_count. This would usually be the lowest possible aggregate
        score.
    """
    def __init__(self,
                 runoff_added_count: int = 1,
                 runoff_added_fraction: Number = 0,
                 runoff_evaluator: Union[
                     str,
                     votelib.evaluate.condorcet.Selector
                 ] = 'schulze',
                 unscored_value: Union[str, Number, None] = None,
                 min_count: int = 0,
                 truncation: Number = 0,
                 bottom_value: Number = 0,
                 ):
        if isinstance(runoff_evaluator, str):
            runoff_evaluator = votelib.evaluate.condorcet.EVALUATORS[
                runoff_evaluator
            ]
        self._agg = votelib.convert.ScoreToSimpleVotes(
            function='sum',
            unscored_value=unscored_value,
            min_count=min_count,
            truncation=truncation,
            bottom_value=bottom_value,
        )
        self._runoff_torank_conv = votelib.convert.ScoreToRankedVotes(
            unscored_value=unscored_value
        )
        self._runoff_tocond_conv = votelib.convert.RankedToCondorcetVotes()
        self.runoff_added_count = runoff_added_count
        self.runoff_added_fraction = runoff_added_fraction
        self.runoff_evaluator = runoff_evaluator

    def to_dict(self) -> Dict[str, Any]:
        out = {
            'class': votelib.persist.scoped_class_name(self),
            'runoff_added_count': self.runoff_added_count,
            'runoff_added_fraction': self.runoff_added_fraction,
            'runoff_evaluator': self.runoff_evaluator.to_dict(),
        }
        for key, val in self._agg.to_dict().items():
            if key not in ('function', 'class'):
                out[key] = val
        return out

    def evaluate(self,
                 votes: Dict[ScoreVoteType, int],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        """Select candidates by STAR voting.

        :param votes: Score votes.
        :param n_seats: Number of candidates to select.
        """
        # Aggregate scores to determine who goes to runoff.
        agg_scores = self._agg.convert(votes)
        runoff_size = (
            n_seats + self.runoff_added_count
            + int(math.ceil(self.runoff_added_fraction * n_seats))
        )
        runoff_members = votelib.evaluate.core.get_n_best(
            agg_scores, runoff_size
        )
        # Convert scores to pairwise wins for the runoff.
        pairwin_votes = {
            pair: n_votes
            for pair, n_votes in self._runoff_tocond_conv.convert(
                self._runoff_torank_conv.convert(votes)
            ).items()
            # Only preferences for runoff members.
            if all(cand in runoff_members for cand in pair)
        }
        return self.runoff_evaluator.evaluate(pairwin_votes, n_seats)


@simple_serialization
class AllocatedScoreDistributor:
    """Allocated Score, also known as Proportional STAR, as a distributor.

    Achieves proportional representation by allocating a seat to the candidate
    with the highest total score sum, then removing a quota fraction of their
    most important supporters from the consideration and repeating until all
    seats are filled.

    :param quota_function: A callable producing the quota threshold from the
        total number of votes and number of seats. The common quota functions
        can be referenced by string name from the
        :mod:`votelib.component.quota` module.
    """

    def __init__(self,
                 quota_function: Union[
                     str, Callable[[int, int], Number], None
                 ] = 'droop',
                 ):
        self.quota_function = votelib.component.quota.construct(
            quota_function
        )
        self._subsetter = votelib.convert.SubsettedVotes(
            vote_subsetter=votelib.vote.ScoreSubsetter()
        )

    def evaluate(self,
                 votes: Dict[ScoreVoteType, int],
                 n_seats: int = 1,
                 prev_gains: Dict[Candidate, int] = {},
                 max_seats: Dict[Candidate, int] = {},
                 ) -> Dict[Candidate, int]:
        """Select candidates by Allocated Score (Proportional STAR).

        :param votes: Score votes.
        :param n_seats: Number of seats to be filled.
        :param prev_gains: Seats gained by the candidate/party in previous
            election rounds to be subtracted from the proportional result
            awarded here.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total (including previous gains).
        """
        current_votes = votes.copy()
        elected = collections.defaultdict(int)
        rem_seats = n_seats
        quota = self.quota_function(sum(votes.values()), n_seats)
        while rem_seats > 0:
            agg_scores = self._sum_scores(current_votes)
            best = votelib.evaluate.core.get_n_best(agg_scores, 1)[0]
            if isinstance(best, votelib.evaluate.core.Tie):
                if rem_seats >= len(best):
                    logging.info("%s are tied best, electing all", best)
                    for cand in best:
                        elected[cand] += 1
                        current_votes = self._subtract_votes(
                            current_votes,
                            candidate=cand,
                            gained=elected[cand] + prev_gains.get(cand, 0),
                            max_seats=max_seats.get(cand),
                            subtract_size=quota,
                        )
                    rem_seats -= len(best)
                else:
                    logging.info("%s are tied best for %d seats",
                                 best, rem_seats)
                    elected[best] += rem_seats
                    rem_seats = 0
                    # we will terminate anyway, so no subtraction needed
            else:
                logging.info("%s is the best candidate, electing", best)
                elected[best] += 1
                rem_seats -= 1
                current_votes = self._subtract_votes(
                    current_votes,
                    candidate=best,
                    gained=elected[best] + prev_gains.get(best, 0),
                    max_seats=max_seats.get(best),
                    subtract_size=quota,
                )
        return elected

    @staticmethod
    def _sum_scores(current_votes: Dict[
                        ScoreVoteType,
                        Union[int, Fraction]
                    ],
                    ) -> Dict[Candidate, Union[int, Fraction]]:
        scores = collections.defaultdict(int)
        for vote, n_votes in current_votes.items():
            for candidate, score in vote:
                scores[candidate] += score * n_votes
        return dict(scores)

    def _subtract_votes(self,
                        current_votes: Dict[
                            ScoreVoteType,
                            Union[int, Fraction]
                        ],
                        candidate: Candidate,
                        gained: int,
                        max_seats: Optional[int],
                        subtract_size: Union[int, Fraction],
                        ) -> Dict[ScoreVoteType, Union[int, Fraction]]:
        logging.info("subtracting %g best votes from %s",
                     subtract_size, candidate)
        current_votes = self._fraction_out_elected(
            current_votes,
            cand=candidate,
            subtract_size=subtract_size,
        )
        if max_seats is not None and gained == max_seats:
            logging.info("%s reached maximum %d seats, eliminating",
                         candidate, gained)
            retain_cands = [
                cand
                for cand in votelib.util.all_scored_candidates(current_votes)
                if cand != candidate
            ]
            return self._subsetter.convert(
                current_votes,
                subset=retain_cands
            )
        else:
            return current_votes

    def _fraction_out_elected(self,
                              current_votes: Dict[
                                  ScoreVoteType,
                                  Union[int, Fraction]
                              ],
                              cand: Candidate,
                              subtract_size: Union[int, Fraction],
                              ) -> Dict[ScoreVoteType, Union[int, Fraction]]:
        while subtract_size > 0:
            best_votes, best_score = self._find_best_votes(current_votes, cand)
            current_size = sum(current_votes[vote] for vote in best_votes)
            if not current_size:
                # No more votes for candidate, return unchanged.
                logging.debug("no more votes for %s, terminating subtraction",
                              cand)
                return current_votes
            else:
                current_votes = current_votes.copy()
                if current_size > subtract_size:
                    # There are more votes than we need to remove;
                    # spread remove_size subtraction across them equally.
                    fraction = Fraction(
                        current_size - subtract_size,
                        current_size
                    )
                    logging.debug("cutting %g votes scoring %s at %s to %s",
                                  current_size, cand, best_score, fraction)
                    for vote in best_votes:
                        current_votes[vote] *= fraction
                    return current_votes
                else:
                    logging.debug("removing %g votes scoring %s at %s",
                                  current_size, cand, best_score)
                    # Remove all best_votes and run one more round.
                    for vote in best_votes:
                        del current_votes[vote]
                    subtract_size -= current_size
        return current_votes

    @staticmethod
    def _find_best_votes(current_votes: Dict[
                             ScoreVoteType,
                             Union[int, Fraction]
                         ],
                         cand: Candidate,
                         ) -> Tuple[List[ScoreVoteType], Any]:
        best_votes = []
        # Bootstrap with overall minimum score.
        best_score = min(
            min(score for cand, score in vote)
            for vote in current_votes
        )
        for vote in current_votes:
            for c, score in vote:
                if c == cand:
                    if score > best_score:
                        best_votes = [vote]
                        best_score = score
                    elif score == best_score:
                        best_votes.append(vote)
                    break
        return best_votes, best_score


class AllocatedScoreSelector:
    """Allocated Score, also known as Proportional STAR, as a selector.

    Elects the candidate with the highest score, then removes a quota fraction
    of their most important supporters from the consideration and repeats
    until all seats are filled.

    Uses :class:`AllocatedScoreDistributor` internally; see its definition
    for parameter documentation.
    """

    def __init__(self, *args, **kwargs):
        self._distributor = AllocatedScoreDistributor(*args, **kwargs)

    def evaluate(self,
                 votes: Dict[ScoreVoteType, int],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        cands = votelib.util.all_scored_candidates(votes)
        return list(self._distributor.evaluate(
            votes,
            n_seats=n_seats,
            max_seats={cand: 1 for cand in cands}
        ))
