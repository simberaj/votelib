'''Advanced approval voting methods.

This module contains approval voting evaluators that cannot be reduced to
a plurality evaluation by aggregating the scores. Use
:class:`votelib.convert.ApprovalToSimpleVotes` in conjunction with
:class:`votelib.evaluate.Plurality` to evaluate simple approval voting (AV)
or satisfaction approval voting (SAV).
'''

import itertools
import collections
from fractions import Fraction
from numbers import Number
from typing import List, FrozenSet, Dict, Union, Callable

import votelib.evaluate.core
import votelib.component.quota
from votelib.candidate import Candidate
from votelib.persist import simple_serialization


@simple_serialization
class ProportionalApproval:
    '''Proportional Approval Voting (PAV) evaluator. [#wpav]_

    This method uses approval votes (voters select one or more permissible
    candidates) and evaluates the satisfaction of voters with each of the
    combinations of elected candidates. The satisfaction for each voter is
    given as the sum of reciprocals from 1 to N, where N is the number of
    elected candidates that the voter approved of.

    WARNING: Due to the enumeration of all candidate set combinations, this
    method is highly computationally expensive (``O(n!)`` in the number of
    candidates) and infeasible on common machines for more than a handful of
    candidates.

    Tie breaking not implemented - the method itself does not provide a way
    to do it, a dedicated tie breaker will probably be necessary.

    .. [#wpav] "Proportional approval voting", Wikipedia.
        https://en.wikipedia.org/wiki/Proportional_approval_voting
    '''
    def __init__(self):
        self._coefs = [0]

    def evaluate(self,
                 votes: Dict[FrozenSet[Candidate], int],
                 n_seats: int,
                 ) -> List[Candidate]:
        '''Select candidates by proportional approval.

        :param votes: Approval votes.
        :param n_seats: Number of candidates to be elected.
        :returns: Selected candidates in decreasing order measured by
            drop in satisfaction when the given candidate is excluded from the
            selected set.
        '''
        if len(self._coefs) < n_seats:
            self._coefs += [
                sum(Fraction(1, k + 1) for k in range(n))
                for n in range(len(self._coefs), n_seats + 1)
            ]
        best_alts = self._get_best_alternatives(votes, n_seats)
        if len(best_alts) == 1:
            return self._order_by_score(frozenset(best_alts[0]), votes)
        else:
            raise NotImplementedError(f'tied PAV alternatives: {best_alts}')
            # common = best_alts[0].intersection(*best_alts[1:])
            # return Tie.reconcile(self._order_by_score(common) +

    def _order_by_score(self,
                        alternative: FrozenSet[Candidate],
                        votes: Dict[FrozenSet[Candidate], int],
                        ) -> List[Candidate]:
        '''Order the candidates within an alternative.

        To output a correctly sorted list, we need to extend the PAV algorithm
        to impose an ordering to the set. This is done by sorting in decreasing
        order measured by drop in satisfaction when the given candidate is
        excluded from the selected set.
        '''
        satisfaction_drops = {
            cand: -self._satisfaction(alternative - {cand}, votes)
            for cand in alternative
        }
        return votelib.evaluate.core.get_n_best(
            satisfaction_drops, len(alternative)
        )

    def _get_best_alternatives(self,
                               votes: Dict[FrozenSet[Candidate], int],
                               n_seats: int,
                               ) -> List[FrozenSet[Candidate]]:
        '''Get the selection alternative(s) with the highest satisfaction.'''
        all_candidates = frozenset(
            cand for alt in votes.keys() for cand in alt
        )
        best_alternatives = []
        best_score = -float('inf')
        # evaluate each alternative
        for alternative in itertools.combinations(all_candidates, n_seats):
            # compute total satisfaction
            satisfaction = self._satisfaction(frozenset(alternative), votes)
            if satisfaction > best_score:
                best_alternatives = [alternative]
                best_score = satisfaction
            elif satisfaction == best_score:
                best_alternatives.append(alternative)
        return best_alternatives

    def _satisfaction(self,
                      alternative: FrozenSet[Candidate],
                      votes: Dict[FrozenSet[Candidate], int],
                      ) -> float:
        return sum(
            self._coefs[len(alt & alternative)] * n_votes
            for alt, n_votes in votes.items()
        )


