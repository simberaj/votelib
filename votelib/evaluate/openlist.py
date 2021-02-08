'''Open party list selection evaluators.

Many party-list proportional systems feature open lists - that is, voters get
to cast preferential votes for the candidates on that list, and the order of
those candidates might then be altered by these preferences. These evaluators
serve to select the candidates from the party list that actually get one of the
seats allocated to it.

The evaluators in this module accept an extra argument to their ``evaluate()``
methods, namely the original ordering of the candidates on the party list. Many
methods only alter this ordering (allow *jumps*) if the lower candidates have
significantly more votes than those above them; almost all of them rely on this
ordering to break ties.

For the most common open list evaluation case, :class:`ThresholdOpenList`
(allowing jumps when the candidate gets at least a given fraction of the total
votes for the list or at least a quota of the votes based on the number of
seats) is provided.
:class:`ListOrderTieBreaker` provides a wrapper for any
selection evaluator and uses the list ordering to break ties.
'''


from typing import Any, List, Dict, Union, Callable
from numbers import Number
from fractions import Fraction

import votelib.util
import votelib.component.quota
import votelib.evaluate.core
from votelib.candidate import Candidate
from votelib.persist import simple_serialization


@simple_serialization
class ThresholdOpenList:
    '''A threshold-based open list evaluator.

    Allows candidates that got at least a given number of votes for the list as
    preferential votes to jump over all other candidates. These jumping
    candidates are selected first, ordered by their number of votes; the rest
    of the seats is filled by other candidates on the list in its
    original order.

    The number of votes required for the jump is determined relative
    to the total number of votes received by the list (``jump_fraction``)
    or to a quota computed from this total and the number of seats to award
    to the list (``quota_function`` and ``quota_fraction``).

    :param jump_fraction: The fraction of total votes for the list that the
        candidate must obtain to jump ahead in the rankings.
    :param quota_function: A callable producing the quota threshold (number
        of votes required to jump) from the
        total number of votes and number of seats. The common quota functions
        can be referenced by string name from the
        :mod:`votelib.component.quota` module. The Hare quota (``'hare'``)
        is used most frequently.
    :param quota_fraction: A number to multiply the calculated quota with, to
        allow e.g. all candidates that got at least half of the quota to jump.
    :param take_higher: If both the jump fraction and quota are specified,
        this determines whether to take the higher of the thresholds (amounting
        to an AND function) or the lower one (amounting to an OR function, the
        default).
    :param accept_equal: Whether to use non-strict comparison for the number
        of votes against the quota or jump fraction.
    :param list_precedence: Whether the original list ordering takes precedence
        when more candidates are allowed to jump than the number of seats.
        If True, the candidates lowest on the list are eliminated; if False,
        the candidates with the least votes are eliminated.
    '''
    def __init__(self,
                 jump_fraction: Fraction = None,
                 quota_function: Union[
                     str, Callable[[int, int], Number], None
                 ] = None,
                 quota_fraction: Fraction = 1,
                 take_higher: bool = False,
                 accept_equal: bool = False,
                 list_precedence: bool = False,
                 ):
        self.jump_fraction = jump_fraction
        self.quota_fraction = quota_fraction
        if quota_function is not None and quota_fraction != 1:
            wrapped = votelib.component.quota.construct(quota_function)

            def _quota_fractional(votes: int, seats: int) -> Fraction:
                return wrapped(votes, seats) * quota_fraction

            self.quota_function = _quota_fractional
        else:
            self.quota_function = quota_function
        self.take_higher = take_higher
        self.accept_equal = accept_equal
        self.list_precedence = list_precedence

    def evaluate(self,
                 votes: Dict[Candidate, Number],
                 n_seats: int,
                 candidate_list: List[Candidate],
                 ) -> List[Candidate]:
        '''Select candidates from an open party list.

        :param votes: Preferential votes (simple) for candidates on the list.
        :param n_seats: Number of seats to be awarded to the list - the number
            of candidates to elect.
        :param candidate_list: The original (party-determined) list ordering.
        '''
        jump_thresholds = []
        total_votes = sum(votes.values())
        if self.jump_fraction is not None:
            jump_thresholds.append(total_votes * self.jump_fraction)
        if self.quota_function is not None:
            jump_thresholds.append(self.quota_function(total_votes, n_seats))
        if not jump_thresholds:
            return candidate_list[:n_seats]
        else:
            # selects all over (or equaling) the threshold, sorted by votes
            threshold = (max if self.take_higher else min)(jump_thresholds)
            jumping = [
                cand for cand, n_votes in votelib.util.sorted_votes(votes)
                if n_votes > threshold or (
                    self.accept_equal and n_votes == threshold
                )
            ]
            if len(jumping) > n_seats:
                if self.list_precedence:
                    # list ordering takes precedence, eliminate those lowest
                    jumping.sort(key=candidate_list.index)
                    jumping = jumping[:n_seats]
                    jumping.sort(key=votes.get, reverse=True)
                    return jumping
                else:
                    return jumping[:n_seats]
            else:
                # if seats left, take the highest on the list not yet elected
                elected = jumping
                for list_i, cand in enumerate(candidate_list):
                    if len(elected) == n_seats:
                        break
                    if cand not in elected:
                        elected.append(cand)
                return elected


@simple_serialization
class ListOrderTieBreaker:
    '''A wrapper for any selector for open-list candidate selection.

    The candidates that the provided evaluator returns with the given votes are
    provided as the result of the open list. If there is a tie, it is
    broken by the ordering on the party list.

    :param evaluator: Any selection evaluator.
    '''
    def __init__(self, evaluator: votelib.evaluate.core.Selector):
        self.evaluator = evaluator

    def evaluate(self,
                 votes: Dict[Any, Number],
                 n_seats: int,
                 candidate_list: List[Candidate],
                 ) -> List[Candidate]:
        '''Select candidates from an open party list.

        :param votes: Preferential votes for candidates on the list. Must be
            of the type that is accepted by the underlying evaluator.
        :param n_seats: Number of seats to be awarded to the list - the number
            of candidates to elect.
        :param candidate_list: The original (party-determined) list ordering.
        '''
        inner_result = self.evaluator.evaluate(votes, n_seats)
        if votelib.evaluate.core.Tie.any(inner_result):
            return votelib.evaluate.core.Tie.break_by_list(
                inner_result, candidate_list
            )
        else:
            return inner_result
