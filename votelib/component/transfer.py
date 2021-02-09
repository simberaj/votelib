'''Objects to transfer votes between candidates for transferable vote systems.

Transfers of votes from eliminated and elected candidates to candidates staying
in the contest are an essential part of any transferable vote system,
such as the one of
:class:`votelib.evaluate.sequential.TransferableVoteSelector`.
There are many variants how to achieve this, some are implemented here.

NOTE: The :class:`VoteTransferer` interface is provisional and may be changed
in the future, chiefly to accommodate a wider range of transfer methods (Meek,
Wright...)
'''

import sys
import abc
import collections
import random
import itertools
import bisect
import functools
from fractions import Fraction
from typing import Any, List, Dict, FrozenSet, Optional, Collection, Union
from numbers import Number

from votelib.candidate import Candidate
from votelib.vote import RankedVoteType
from votelib.evaluate.proportional import LargestRemainder
from votelib.persist import simple_serialization


RankedVoteAllocation = Dict[Optional[Candidate], Dict[RankedVoteType, Number]]


def ranked_next(vote: RankedVoteType,
                cand: Candidate,
                allowed: Collection[Candidate],
                ) -> FrozenSet[Candidate]:
    '''Select the candidate(s) ranked in the vote after the given candidate.

    :param vote: The ranked vote to examine.
    :param cand: The candidate to look after.
    :param allowed: Only return candidate(s) from this collection, skip all
        others to lower ranks.
    :returns: Candidates ranked after cand. Will be empty if cand was ranked
        last or is not present in the vote. Will only have multiple members
        if the ranked vote contains a shared rank after cand.
    '''
    # Iterate through the vote until we find cand. At him, set take_next to
    # True to return the candidates ranked next.
    take_next = False
    for rank_alt in vote:
        if isinstance(rank_alt, frozenset):
            if take_next:
                allowed_alt = rank_alt.intersection(allowed)
                if allowed_alt:
                    return allowed_alt
                # else go on for another rank
            elif cand in rank_alt:
                take_next = True
        else:
            if take_next:
                if rank_alt in allowed:
                    return frozenset([rank_alt])
            elif cand == rank_alt:
                take_next = True
    return frozenset()    # exhausted ballot


def distribute_n_random(cand_weights: Dict[Any, Number],
                        n: int,
                        limit_by_weight: bool = False,
                        ) -> Dict[Any, int]:
    '''Distribute n randomly among candidates with weighted probabilities.

    :param cand_weights: Candidates and their weights.
    :param n: Number to distribute.
    :param limit_by_weight: Whether the maximum count assigned to a candidate
        is limited by the value of their weight.
    :returns: A dictionary mapping candidates to their assigned quantities.
        The quantities sum to n.
    '''
    candidates, weights = zip(*cand_weights.items())
    total_weight = sum(weights)
    if isinstance(total_weight, Fraction):
        max_denom = max(
            f.denominator if hasattr(f, 'denominator') else 1
            for f in weights
        )
        # multiply weights by maximum denominator and then go on with integers
        weights = [w * max_denom for w in weights]
        total_weight *= max_denom
    if isinstance(total_weight, int):
        cum_weights = list(itertools.accumulate(weights))
        generator = random.sample(range(total_weight), n)
    else:
        cum_weights = list(itertools.accumulate(
            w / total_weight for w in weights
        ))
        generator = (random.random() for i in range(n))
    do_bisect = functools.partial(bisect.bisect_right, cum_weights)
    index_selection = collections.Counter(
        do_bisect(i) for i in generator
    )
    selection = {candidates[ind]: n for ind, n in index_selection.items()}
    if limit_by_weight:
        return LargestRemainder('hare').evaluate(
            selection, n, max_seats=cand_weights
        )
    else:
        return selection


