'''Distribution evaluators that are usually called proportional.

This contains the most common distribution evaluators used in party-list
elections that at least aim to be proportional (although some parameter setups
might make the result very nonproportional, such as the Imperiali divisor)
and also some similar, simpler distribution evaluators that aim for strict
proportionality while relaxing some of the constraints of a distribution
evaluator.
'''

import bisect
from fractions import Fraction
from typing import Dict, Union, Callable
from numbers import Number

from .. import util
from ..candidate import Candidate
from ..component import quota, divisor
from . import core


INF = float('inf')


class PureProportionality:
    '''Distribute seats among candidates strictly proportionally (no rounding).

    This evaluator is mostly auxiliary since it gives fractional seat counts.
    '''
    def evaluate(self,
                 votes: Dict[Candidate, int],
                 n_seats: int,
                 prev_gains: Dict[Candidate, int] = {},
                 max_seats: Dict[Candidate, int] = {},
                 ) -> Dict[Candidate, Fraction]:
        '''Distribute seats exactly proportionally, giving fractional seats.

        :param votes: Simple votes to be evaluated.
        :param n_seats: Number of seats to be filled.
        :param prev_gains: Seats gained by the candidate/party in previous
            election rounds to be subtracted from the proportional result
            awarded here.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total (including previous gains).
        '''
        fixed = []
        result = {}
        prev_len_fixed = -1
        while len(fixed) != prev_len_fixed:
            prev_len_fixed = len(fixed)
            result = {
                cand: cseats for cand, cseats in result.items()
                if cand in fixed
            }
            budget = n_seats - sum(result.values())
            current_votes = {
                cand: n_votes for cand, n_votes in votes.items()
                if cand not in fixed
            }
            seats_per_vote = Fraction(budget, sum(current_votes.values()))
            for cand, n_votes in current_votes.items():
                cand_give_seats = n_votes * seats_per_vote
                if int(cand_give_seats) == cand_give_seats:
                    cand_give_seats = int(cand_give_seats)
                cand_has_seats = prev_gains.get(cand, 0)
                cand_max_seats = max_seats.get(cand, INF)
                if cand_give_seats > cand_has_seats:
                    if cand_give_seats > cand_max_seats:
                        # proportional result over maximum, fix maximum
                        fixed.append(cand)
                        cand_give_seats = cand_max_seats
                    result[cand] = cand_give_seats
                else:
                    # proportional result below minimum, fix minimum
                    fixed.append(cand)
                    result[cand] = cand_has_seats
        return {
            cand: cseats - prev_gains.get(cand, 0)
            for cand, cseats in result.items()
        }


class QuotaDistributor:
    '''Distribute seats proportionally, according to multiples of quota filled.

    Each contestant is awarded the number of seats according to the number
    of times their votes fill the provided quota. (This essentially means the
    numbers of votes are divided by the quota and rounded down to get the
    numbers of seats.)

    This is usually not a self-standing evaluator because it (except for very
    rare cases) does not award the full number of seats.

    :param quota_function: A callable producing the quota threshold from the
        total number of votes and number of seats. The common quota functions
        can be referenced by string name from the :mod:`quota` module.
    '''
    def __init__(self,
                 quota_function: Union[
                     str, Callable[[int, int], Number]
                 ] = 'droop',
                 ):
        self.quota_function = quota.construct(quota_function)

    def evaluate(self,
                 votes: Dict[Candidate, int],
                 n_seats: int,
                 prev_gains: Dict[Candidate, int] = {},
                 max_seats: Dict[Candidate, int] = {},
                 ) -> Dict[Candidate, int]:
        '''Distribute seats proportionally by multiples of quota filled.

        :param votes: Simple votes to be evaluated.
        :param n_seats: Number of seats to be filled.
        :param prev_gains: Seats gained by the candidate/party in previous
            election rounds to be subtracted from the proportional result
            awarded here.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total (including previous gains).
        '''
        quota_number = self.quota_function(
            sum(votes.values()), n_seats
        )
        selected = {}
        n_overshot = 0
        overshot_candidates = []
        for candidate, n_votes in votes.items():
            n_prev = prev_gains.get(candidate, 0)
            if n_votes >= quota_number:
                n_add_seats = int(Fraction(n_votes, quota_number)) - n_prev
                if n_add_seats > 0:
                    if n_add_seats + n_prev > max_seats.get(candidate, INF):
                        overshoot = n_add_seats + n_prev
                        n_add_seats -= overshoot
                        n_overshot += overshoot
                        overshot_candidates.append(candidate)
                    selected[candidate] = n_add_seats
        if n_overshot:
            remaining_votes = {
                cand: n_votes for cand in votes.keys()
                if cand not in overshot_candidates
            }
            total_gained = {
                cand: selected.get(cand, 0) + prev_gains.get(cand, 0)
                for cand in votes
            }
            util.add_dict_to_dict(selected, self.evaluate(
                remaining_votes,
                n_overshot,
                prev_gains=total_gained,
                max_seats=max_seats
            ))
        return selected


