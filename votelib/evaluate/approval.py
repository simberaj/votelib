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
from typing import List, FrozenSet, Dict

from ..candidate import Candidate
from . import core


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
        return core.get_n_best(satisfaction_drops, len(alternative))

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
            choice = core.get_n_best(round_votes, 1)
            if not choice:
                return elected
            best = choice[0]
            if isinstance(best, core.Tie):
                raise NotImplementedError('tie breaking in SPAV')
            else:
                elected.append(best)
        return elected