class VoteTransferer(metaclass=abc.ABCMeta):
    '''An abstract base class for vote transferers.

    Vote transferers must provide a `subtract()` method that subtracts votes
    from elected candidates and a `transfer()` method that redistributes
    votes for some candidates to those remaining in the contest.
    '''
    @abc.abstractmethod
    def subtract(self,
                 allocation: RankedVoteAllocation,
                 elected: Dict[Candidate, int],
                 ) -> RankedVoteAllocation:
        '''Remove votes from elected candidates according to the quota.

        :param allocation: Current allocation of ranked votes to candidates.
            The votes allocated to elected candidates will be lowered by the
            amount corresponding to the quota for their election.
        :param elected: Elected candidates, mapped to the quota with which they
            were elected (or multiples thereof, if they were awarded multiple
            seats). These quotas should be removed from the candidates'
            votes (because so many votes were used).
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def transfer(self,
                 allocation: RankedVoteAllocation,
                 candidates: List[Candidate],
                 ) -> RankedVoteAllocation:
        '''Transfer votes from eliminated or fully elected candidates.

        :param allocation: Current allocation of ranked votes to candidates.
            The votes allocated to specified candidates will be reallocated
            to other candidates.
        :param candidates: Candidates no longer continuing in the contest.
        '''
        raise NotImplementedError


class SimpleVoteTransferer(VoteTransferer):
    def subtract(self,
                 allocation: RankedVoteAllocation,
                 elected: Dict[Candidate, int],
                 ) -> RankedVoteAllocation:
        allocation = {cand: alloc.copy() for cand, alloc in allocation.items()}
        if elected:
            for cand, quota in elected.items():
                self._subtract(allocation[cand], quota)
        return allocation

    def transfer(self,
                 allocation: RankedVoteAllocation,
                 candidates: List[Candidate],
                 ) -> RankedVoteAllocation:
        '''Transfer votes from eliminated or fully elected candidates.

        :param allocation: Current allocation of ranked votes to candidates.
            The votes allocated to specified candidates will be reallocated
            to other candidates that are present in the allocation, or
            reassigned to the None key as exhausted ballots.
        :param candidates: Candidates to be removed from the allocation.
        '''
        allocation = {cand: alloc.copy() for cand, alloc in allocation.items()}
        to_remove = [cand for cand in allocation if cand in candidates]
        continuing = [
            cand for cand in allocation
            if cand is not None and cand not in candidates
        ]
        for cand in to_remove:
            for vote, n_votes in allocation[cand].items():
                targets = ranked_next(vote, cand, continuing)
                if targets:
                    if len(targets) > 1:
                        realloc = self._distribute_equal_ranking(
                            targets, n_votes
                        )
                    else:
                        target, = targets
                        realloc = {target: n_votes}
                    for target, n in realloc.items():
                        target_alloc = allocation.setdefault(target, {})
                        if vote not in target_alloc:
                            target_alloc[vote] = 0
                        target_alloc[vote] += n
                else:
                    # Put the ballots on the exhausted pile.
                    if None not in allocation:
                        allocation[None] = {}
                    if vote not in allocation[None]:
                        allocation[None][vote] = 0
                    allocation[None][vote] += n_votes
            del allocation[cand]
        return allocation

    def _subtract(self,
                  cand_alloc: Dict[RankedVoteType, Number],
                  quota: int,
                  ) -> None:
        # Remove a total of *quota* votes from values of *cand_alloc*.
        # Hare STV does this randomly, Gregory STV uses exact proportional
        # fractions.
        raise NotImplementedError

    def _distribute_equal_ranking(self,
                                  targets: FrozenSet[Candidate],
                                  n_votes: int,
                                  ) -> Dict[Candidate, int]:
        # Distribute a total of *n_votes* among candidates in *targets*.
        # Hare STV does this randomly, Gregory STV uses exact proportional
        # fractions.
        raise NotImplementedError


@simple_serialization
class Hare(SimpleVoteTransferer):
    '''Hare (random ballot selection) vote transferer.

    This is the variant used (AFAIK) in Irish lower house legislative elections
    (Dáil Éireann).

    When a candidate is elected by quota, the number of ballots corresponding
    to the quota is randomly selected and discarded, the rest is fully
    transferred to their next preferences.

    In case of shared ranks, the votes are randomly distributed between the
    candidates sharing the rank.

    :param seed: Seed for the random generator.
    '''
    def __init__(self,
                 seed: Optional[int] = None,
                 ):
        self.seed = seed
        self.stable = (self.seed is not None)

    def _subtract(self,
                  cand_alloc: Dict[RankedVoteType, Number],
                  n_sub: int,
                  ) -> None:
        random.seed(self.seed)
        subtractions = distribute_n_random(
            cand_alloc, n_sub, limit_by_weight=True
        )
        for vote, to_sub in subtractions.items():
            to_sub_from = cand_alloc[vote]
            if to_sub >= to_sub_from:
                del cand_alloc[vote]
            else:
                cand_alloc[vote] -= to_sub

    def _distribute_equal_ranking(self,
                                  targets: FrozenSet[Candidate],
                                  n_votes: int,
                                  ) -> Dict[Candidate, int]:
        whole_val = n_votes // len(targets)
        if whole_val:
            result = {cand: whole_val for cand in targets}
            remainder = n_votes - len(targets) * whole_val
            if not remainder:
                return result
        else:
            result = {}
            remainder = n_votes
        random.seed(self.seed)
        remnant_dist = distribute_n_random(
            {tgt: remainder for tgt in targets},
            remainder,
        )
        for cand, transfer in remnant_dist.items():
            result[cand] = result.get(cand, 0) + transfer
        return result


@simple_serialization
class Gregory(SimpleVoteTransferer):
    '''Gregory (fractional) vote transferer.

    The variant used is the Weighted Inclusive Gregory Method (WIGM) used e.g.
    in Scottish local government elections.

    When a candidate is elected by quota, the fraction corresponding to the
    quota divided by total votes for the candidate is used to multiply (lower)
    each vote allocated to that candidate; the votes are then transferred to
    next candidates on the ballots.

    In case of shared ranks, the votes are evenly distributed between the
    candidates sharing the rank.

    The implementation produces exact fractional votes. Rounding rules are not
    implemented yet.
    '''
    def _subtract(self,
                  cand_alloc: Dict[RankedVoteType, Fraction],
                  n_sub: Fraction,
                  ) -> None:
        current_sum = sum(cand_alloc.values())
        if current_sum == 0:
            raise RuntimeError
        if n_sub >= current_sum:
            # We need to subtract more than there is, delete all votes.
            for vote in list(cand_alloc.keys()):
                del cand_alloc[vote]
        else:
            fraction = Fraction(current_sum - n_sub, current_sum)
            for vote in cand_alloc.keys():
                cand_alloc[vote] *= fraction

    def _distribute_equal_ranking(self,
                                  targets: FrozenSet[Candidate],
                                  n_votes: Fraction,
                                  ) -> Dict[Candidate, Fraction]:
        split_val = Fraction(n_votes, len(targets))
        return {cand: split_val for cand in targets}


def construct(trans_def: Union[VoteTransferer, str]) -> VoteTransferer:
    return (
        getattr(sys.modules[__name__], trans_def)()
        if isinstance(trans_def, str)
        else trans_def
    )