class LargestRemainder:
    '''Distribute seats proportionally, rounding by largest remainder.

    Each contestant is awarded the number of seats according to the number
    of times their votes fill the provided quota, just like
    :class:`QuotaDistributor`. In addition to that, the
    parties that have the largest remainder of votes after the quotas are
    subtracted get an extra seat until the number of seats is exhausted.

    This includes some popular proportional party-list systems like Hare,
    Droop or Hagenbach-Bischoff. The result is usually very close to
    proportionality (closer than in highest averages systems) but might suffer
    from an Alabama paradox where adding proportionally distributed votes might
    cause one of the contestants to lose seats.

    :param quota_function: A callable producing the quota threshold from the
        total number of votes and number of seats. The common quota functions
        can be referenced by string name from the :mod:`quota` module.
    '''
    def __init__(self,
                 quota_function: Union[str, Callable[[int, int], Number]],
                 ):
        self.quota_function = quota.construct(quota_function)
        self._quota_evaluator = QuotaDistributor(self.quota_function)

    def evaluate(self,
                 votes: Dict[Candidate, int],
                 n_seats: int,
                 prev_gains: Dict[Candidate, int] = {},
                 max_seats: Dict[Candidate, int] = {},
                 ) -> Dict[Candidate, int]:
        '''Distribute seats proportionally, rounding by largest remainder.

        :param votes: Simple votes to be evaluated.
        :param n_seats: Number of seats to be filled.
        :param prev_gains: Seats gained by the candidate/party in previous
            election rounds to be subtracted from the proportional result
            awarded here.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total (including previous gains).
        '''
        # first, assign the non-remainder seats for those over the quota
        quota_elected = self._quota_evaluator.evaluate(
            votes, n_seats, prev_gains
        )
        quota_number = self.quota_function(
            sum(votes.values()), n_seats
        )
        gained_prerem = util.sum_dicts(quota_elected, prev_gains)
        n_for_remainder = n_seats - sum(gained_prerem.values())
        remainders = {
            cand: Fraction(n_votes, quota_number) - gained_prerem.get(cand, 0)
            for cand, n_votes in votes.items()
            if gained_prerem.get(cand, 0) < max_seats.get(cand, INF)
        }
        for candidate in core.get_n_best(remainders, n_for_remainder):
            if candidate in quota_elected:
                quota_elected[candidate] += 1
            else:
                quota_elected[candidate] = 1
        return quota_elected


class HighestAverages:
    '''Distribute seats proportionally by ordering divided vote counts.

    Divides the vote count for each party by an increasing sequence of divisors
    (usually small integers), sorts these quotients and awards a seat for each
    of the first n_seats quotients.

    This includes some popular proportional party-list systems like D'Hondt or
    Sainte-Laguë/Webster The result is usually quite close to proportionality
    and avoids the Alabama paradox of largest remainder systems. However, it
    usually favors either large or smaller parties, depending on the choice
    of the divisor function.

    :param divisor_function: A callable producing the divisor from the number
        of seats awarded to the contestant so far. For example, the D'Hondt
        divisor (which uses the natural numbers sequence) would always return
        the number of currently held seats raised by one. The common divisor
        functions can be referenced by string name from the :mod:`divisor`
        module.
    '''
    def __init__(self,
                 divisor_function: Union[
                     str, Callable[[int], Number]
                 ] = 'd_hondt',
                 ):
        self.divisor_function = divisor.construct(divisor_function)

    def evaluate(self,
                 votes: Dict[Candidate, int],
                 n_seats: int,
                 prev_gains: Dict[Candidate, int] = {},
                 max_seats: Dict[Candidate, int] = {},
                 ) -> Dict[Candidate, int]:
        '''Distribute seats proportionally by highest averages.

        :param votes: Simple votes to be evaluated.
        :param n_seats: Number of seats to be filled.
        :param prev_gains: Seats gained by the candidate/party in previous
            election rounds, to determine the starting divisor.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total (including previous gains).
        '''
        totals = prev_gains.copy()
        quotient_dict = {}
        for cand, n_votes in votes.items():
            cand_total = totals.get(cand, 0)
            divisor = self.divisor_function(cand_total)
            if divisor > 0 and cand_total < max_seats.get(cand, n_seats):
                quotient_dict[cand] = Fraction(n_votes, divisor)
        candidates, quotients = [list(x) for x in zip(*util.sorted_votes(
            quotient_dict, descending=False
        ))]
        rem_seats = n_seats - sum(totals.values())
        while rem_seats > 0 and quotients:
            n_elect = 1
            max_q = quotients[-1]
            while n_elect < len(quotients) and quotients[-n_elect-1] == max_q:
                n_elect += 1
            to_elect = candidates[-n_elect:]
            if n_elect > rem_seats:
                to_elect = [core.Tie(to_elect)] * rem_seats
            for cand in to_elect:
                if cand in totals:
                    totals[cand] += 1
                else:
                    totals[cand] = 1
                rem_seats -= 1
            for i in range(n_elect):
                cand = candidates.pop()
                quotients.pop()
                cand_total = totals.get(cand, 0)
                if cand_total < max_seats.get(cand, n_seats) and cand in votes:
                    new_quot = Fraction(
                        votes[cand], self.divisor_function(cand_total)
                    )
                    new_pos = bisect.bisect_left(quotients, new_quot)
                    candidates.insert(new_pos, cand)
                    quotients.insert(new_pos, new_quot)
        return {
            cand: cand_seats - prev_gains.get(cand, 0)
            for cand, cand_seats in totals.items()
            if cand_seats > prev_gains.get(cand, 0)
        }