@simple_serialization
class SequentialProportionalApproval:
    '''Sequential Proportional Approval Voting (SPAV) evaluator. [#wspav]_

    This method uses approval votes (voters select one or more permissible
    candidates) but evaluates them iteratively, unlike proportional approval
    voting. In each iteration, the best candidate is selected and all ballots
    that approve of them are reduced in value to ``1/n``, where ``n`` is the
    number of the candidates on that ballot already elected plus one (the
    value of those votes thus decreases to a half after one of the marked
    candidates is elected, to a third if a second one is elected, and so on).

    Tie breaking not yet implemented.

    .. [#wspav] "Sequential proportional approval voting", Wikipedia.
        https://en.wikipedia.org/wiki/Sequential_proportional_approval_voting
    '''
    def evaluate(self,
                 votes: Dict[FrozenSet[Candidate], int],
                 n_seats: int,
                 ) -> List[Candidate]:
        '''Select candidates by sequential proportional approval.

        :param votes: Approval votes.
        :param n_seats: Number of candidates to be elected.
        :returns: Selected candidates ordered as they were selected in the
            successive iterations.
        '''
        elected = []
        while len(elected) < n_seats:
            round_votes = collections.defaultdict(int)
            for cand_set, n_votes in votes.items():
                n_elected_from_set = len(cand_set.intersection(elected))
                for cand in cand_set:
                    round_votes[cand] += Fraction(
                        n_votes, n_elected_from_set + 1
                    )
            for cand in elected:
                del round_votes[cand]
            choice = votelib.evaluate.core.get_n_best(round_votes, 1)
            if not choice:
                return elected
            best = choice[0]
            if isinstance(best, votelib.evaluate.core.Tie):
                raise NotImplementedError('tie breaking in SPAV')
            else:
                elected.append(best)
        return elected


@simple_serialization
class QuotaSelector:
    '''Quota threshold (plurality) selector.

    Elects candidates with more (or also equally many, depending on
    *accept_equal*) votes than the specified quota.
    This often gives fewer candidates than the number of seats, and thus
    usually needs to be accompanied by an another evaluation step. In very rare
    cases, it might select more candidates than the number of seats.

    This is a component in the following systems:

    -   *Two-round runoff* (usually with the Droop quota and a single seat)
        where it gives the first-round winner if they have a majority of votes,
        and no one otherwise.

    It can also serve as a threshold evaluator (eliminator) in proportional
    systems that restrict the first party seat from being a remainder seat,
    or a kickstart for Huntington-Hill related methods that are not defined
    for zero-seat parties.

    :param quota_function: A callable producing the quota threshold from the
        total number of votes and number of seats.
    :param accept_equal: Whether to elect candidates that only just reach the
        quota threshold (this is known to produce some instabilities).
    :param on_more_over_quota: How to handle the case when more candidates
        fulfill the quota that there is seats:

        -   ``'error'``: raise a
            :class:`votelib.evaluate.core.VotingSystemError`,
        -   ``'select'``: select the candidates with the most votes (possibly
            producing ties when they are equal).
    '''
    def __init__(self,
                 quota_function: Union[
                     str, Callable[[int, int], Number]
                 ] = 'droop',
                 accept_equal: bool = True,
                 on_more_over_quota: str = 'error',
                 ):
        self.quota_function = votelib.component.quota.construct(quota_function)
        self.accept_equal = accept_equal
        self.on_more_over_quota = on_more_over_quota

    def evaluate(self,
                 votes: Dict[Candidate, int],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        qval = self.quota_function(
            sum(votes.values()), n_seats
        )
        over_quota = {}
        unselected = set()
        for cand, n_votes in votes.items():
            if n_votes > qval or self.accept_equal and n_votes == qval:
                over_quota[cand] = n_votes
            else:
                unselected.add(cand)
        if len(over_quota) > n_seats:
            if self.on_more_over_quota == 'error':
                raise votelib.evaluate.core.VotingSystemError(
                    f'wanted {n_seats}, quota gave {len(over_quota)}'
                )
            elif self.on_more_over_quota != 'select':
                raise ValueError(
                    f'invalid more_over_quota setting: {self.more_over_quota}'
                )
        return votelib.evaluate.core.get_n_best(over_quota, n_seats)
