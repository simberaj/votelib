'''Various utility functions for other modules of Votelib.

There should normally be no need to use these functions directly.
'''

import operator
import itertools
import collections
import bisect
import random
from fractions import Fraction
from typing import Any, List, Tuple, Dict, Union, Iterable
from numbers import Number

from votelib.vote import RankedVoteType
from votelib.candidate import Candidate


def add_dict_to_dict(dict1: Dict[Any, Number],
                     dict2: Dict[Any, Number],
                     ) -> None:
    for key, addition in dict2.items():
        dict1[key] = dict1.get(key, 0) + addition


def sum_dicts(dict1: Dict[Any, Number],
              dict2: Dict[Any, Number],
              ) -> Dict[Any, Number]:
    summed = dict1.copy()
    add_dict_to_dict(summed, dict2)
    return summed


def descending_dict(d: Dict[Any, Number]) -> Dict[Any, Number]:
    return dict(sorted(d.items(), key=operator.itemgetter(1), reverse=True))


def all_ranked_candidates(votes: Dict[RankedVoteType, Any]
                          ) -> List[Candidate]:
    '''Return a list of all candidates appearing in any of the rankings.

    Preserves the input ordering (i.e. first, the candidates ranked in any
    first choice position are listed in the order of the first such vote,
    first vote are listed, then all remaining candidates from the second vote,
    etc.)

    :param votes: Ranked votes.
    :returns: All unique candidates from the ranked votes.
    '''
    output = []
    for cand, rank_i, n_votes in all_rankings(votes):
        if cand not in output:
            output.append(cand)
    return output


def all_rankings(votes: Dict[RankedVoteType, Any]
                 ) -> Iterable[Tuple[Candidate, int, Any]]:
    rank_i = 0
    while True:
        used = False
        for ranking, n_votes in votes.items():
            if len(ranking) > rank_i:
                used = True
                positioned = ranking[rank_i]
                if isinstance(positioned, collections.abc.Set):
                    for cand in positioned:
                        yield cand, rank_i, n_votes
                else:
                    yield positioned, rank_i, n_votes
        if used:
            rank_i += 1
        else:
            break


def distribution_to_selection(d: Dict[Any, Number]) -> List[Any]:
    return list([cand for cand, _ in sorted(
        d.items(),
        key=operator.itemgetter(1),
        reverse=True    # rank in descending order of votes/scores/seats
    )])


def sorted_votes(votes: Dict[Any, Number],
                 descending: bool = True,
                 ) -> List[Tuple[Any, Number]]:
    '''Return votes items sorted by value.'''
    return list(sorted(
        votes.items(),
        key=operator.itemgetter(1),
        reverse=descending
    ))


def select_n_random(votes: Dict[Any, Number],
                    n: int = 1,
                    ) -> List[Any]:
    candidates, weights = zip(*sorted_votes(votes))
    candidates = list(candidates)
    cum_weights = list(itertools.accumulate(weights))
    weight_total = cum_weights[-1]
    if isinstance(weight_total, int):    # we have all integers
        return _select_n_random_int(candidates, cum_weights, n)
    elif isinstance(weight_total, Fraction):  # we have fractions, still exact
        last_denom = weight_total.denominator
        return _select_n_random_int(
            candidates, [w * last_denom for w in cum_weights], n
        )
    else:
        # TODO raise inexact arithmetics warning
        return _select_n_random_float(candidates, cum_weights, n)


def _select_n_random_int(candidates: List[Any],
                         cum_weights: List[int],
                         n: int,
                         ) -> List[Any]:
    if n > len(candidates):
        return candidates
    chosen = []
    while len(chosen) < n:
        new_cand_i = bisect.bisect_left(
            cum_weights,
            random.randrange(1, cum_weights[-1] + 1)
        )
        chosen.append(candidates.pop(new_cand_i))
        subtract_wt = cum_weights.pop(new_cand_i)
        if new_cand_i != 0 and cum_weights:
            subtract_wt -= cum_weights[new_cand_i-1]
        cum_weights = (
            cum_weights[:new_cand_i]
            + [wt - subtract_wt for wt in cum_weights[new_cand_i:]]
        )
    return chosen


def _select_n_random_float(candidates: List[Any],
                           cum_weights: List[Number],
                           n: int,
                           ) -> List[Any]:
    return random.choices(
        candidates,
        cum_weights=cum_weights,
        k=n
    )


def exact_mean(values: List[Union[int, Fraction]]) -> Fraction:
    return Fraction(sum(values), len(values))


EXACT_AGGREGATORS = {
    'mean': exact_mean,
}
