'''Evaluators that operate sequentially on ranked votes.

This hosts mainly the transferable vote evaluator
(:class:`TransferableVoteSelector`) but also its less known relative,
:class:`PreferenceAddition`.
'''
import operator
import sys
import itertools
import collections
from fractions import Fraction
from typing import Any, List, Dict, Tuple, Union, Callable, Optional
from numbers import Number

from ..candidate import Candidate
from ..vote import RankedVoteType
from ..component import transfer, quota
from ..persist import simple_serialization
from . import core
from .. import util, persist

INF = float('inf')


@simple_serialization
class TransferableVoteDistributor:
    '''Select candidates by eliminating and transfering votes among them.

    This is the evaluator for transferable vote selection (since the evaluator
    does not concern itself with restrictions on allowed votes, it covers not
    only single transferable vote systems - STV -, but also potential multiple
    transferable vote systems). Its single-winner
    variant is also called instant-runoff voting (IRV).

    First, this evaluator looks at first-preference votes. If any of the
    candidates has at least a specified quota of votes, they are awarded the
    number of seats according to how many times the quota fits into their
    number of votes. If they hit their maximum achievable number of seats
    (if there is one), their votes over the quota are redistributed
    (reallocated) to other candidates according to the next stated preference.

    If no candidate has the quota, the candidate with the fewest
    currently allocated votes is eliminated and their votes transferred
    according to their next stated preference. Votes that have no further
    stated preferences are called exhausted and are removed from consideration.

    The current version does not use elimination breakpoints.

    :param transferer: An instance determining how much votes for eliminated
        candidates to transfer and to whom. It must provide the
        :class:`transfer.VoteTransferer` interface (experimental, stability
        not guaranteed). The basic vote transfer variants are implemented
        in the :mod:`transfer` module and can be referred to by their names
        as strings.
    :param retainer: A selector determining which candidates to retain when
        elimination is to be performed (it may accept a number of seats, which
        will correspond to the number of candidates to retain). If not given,
        the candidates with the lowest amounts of currently allocated votes
        will be eliminated one by one.
    :param eliminate_step: Determines how many candidates to eliminate whenever
        elimination is to be performed. If a negative integer, determines how
        many candidates to eliminate at each step (the default eliminates one
        candidate at a time). If a positive integer, determines how many
        candidates to retain after elimination - this essentially allows only
        a single elimination and might cause an infinite loop if not used
        properly.
    :param quota_function: A callable producing the quota threshold from the
        total number of votes and number of seats. The common quota functions
        can be referenced by string name from the :mod:`quota` module. If
        None, no election by quota takes place - the candidates are just
        eliminated until the desired number remains. (Not specifying the quota
        only works when the maximum numbers of seats per candidate are
        specified.)
    :param accept_quota_equal: Whether to use non-strict comparison for the
        number of votes against the quota.
    '''
    def __init__(self,
                 transferer: Union[str, transfer.VoteTransferer] = 'Gregory',
                 retainer: Optional[core.Selector] = None,
                 eliminate_step: Optional[int] = -1,
                 quota_function: Union[
                     str, Callable[[int, int], Number], None
                 ] = 'droop',
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
                 votes: Dict[RankedVoteType, int],
                 n_seats: int,
                 prev_gains: Dict[Candidate, int] = {},
                 max_seats: Dict[Candidate, int] = {},
                 ) -> Dict[Candidate, int]:
        '''Allocate seats to candidates by transferable vote.

        :param votes: Ranked votes. Equal rankings are allowed.
        :param n_seats: Number of seats to allocate to candidates.
        :param prev_gains: Seats gained by the candidate/party in previous
            election rounds to be subtracted from the result awarded here.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total (including previous gains).
        '''
        return self.nth_count(
            votes,
            n_seats,
            sys.maxsize,    # this is not maximum int value but an equivalent
            prev_gains=prev_gains,
            max_seats=max_seats,
        )[1]

    def next_count(self,
                   allocation: Dict[Candidate, Dict[RankedVoteType, Number]],
                   n_seats: int,
                   total_n_votes: Number,
                   prev_gains: Dict[Candidate, int] = {},
                   max_seats: Dict[Candidate, int] = {},
                   ) -> Tuple[
                       Dict[Candidate, Dict[RankedVoteType, Number]],
                       Dict[Candidate, int]
                   ]:
        '''Advance the transferable voting process by one iteration (count).

        :param allocation: Current allocation of ranked votes to candidates
            still contesting the remaining seats.
        :param n_seats: Total number of seats to award.
        :param total_n_votes: The total number of votes cast in the election.
            Used to determine the election quota, if enabled.
        :param prev_gains: Numbers of seats the candidates gained in the
            previous counts of the election.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total (including previous gains).
        :returns: A 2-tuple containing the new allocation of votes and
            a mapping of candidates to newly assigned seats (might be empty if
            no seats were awarded on this count).
        '''
        n_rem_seats = n_seats - sum(prev_gains.values())
        avail_seats = {
            cand: max_seats.get(cand, INF) - prev_gains.get(cand, 0)
            for cand in allocation.keys()
        }
        if sum(avail_seats.values()) == n_rem_seats:
            return {}, avail_seats    # elect all remaining, no choice
        else:
            totals = {
                cand: sum(cand_votes.values())
                for cand, cand_votes in allocation.items()
            }
            quota_val = self._compute_quota(total_n_votes, n_seats)
            quota_elected = self._elect_by_quota(
                totals,
                quota_val,
                n_rem_seats,
                prev_gains=prev_gains,
                max_seats=max_seats
            )
            if quota_elected:
                return self._transfer_elected(
                    allocation, quota_elected, quota_val, prev_gains, max_seats
                ), quota_elected
            else:
                # nobody elected by quota, we have to eliminate
                retained = self.select_retained(totals)
                eliminated = [
                    cand for cand in totals.keys()
                    if cand not in retained
                ]
                return self.transferer.transfer(
                    allocation, eliminated
                ), {}

    def nth_count(self,
                  votes: Dict[RankedVoteType, Number],
                  n_seats: int = 1,
                  count_number: int = 1,
                  prev_gains: Dict[Candidate, int] = {},
                  max_seats: Dict[Candidate, int] = {},
                  ) -> Tuple[
                      Dict[Candidate, Dict[RankedVoteType, Number]],
                      Dict[Candidate, int]
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
        # quota needs to be computed on full votes
        total_votes = sum(votes.values())
        seats = prev_gains.copy()
        for count_i in range(count_number):
            n_already_elected = sum(seats.values())
            if n_already_elected == n_seats:
                break
            if new_allocation is not None:
                allocation = new_allocation
            new_allocation, newly_elected = self.next_count(
                allocation,
                n_seats,
                total_votes,
                prev_gains=seats,
                max_seats=max_seats,
            )
            if not newly_elected and new_allocation == allocation:
                raise core.VotingSystemError('infinite loop in STV')
            util.add_dict_to_dict(seats, newly_elected)
        return {
            cand: sum(cand_votes.values())
            for cand, cand_votes in allocation.items()
        }, seats

    def _compute_quota(self,
                       total_n_votes: Optional[Number],
                       n_seats: int
                       ) -> Number:
        if self.quota_function and total_n_votes and n_seats:
            return self.quota_function(total_n_votes, n_seats)
        else:
            return INF

    def _transfer_elected(self,
                          allocation: Dict[
                              Candidate, Dict[RankedVoteType, Number]
                          ],
                          elected: Dict[Candidate, int],
                          quota_val: Number,
                          prev_gains: Dict[Candidate, int] = {},
                          max_seats: Dict[Candidate, int] = {},
                          ):
        subtracted_alloc = self.transferer.subtract(
            allocation,
            {cand: n_seats * quota_val for cand, n_seats in elected.items()}
        )
        exhausted = [
            cand for cand, n_add_seats in elected.items()
            if (
                n_add_seats + prev_gains.get(cand, 0)
                == max_seats.get(cand, INF)
            )
        ]
        if exhausted:
            return self.transferer.transfer(
                subtracted_alloc, exhausted
            )
        else:
            return subtracted_alloc

    def _elect_by_quota(self,
                        totals: Dict[Candidate, Number],
                        quota_val: Number,
                        n_rem_seats: int,
                        prev_gains: Dict[Candidate, int] = {},
                        max_seats: Dict[Candidate, int] = {},
                        ) -> Dict[Candidate, int]:
        quota_multiples = {}
        overcounts = {}
        cand_items = sorted(
            totals.items(),
            key=operator.itemgetter(1),
            reverse=True
        )
        for cand, total in cand_items:
            n_multiples = total // quota_val
            overcount = total - n_multiples * quota_val
            if self.accept_quota_equal or overcount:
                actual_seats = (
                    min(n_multiples, max_seats.get(cand, INF))
                    - prev_gains.get(cand, 0)
                )
                if actual_seats > 0:
                    quota_multiples[cand] = actual_seats
                    overcounts[cand] = overcount
        if quota_multiples:
            total_awarded = sum(quota_multiples.values())
            if total_awarded > n_rem_seats:
                # Over maximum, we need to select who will get one less seat.
                quota_multiples = self._correct_overcount(
                    quota_multiples, overcounts, n_rem_seats
                )
        return quota_multiples

    def _correct_overcount(self,
                           awarded_seats: Dict[Candidate, int],
                           overcounts: Dict[Candidate, Number],
                           n_rem_seats: int,
                           ) -> Dict[Candidate, int]:
        kept = core.get_n_best(overcounts, n_rem_seats)
        if any(isinstance(e, core.Tie) for e in kept):
            raise NotImplementedError('tie in STV quota election')
        else:
            return {
                cand: (n_seats - 1 if cand not in kept else n_seats)
                for cand, n_seats in awarded_seats
                if cand in kept or n_seats > 1
            }

    def first_preference_allocation(self,
                                    votes: Dict[RankedVoteType, Number],
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
                # first rank is shared
                # we pass this to transferer - we prepend a fictional (None)
                # eliminated candidate to this vote and have it transferred
                first_prefs.setdefault(None, {})[(None,) + vote] = n_votes
            else:
                first_prefs[first_pref][vote] = n_votes
        if first_prefs.get(None):
            split_alloc = self.transferer.transfer(
                first_prefs, candidates=[None],
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

    def select_retained(self,
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


class TransferableVoteSelector:
    def __init__(self, *args, **kwargs):
        got_inner_pos_arg = (
            len(args) == 1 and not kwargs
            and isinstance(args[0], TransferableVoteDistributor)
        )
        if got_inner_pos_arg:
            self._inner = args[0]
        elif '_inner' in kwargs:
            self._inner = kwargs['_inner']
        else:
            self._inner = TransferableVoteDistributor(*args, **kwargs)

    def evaluate(self,
                 votes: Dict[RankedVoteType, int],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        return self.nth_count(votes, n_seats, sys.maxsize)[1]

    def next_count(self,
                   allocation: Dict[Candidate, Dict[RankedVoteType, Number]],
                   n_seats: int,
                   total_n_votes: Number = None,
                   ) -> Tuple[
                       Dict[Candidate, Dict[RankedVoteType, Number]],
                       List[Candidate]
                   ]:
        '''Advance the transferable voting process by one iteration (count).

        :param allocation: Current allocation of ranked votes to candidates
            still contesting the remaining seats.
        :param n_seats: Total number of seats to award.
        :param total_n_votes: The total number of votes cast in the election.
            Used to determine the election quota, if enabled.
        :returns: A 2-tuple containing the new allocation of votes and
            a mapping of candidates to newly assigned seats (might be empty if
            no seats were awarded on this count).
        '''
        all_cands = set()
        for cand, alloc_votes in allocation:
            all_cands.update(util.all_ranked_candidates(alloc_votes))
        new_alloc, newly_elected = self._inner.next_count(
            allocation,
            n_seats,
            total_n_votes,
            max_seats={c: 1 for c in all_cands}
        )
        return new_alloc, util.distribution_to_selection(newly_elected)

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
        all_cands = util.all_ranked_candidates(votes)
        allocation, elected_dict = self._inner.nth_count(
            votes,
            n_seats,
            count_number,
            max_seats={c: 1 for c in all_cands}
        )
        return allocation, util.distribution_to_selection(elected_dict)

    @property
    def quota_function(self):
        return self._inner.quota_function

    def to_dict(self) -> Dict[str, Any]:
        return {
            'class': persist.scoped_class_name(self),
            '_inner': self._inner.to_dict(),
        }


# Gradual preference addition
@simple_serialization
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
