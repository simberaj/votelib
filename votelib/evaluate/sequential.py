'''Evaluators that operate sequentially on ranked votes.

This hosts mainly the transferable vote evaluator
(:class:`TransferableVoteSelector`) but also its less known relative,
:class:`PreferenceAddition`.
'''

import itertools
import collections
from fractions import Fraction
from typing import List, Dict, Tuple, Union, Callable, Optional
from numbers import Number

from ..candidate import Candidate
from ..vote import RankedVoteType
from ..component import transfer, quota
from . import core
from .. import util


class TransferableVoteSelector:
    '''Select candidates by eliminating and transfering votes among them.

    This is the evaluator for transferable vote selection (since the evaluator
    does not concern itself with restrictions on allowed votes, it covers not
    only single transferable vote systems - STV -, but also potential multiple
    transferable vote systems). Its single-winner
    variant is also called instant-runoff voting (IRV).

    First, this evaluator looks at first-preference votes. If any of the
    candidates has at least a specified quota of votes, they are elected and
    their votes over the quota are redistributed according to their next stated
    preference. If no candidate has the quota, the candidate with the fewest
    currently allocated votes is eliminated and their votes transferred
    according to their next stated preference. Votes that have no further
    stated preferences are called exhausted and are removed from consideration.

    The current version does not use elimination breakpoints.

    :param transferer: An instance determining how much votes for eliminated
        candidates to transfer and to whom. It must provide the
        :class:`transfer.VoteTransferer` interface (experimental, stability
        not guaranteed). The basic vote transfer variants are implemented
        in the :mod:`transfer` module and can be referred to by their names.
    :param retainer: A selector determining which candidates to retain when
        elimination is to be performed (it may accept a number of seats, which
        will correspond to the number of candidates to retain). If not given,
        the candidates with the lowest amounts of votes will be eliminated.
    :param eliminate_step: Determines how many candidates to eliminate whenever
        elimination is to be performed. If a negative integer, determines how
        many candidates to eliminate at each step (the default eliminates one
        candidate at a time). If a positive integer, determines how many
        candidates to retain after elimination - this essentially allows only
        a single elimination and might cause an infinite loop if not used
        properly.
    :param quota_function: A callable producing the quota threshold from the
        total number of votes and number of seats. The common quota functions
        can be referenced by string name from the :mod:`quota` module. If not
        given, no election by quota takes place - the candidates are just
        eliminated until the desired number remains.
    :param accept_quota_equal: Whether to use non-strict comparison for the
        number of votes against the quota.
    '''
    def __init__(self,
                 transferer: Union[str, transfer.VoteTransferer] = 'Gregory',
                 retainer: Optional[core.Selector] = None,
                 eliminate_step: Optional[int] = -1,
                 quota_function: Union[
                     str, Callable[[int, int], Number], None
                 ] = None,
                 accept_quota_equal: bool = True,
                 # use_breakpoints: bool = True, - quota + applied
                 ):
        self.transferer = (
            getattr(transfer, transferer)() if isinstance(transferer, str)
            else transferer
        )
        if quota_function is not None:
            self.quota_function = quota.construct(quota_function)
        else:
            self.quota_function = None
        self.accept_quota_equal = accept_quota_equal
        self.retainer = retainer
        self.eliminate_step = eliminate_step

    def evaluate(self,
                 votes: Dict[RankedVoteType, Number],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        '''Select candidates by transferable vote.

        :param votes: Ranked votes. Equal rankings are allowed.
        :param n_seats: Number of candidates to select.
        '''
        return self.nth_count(votes, n_seats, 1000000000000)[1]

    def next_count(self,
                   allocation: Dict[Candidate, Dict[RankedVoteType, Number]],
                   quota: Number,
                   n_rem_seats: int,
                   ) -> Tuple[
                       Dict[Candidate, Dict[RankedVoteType, Number]],
                       List[Candidate]
                   ]:
        '''Advance the transferable voting process by one iteration (count).

        :param allocation: Current allocation of ranked votes to candidates
            still contesting the remaining seats.
        :param quota: Current value of the vote quota to elect a candidate.
        :param n_rem_seats: Number of seats not yet filled.
        :returns: A 2-tuple containing the new allocation of votes and a list
            of newly elected candidates (might be empty).
        '''
        totals = {
            cand: sum(cand_votes.values())
            for cand, cand_votes in allocation.items()
        }
        if len(totals) <= n_rem_seats:
            # all over count are eliminated, elect all remaining and end
            return {}, core.get_n_best(totals, len(totals))
        quota_elected = self._elect_by_quota(totals, quota, n_rem_seats)
        if quota_elected:
            return self.transferer.transfer(
                allocation,
                elected={cand: quota for cand in quota_elected},
            ), quota_elected
        else:
            # nobody elected by quota, we have to eliminate
            retained = self._select_retained(totals)
            newly_eliminated = [
                cand for cand in totals.keys()
                if cand not in retained
            ]
            return self.transferer.transfer(
                allocation, eliminated=newly_eliminated
            ), []

    def nth_count(self,
                  votes: Dict[RankedVoteType, Number],
                  n_seats: int = 1,
                  count_number: int = 1,
                  ) -> Tuple[
                      Dict[Candidate, Dict[RankedVoteType, Number]],
                      List[Candidate]
                  ]:
        '''Get the intermediate counting state at a given iteration (count).

        :param votes: Ranked votes. Equal rankings are allowed.
        :param n_seats: Number of candidates to select.
        :param count_number: 1-indexed count number.
        :returns: A 2-tuple containing the allocation of votes after the given
            count and a list of elected candidates so far (might be empty).
        '''
        allocation = self.first_preference_allocation(votes)
        new_allocation = None
        if self.quota_function:
            quota = self.quota_function(sum(votes.values()), n_seats)
        else:
            quota = float('inf')
        elected = []
        for count_i in range(count_number):
            if len(elected) >= n_seats:
                break
            if new_allocation is not None:
                allocation = new_allocation
            new_allocation, newly_elected = self.next_count(
                allocation, quota, n_seats - len(elected)
            )
            if not newly_elected and new_allocation == allocation:
                raise core.VotingSystemError('infinite loop in STV')
            elected += newly_elected
        return {
            cand: sum(cand_votes.values())
            for cand, cand_votes in allocation.items()
        }, elected[:n_seats]

    def _select_retained(self,
                         totals: Dict[Candidate, Number]
                         ) -> List[Candidate]:
        if self.retainer:
            if core.accepts_seats(self.retainer):
                n_seats = self._retained_count(totals)
                retained = self.retainer.evaluate(totals, n_seats)
            else:
                retained = self.retainer.evaluate(totals)
        else:
            retained = core.get_n_best(totals, self._retained_count(totals))
        if any(isinstance(e, core.Tie) for e in retained):
            raise NotImplementedError('tie in STV elimination')
        return retained

    def _retained_count(self, totals: Dict[Candidate, Number]) -> int:
        if self.eliminate_step is None:
            raise ValueError('need to specify eliminate step'
                             ' without standalone retainer')
        if self.eliminate_step < 0:
            return max(len(totals) + self.eliminate_step, 1)
        else:
            return min(self.eliminate_step, len(totals) - 1)

    def _elect_by_quota(self,
                        totals: Dict[Candidate, Number],
                        quota: Number,
                        n_rem_seats: int,
                        ) -> List[Candidate]:
        fill_quota = {
            cand: total for cand, total in totals.items()
            if total > quota or self.accept_quota_equal and total == quota
        }
        if fill_quota:
            if len(fill_quota) > n_rem_seats:
                new_elected = core.get_n_best(fill_quota, n_rem_seats)
                if any(isinstance(e, core.Tie) for e in new_elected):
                    raise NotImplementedError('tie in STV quota election')
            else:
                new_elected = core.get_n_best(fill_quota, len(fill_quota))
        else:
            new_elected = []
        return new_elected

    def first_preference_allocation(self,
                                    votes: Dict[RankedVoteType, int],
                                    ) -> Dict[
                                        Candidate, Dict[RankedVoteType, Number]
                                    ]:
        '''Allocate votes by first preference.

        Performed at the beginning of the first count.

        :param votes: Ranked votes.
        :returns: The votes dictionary separated into subdictionaries keyed by
            candidate to whom the votes are allocated.
        '''
        first_prefs = {
            cand: {} for cand in util.all_ranked_candidates(votes)
        }
        for vote, n_votes in votes.items():
            first_pref = vote[0]
            if isinstance(first_pref, collections.abc.Set):
                # shared rank
                # we pass this to transferer - we prepend a fictional
                # eliminated candidate to this vote and have it transferred
                first_prefs.setdefault(None, {})[(None,) + vote] = n_votes
            else:
                first_prefs[first_pref][vote] = n_votes
        if first_prefs.get(None):
            split_alloc = self.transferer.transfer(
                first_prefs, eliminated=[None],
            )
            for cand_alloc in split_alloc.values():
                to_remove = []
                to_update = {}
                for vote, n_votes in cand_alloc.items():
                    if vote[0] is None:
                        to_remove.append(vote)
                        to_update[vote[1:]] = n_votes
                for vote in to_remove:
                    del cand_alloc[vote]
                cand_alloc.update(to_update)
            return split_alloc
        else:
            return first_prefs


# Gradual preference addition
class PreferenceAddition:
    '''Evaluates ranked votes by stepwise addition of lower preferences.

    Each candidate starts with their first-preference votes and
    lower-preference votes are added to them until a sufficient amount of
    candidates achieve a majority. This includes the following voting systems:

    -   *Bucklin voting* where the lower preferences are added without change.
    -   *Oklahoma system* where the lower preferences are added divided by
        the order of preference, thus yielding the row of coefficients
        1, 1/2, 1/3, 1/4... (Use :class:`Fraction` to maintain
        exact values.)

    :param coefficients: Coefficients to multiply the lower preferences with
        before they are added to the vote totals (the default adds them simply,
        which creates Bucklin voting).
    :param split_equal_rankings: Whether to split votes having multiple
        alternatives at the same rank, or to add the whole amount to each
        of these alternatives.
    '''
    def __init__(self,
                 coefficients: Union[
                     List[Number],
                     Callable[[int], Number],
                 ] = [1],
                 split_equal_rankings: bool = True,
                 ):
        self.coefficients = coefficients
        self.split_equal_rankings = split_equal_rankings

    def evaluate(self,
                 votes: Dict[RankedVoteType, int],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        '''Select candidates by sequential preference addition.

        :param votes: Ranked votes.
        :param n_seats: Number of candidates to be elected.
        '''
        if self.split_equal_rankings:
            votes = self._decouple_equal_rankings(votes)
        total_votes = collections.defaultdict(int)
        majority_quota = Fraction(sum(votes.values()), 2)
        max_pref_len = max(
            len(preferences) for preferences, n_votes in votes.items()
        )
        elected = []
        for pref_i in range(max_pref_len):
            # add this round's preferences
            self._add_round_votes(total_votes, votes, pref_i, elected)
            # take all that have achieved majority, ordered by the vote sum
            majority = {
                cand: n_votes
                for cand, n_votes in util.sorted_votes(total_votes)
                if n_votes > majority_quota
            }
            best = core.get_n_best(majority, n_seats - len(elected))
            elected.extend(best)
            if len(elected) == n_seats:
                break
            else:
                for cand in best:
                    if cand in total_votes:
                        del total_votes[cand]
            # if still not enough elected, go on by adding another preference
        return core.Tie.reconcile(elected)

    def _decouple_equal_rankings(self,
                                 votes: Dict[RankedVoteType, int]
                                 ) -> Dict[RankedVoteType, Fraction]:
        new_votes = None
        for one_vote, n_votes in votes.items():
            equal_rank_tuples = [
                (i, rank) for i, rank in enumerate(one_vote)
                if isinstance(rank, collections.abc.Set)
            ]
            if equal_rank_tuples:
                if new_votes is None:
                    new_votes = votes.copy()
                del new_votes[one_vote]
                eqr_is = [i for i, rank in equal_rank_tuples]
                variants = list(itertools.product(*(
                    itertools.permutations(rank)
                    for i, rank in equal_rank_tuples
                )))
                n_variant_votes = Fraction(n_votes, len(variants))
                for variant in variants:
                    var_vote = one_vote[:]
                    offset = 0
                    for i, var_part in zip(eqr_is, variant):
                        var_vote = var_vote[:]
                        var_vote = (
                            var_vote[:i+offset]
                            + var_part
                            + var_vote[i+offset+1:]
                        )
                        offset += len(var_part)
                    new_votes[var_vote] = n_variant_votes
        return new_votes if new_votes is not None else votes

    def _add_round_votes(self,
                         total_votes: Dict[Candidate, Fraction],
                         votes: Dict[RankedVoteType, int],
                         pref_i: int,
                         elected: List[Candidate],
                         ) -> None:
        coef = self._get_coefficient(pref_i)
        for preferences, n_votes in votes.items():
            if pref_i < len(preferences):
                preference = preferences[pref_i]
                if isinstance(preference, collections.abc.Set):
                    n_to_add = n_votes * coef
                    for cand in preference:
                        if cand not in elected:
                            total_votes[cand] += n_to_add
                elif preference not in elected:
                    total_votes[preference] += n_votes * coef

    def _get_coefficient(self, pref_i: int) -> Number:
        if hasattr(self.coefficients, '__call__'):
            return self.coefficients(pref_i)
        elif pref_i < len(self.coefficients):
            return self.coefficients[pref_i]
        else:
            return self.coefficients[-1]