'''
class BiproportionalEvaluator:
    def __init__(self,
                 candidate_eval: DistributionEvaluator,
                 district_eval: Optional[DistributionEvaluator] = None,
                 ):
        self.candidate_eval = candidate_eval
        self.district_eval = district_eval if district_eval else candidate_eval
        self._agg = convert.ConstituencyVoteAggregator()

    def evaluate(self,
                 votes: Dict[Constituency, Dict[Candidate, int]],
                 n_seats: int,
                 ) -> Dict[Constituency, Dict[Candidate, int]]:
        # districts = list(votes.keys())
        # candidates = list(frozenset(
        #     cand for clist in votes.values() for cand in clist
        # ))
        district_sums = {
            district: sum(dvotes.values())
            for district, dvotes in votes.items()
        }
        district_alloc = self.district_eval.evaluate(district_sums, n_seats)
        cand_sums = self._agg.aggregate(votes)
        cand_alloc = self.candidate_eval.evaluate(cand_sums, n_seats)
        district_mult = {district: 1 for district in district_alloc.keys()}
        cand_mult = {cand: 1 for cand in cand_alloc.keys()}
        dist_cand_seats = {}
        print(district_alloc)
        print(cand_alloc)
        i = 1
        while True:
            print(i)
            prev_dist_cand_seats = dist_cand_seats
            # district-wise distribution: make sure each district has its
            # rightful amount of seats and distribute them among parties
            # accordingly
            dist_cand_seats = {}
            for district, dvotes in votes.items():
                part_votes = {
                    cand: cdvotes * cand_mult[cand] * district_mult[district]
                    for cand, cdvotes in dvotes.items()
                }
                dist_cand_seats[district] = self.candidate_eval.evaluate(
                    part_votes, district_alloc[district]
                )
            print(dist_cand_seats)
            if dist_cand_seats == prev_dist_cand_seats:
                print()
                print('END')
                print()
                return dist_cand_seats
            # adjust party vote multipliers
            cand_seats = self._agg.aggregate(dist_cand_seats)
            print(cand_seats)
            cand_mult = {
                cand: cand_alloc[cand] / cur_seats
                for cand, cur_seats in cand_seats.items()
            }
            print(cand_mult)
            # party-wise distribution: make sure each party has its rightful
            # amount of seats and distribute them among districts accordingly
            dist_seats = {}
            for cand, n_seats in cand_alloc.items():
                cvotes = {
                    district: (
                        votes[district].get(cand, 0)
                        * district_mult[district]
                        * cand_mult[cand]
                    )
                    for district in district_alloc.keys()
                }
                cand_eval = self.district_eval.evaluate(cvotes, n_seats)
                util.add_dict_to_dict(dist_seats, cand_eval)
            print(dist_seats)
            # adjust district vote multipliers
            district_mult = {
                district: district_alloc[district] / dseats
                for district, dseats in dist_seats.items()
            }
            print(district_mult)
            print()
            if i > 10:
                raise RuntimeError
            i += 1
'''
