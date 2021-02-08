'''Distribution evaluators that are usually called proportional.

This contains the most common distribution evaluators used in party-list
elections that at least aim to be proportional (although some parameter setups
might make the result very nonproportional, such as the Imperiali divisor)
and also some similar, simpler distribution evaluators that aim for strict
proportionality while relaxing some of the constraints of a distribution
evaluator.
'''

import bisect
import collections
import decimal
from fractions import Fraction
from typing import (
    List, Tuple, Dict, Union, Callable, Optional, Set, Collection
)
from numbers import Number

import votelib.convert
import votelib.util
import votelib.component.divisor
import votelib.component.quota
import votelib.evaluate.core
from votelib.candidate import Candidate, Constituency
from votelib.persist import simple_serialization

INF = float('inf')


@simple_serialization
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


@simple_serialization
class VotesPerSeat:
    """Award seats for each N votes cast for each candidate.

    This is an old and simple system that was used e.g. in pre-war Germany
    [#wrstag]_. It divides the number of votes a pre-specified constant and
    rounds to give the appropriate number of seats. It is also used as an
    auxiliary evaluator in some other systems with fixed quota.

    :param votes_per_seat: Number of votes required for the candidate to
        obtain a single seat.
    :param rounding: A rounding mode from the *decimal* Python library. The
        default option is to round down, which is the most frequent case,
        but this evaluator allows to specify a different method as well.
    :param accept_equal: If False, whenever the number of votes is exactly
        divisible by *votes_per_seat*, award one less seat.

    .. [#wrstag] "Reichstag (Weimarer Republik): Wahlsystem", Wikipedia.
        https://de.wikipedia.org/wiki/Reichstag_(Weimarer_Republik)#Wahlsystem
    """
    def __init__(self,
                 votes_per_seat: int,
                 rounding: str = decimal.ROUND_DOWN,
                 accept_equal: bool = True,
                 ):
        self.votes_per_seat = votes_per_seat
        self.rounding = rounding
        self.accept_equal = accept_equal

    def evaluate(self,
                 votes: Dict[Candidate, int],
                 prev_gains: Dict[Candidate, int] = {},
                 max_seats: Dict[Candidate, int] = {},
                 ) -> Dict[Candidate, int]:
        calc_entitlement = self._get_entitlement_computer(sum(votes.values()))
        out = {}
        for cand, n_votes in votes.items():
            entitlement = calc_entitlement(n_votes)
            if not self.accept_equal and entitlement > 0:
                if entitlement * self.votes_per_seat == n_votes:
                    entitlement -= 1
            entitlement = min(entitlement, max_seats.get(cand, INF))
            entitlement -= prev_gains.get(cand, 0)
            if entitlement:
                out[cand] = entitlement
        return out

    def _get_entitlement_computer(self,
                                  total_votes: Number,
                                  ) -> Callable[[int], int]:
        is_fractional = (
            (isinstance(total_votes, int) or isinstance(total_votes, Fraction))
            and (
                isinstance(self.votes_per_seat, int)
                or isinstance(self.votes_per_seat, Fraction)
            )
        )
        if is_fractional and self.rounding == decimal.ROUND_DOWN:
            return self._fractional_entitlement
        else:
            return self._decimal_entitlement

    def _fractional_entitlement(self, n_votes: int) -> int:
        return int(Fraction(n_votes, self.votes_per_seat))

    def _decimal_entitlement(self, n_votes: int) -> int:
        with decimal.localcontext() as context:
            context.rounding = self.rounding
            vps = decimal.Decimal(self.votes_per_seat)
            return int(round(decimal.Decimal(n_votes) / vps, 0))


@simple_serialization
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
        can be referenced by string name from the
        :mod:`votelib.component.quota` module.
    :param accept_equal: Whether to consider the candidate elected when
        their votes exactly equal the quota.
    '''
    def __init__(self,
                 quota_function: Union[
                     str, Callable[[int, int], Number]
                 ] = 'droop',
                 accept_equal: bool = True,
                 ):
        self.quota_function = votelib.component.quota.construct(quota_function)
        self.accept_equal = accept_equal

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
        qval = self.quota_function(
            sum(votes.values()), n_seats
        )
        selected = {}
        n_overshot = 0
        overshot_candidates = []
        for candidate, n_votes in votes.items():
            n_prev = prev_gains.get(candidate, 0)
            fulfills_quota = (
                n_votes > qval
                or self.accept_equal and n_votes == qval
            )
            if fulfills_quota:
                n_add_seats = int(Fraction(n_votes, qval)) - n_prev
                if n_add_seats > 0:
                    if n_add_seats + n_prev > max_seats.get(candidate, INF):
                        overshoot = n_add_seats + n_prev
                        n_add_seats -= overshoot
                        n_overshot += overshoot
                        overshot_candidates.append(candidate)
                    selected[candidate] = n_add_seats
        if n_overshot:
            remaining_votes = {
                cand: n_votes for cand, n_votes in votes.items()
                if cand not in overshot_candidates
            }
            total_gained = {
                cand: selected.get(cand, 0) + prev_gains.get(cand, 0)
                for cand in votes
            }
            votelib.util.add_dict_to_dict(selected, self.evaluate(
                remaining_votes,
                n_overshot,
                prev_gains=total_gained,
                max_seats=max_seats
            ))
        return selected


@simple_serialization
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
        can be referenced by string name from the
        :mod:`votelib.component.quota` module.
    '''
    def __init__(self,
                 quota_function: Union[str, Callable[[int, int], Number]],
                 ):
        self.quota_function = votelib.component.quota.construct(quota_function)
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
        gained_prerem = votelib.util.sum_dicts(quota_elected, prev_gains)
        n_for_remainder = n_seats - sum(gained_prerem.values())
        remainders = {
            cand: Fraction(n_votes, quota_number) - gained_prerem.get(cand, 0)
            for cand, n_votes in votes.items()
            if gained_prerem.get(cand, 0) < max_seats.get(cand, INF)
        }
        best = votelib.evaluate.core.get_n_best(remainders, n_for_remainder)
        for candidate in best:
            if candidate in quota_elected:
                quota_elected[candidate] += 1
            else:
                quota_elected[candidate] = 1
        return quota_elected


@simple_serialization
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
        functions can be referenced by string name from the
        :mod:`votelib.component.divisor` module.
    '''
    def __init__(self,
                 divisor_function: Union[
                     str, Callable[[int], Number]
                 ] = 'd_hondt',
                 ):
        self.divisor_function = votelib.component.divisor.construct(
            divisor_function
        )

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
        candidates, quotients = [
            list(x) for x in zip(*votelib.util.sorted_votes(
                quotient_dict, descending=False
            ))
        ]
        rem_seats = n_seats - sum(totals.values())
        while rem_seats > 0 and quotients:
            n_elect = 1
            max_q = quotients[-1]
            while n_elect < len(quotients) and quotients[-n_elect-1] == max_q:
                n_elect += 1
            to_elect = candidates[-n_elect:]
            if n_elect > rem_seats:
                to_elect = [votelib.evaluate.core.Tie(to_elect)] * rem_seats
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


@simple_serialization
class BiproportionalEvaluator:
    '''Allocate seats biproportionally to parties and constituencies.

    Biproportional apportionment is a method to provide proportional election
    results in two dimensions - constituencies and parties (candidates).
    It works by computing the proportional result using a highest averages
    method along one dimension (here: parties) and then iteratively updating it
    until proportionality is also reached for constituencies, in a process that
    somehow resembles iterative proportional fitting (IPF) but for integer
    values.

    There are two main biproportional apportionment algorithms - alternate
    scaling (AS), which is known to be faster in initial stages but also to
    stall in some corner cases, and tie-and-transfer (TT), which is slower but
    robust. Here, tie-and-transfer (TT) is implemented as described in [#puk]_.

    So far, the only studied variant of biproportional apportionment uses
    highest averages methods, but usually in an alternative specification by
    rounding rules (also called signpost sequences). These rounding rules have
    only been found for D'Hondt and Sainte-Laguë divisors; for other divisors,
    the implementation is missing yet.

    :param divisor_function: A callable producing the divisor from the number
        of seats awarded to the contestant so far, in the same form accepted
        by :class:`HighestAverages`.
    :param apportioner: An optional distribution evaluator to allocate seats to
        constituencies according to the total numbers of votes cast in each.
        Can also be an integer stating the uniformly valid number of seats for
        each constituency, or a dictionary giving the numbers per constituency.
        If None, the number of seats must be specified to :meth:`evaluate`,
        or the highest averages evaluator defined by *divisor_function* is
        used.
    :param signpost_q: The signpost function subtraction constant, which
        defines the rounding. For D'Hondt and Sainte-Laguë divisors, this is
        automatically determined; for other divisors, it must be specified
        manually.

    .. [#puk] "Chapter 15. Double-Proportional Divisor Methods:
        Technicalities", F. Pukelsheim. In: *Proportional Representation*,
        DOI ``10.1007/978-3-319-64707-4_15``.
    '''

    SIGNPOST_QS: Dict[str, Union[int, Fraction]] = {
        'd_hondt': 0,
        'sainte_lague': Fraction(1, 2),
    }

    def __init__(self,
                 divisor_function: Union[
                     str, Callable[[int], Number]
                 ] = 'd_hondt',
                 apportioner: Union[
                     votelib.evaluate.core.Distributor,
                     Dict[Constituency, int],
                     int,
                     None
                 ] = None,
                 signpost_q: Optional[Union[int, Fraction]] = None,
                 ):
        self.divisor_function = votelib.component.divisor.construct(
            divisor_function
        )
        if signpost_q is None:
            signpost_q = self._extract_signpost_q(self.divisor_function)
        self.signpost_q = signpost_q
        self.apportioner = apportioner
        self._eval = HighestAverages(self.divisor_function)

    def _extract_signpost_q(self,
                            fx: Callable[[int], Number],
                            ) -> Union[int, Fraction]:
        '''Determine the signpost subtraction constant from the divisor.'''
        value = self.SIGNPOST_QS.get(fx.__name__, NotImplemented)
        if value is NotImplemented:
            raise NotImplementedError(
                f'signpost q not known for {fx.__name__}, give it explicitly'
            )
        return value

    def evaluate(self,
                 votes: Dict[Constituency, Dict[Candidate, int]],
                 n_seats: Union[int, Dict[Constituency, int]],
                 ) -> Dict[Constituency, Dict[Candidate, int]]:
        '''Distribute seats biproportionally.

        :param votes: Simple votes per constituency to be evaluated.
        :param n_seats: Number of seats to be filled, either in total or by
            constituency.
        '''
        # Initial result, proportional by parties only.
        # All subsequent modifications preserve this proportionality.
        result = self._initial_solution(votes, n_seats)
        tgt_district_seats = votelib.evaluate.core.apportion(
            votes, n_seats,
            self.apportioner if self.apportioner is not None else self._eval,
        )
        # Initial coefficients (inverse divisors) for parties and districts.
        # These are modified by the tie-and-transfer algorithm.
        district_coefs = {d: 1 for d in votes}
        # Party coefficients are computed to be consistent with the initial
        # party-proportional seat allocation result.
        party_coefs = self._initial_party_coefs(votes, result)
        # Iterate the tie-and-transfer algorithm.
        while True:
            cur_district_seats = votelib.convert.ConstituencyTotals().convert(
                result
            )
            # Get districts that have less or more seats than needed.
            districts_under, districts_over = self._districts_unsat(
                cur_district_seats,
                tgt_district_seats,
            )
            if not (districts_under or districts_over):
                # Biproportionality achieved, terminate.
                return result
            quotients = self._calc_quots(votes, district_coefs, party_coefs)
            # Attempt to find a seat transfer path from a district with higher
            # than proportional seat count to a district with lower than
            # proportional count along cells with tied results while keeping
            # party totals.
            districts_labeled, parties_labeled = self._labeled(
                quotients, result, districts_under, districts_over
            )
            # If any undervalued district was reached by the path,
            districts_under_labeled = list(sorted(
                d for d in districts_under if d in districts_labeled
            ))
            if districts_under_labeled:
                # transfer the seat along that path.
                self._augment_result(
                    result, districts_labeled, parties_labeled,
                    districts_under_labeled[0], districts_over
                )
            else:
                # Otherwise, adjust some district and party coefficients
                # so that more ties are created along which the seats can be
                # transferred.
                adj_coef = self._adj_coef(
                    quotients,
                    result,
                    districts_labeled.keys(),
                    parties_labeled.keys()
                )
                if adj_coef == 0 or adj_coef >= 1:
                    raise votelib.evaluate.core.VotingSystemError(
                        f'invalid adjustment coefficient {adj_coef}'
                    )
                for district in districts_labeled:
                    district_coefs[district] *= adj_coef
                for party in parties_labeled:
                    party_coefs[party] /= adj_coef

    def _augment_result(self,
                        result: Dict[Constituency, Dict[Candidate, int]],
                        districts_labeled: Dict[Constituency, Set[Candidate]],
                        parties_labeled: Dict[Candidate, Set[Constituency]],
                        start_district: Constituency,
                        districts_over: List[Constituency],
                        ) -> None:
        '''Transfer a seat to increase proportionality in result.

        Move one allocated seat to *start_district* along a path determined
        by alternating values in *districts_labeled* and *parties_labeled*
        through alternated additions and subtractions until a seat is
        subtracted from one of *districts_over*, which lowers the flaw count
        (disproportionality) by two seats.
        '''
        aug_path = [start_district]
        cur_source = districts_labeled
        while aug_path[-1] not in districts_over:
            aug_path.append(cur_source[aug_path[-1]].pop())
            if cur_source is parties_labeled:
                cur_source = districts_labeled
            else:
                cur_source = parties_labeled
        for i, ctup in enumerate(zip(aug_path[:-1], aug_path[1:])):
            if i % 2:
                party, district = ctup
                result[district][party] -= 1
                if not result[district][party]:
                    del result[district][party]
            else:
                district, party = ctup
                if party not in result[district]:
                    result[district][party] = 0
                result[district][party] += 1

    def _adj_coef(self,
                  quotients: Dict[Constituency, Dict[Candidate, Fraction]],
                  result: Dict[Constituency, Dict[Candidate, int]],
                  districts_labeled: Collection[Constituency],
                  parties_labeled: Collection[Candidate],
                  ) -> Fraction:
        '''Determine the adjustment coefficient that will create more ties.

        Seats can only be transferred along cells (district-party combinations)
        with a tied result. We aim to find a coefficient to multiply the cell
        quotient values in some columns or rows so that more ties are created.
        '''
        alpha = 0
        beta = INF
        for district, d_quots in quotients.items():
            d_is_labeled = district in districts_labeled
            if parties_labeled or d_is_labeled:
                for party, pd_quot in d_quots.items():
                    if d_is_labeled != (party in parties_labeled):
                        pd_seats = result[district].get(party, 0)
                        pd_signpost = pd_seats - self.signpost_q
                        is_alpha_scalable = (
                            d_is_labeled
                            and party not in parties_labeled
                            and pd_signpost > 0
                        )
                        if is_alpha_scalable:
                            pd_alpha = pd_signpost / pd_quot
                            if pd_alpha > alpha:
                                alpha = pd_alpha
                        is_beta_scalable = (
                            not d_is_labeled
                            and party in parties_labeled
                            and pd_quot > 0
                        )
                        if is_beta_scalable:
                            pd_beta = (pd_signpost + 1) / pd_quot
                            if pd_beta < beta:
                                beta = pd_beta
        return alpha if (alpha >= 1 / beta) else (1 / beta)

    def _labeled(self,
                 quotients: Dict[Constituency, Dict[Candidate, Fraction]],
                 result: Dict[Constituency, Dict[Candidate, int]],
                 districts_under: List[Constituency],
                 districts_over: List[Constituency],
                 ) -> Tuple[
                     Dict[Constituency, Set[Candidate]],
                     Dict[Candidate, Set[Constituency]]
                 ]:
        '''Attempt to find a seat transfer path along tied cells.'''
        all_parties = list(sorted(frozenset(
            p for dqs in quotients.values() for p in dqs.keys()
        )))
        # Start with all districts with higher values than needed.
        labeled_districts = collections.defaultdict(
            set, {d: set() for d in districts_over}
        )
        labeled_parties = collections.defaultdict(set)
        prev_n_labelings = -1
        n_labelings = 0
        # Repeat expanding the paths until a step produces no more labels.
        while prev_n_labelings < n_labelings:
            prev_n_labelings = n_labelings
            for d in labeled_districts:
                for party in all_parties:
                    if party not in labeled_parties:
                        is_downgradable = self._is_downgradable(
                            quotients[d][party],
                            result[d].get(party, 0)
                        )
                        if is_downgradable:
                            labeled_parties[party].add(d)
                            n_labelings += 1
            for party in labeled_parties:
                for d in quotients.keys():
                    if d not in labeled_districts:
                        is_upgradable = self._is_upgradable(
                            quotients[d][party],
                            result[d].get(party, 0)
                        )
                        if is_upgradable:
                            labeled_districts[d].add(party)
                            n_labelings += 1
            # If any district with lower value than needed was reached, the
            # path is complete.
            if any(d in districts_under for d in labeled_districts):
                break
        return labeled_districts, labeled_parties

    def _is_upgradable(self, quotient: Fraction, n_seats: int) -> bool:
        '''Check if the cell contains a tie and a seat can be added.'''
        return (
            int(quotient) == quotient - self.signpost_q
            and n_seats + 1 - self.signpost_q == quotient
        )

    def _is_downgradable(self, quotient: Fraction, n_seats: int) -> bool:
        '''Check if the cell contains a tie and a seat can be subtracted.'''
        return (
            int(quotient) == quotient - self.signpost_q
            and n_seats - self.signpost_q == quotient
            and n_seats >= 1
        )

    def _calc_quots(self,
                    votes: Dict[Constituency, Dict[Candidate, int]],
                    district_coefs: Dict[Constituency, int],
                    party_coefs: Dict[Candidate, Fraction],
                    ) -> Dict[Constituency, Dict[Candidate, Fraction]]:
        '''Calculate fractional seat count apporximators from vote counts
        and coefficients (inverse divisors) in both dimensions.
        '''
        return {
            district: {
                party: n_votes * district_coefs[district] * party_coefs[party]
                for party, n_votes in district_votes.items()
            }
            for district, district_votes in votes.items()
        }

    def _districts_unsat(self,
                         cur_district_seats: Dict[Constituency, int],
                         tgt_district_seats: Dict[Constituency, int],
                         ) -> Tuple[List[Constituency], List[Constituency]]:
        '''Return districts with less and more seats than needed, respectively.

        If both are empty, proportionality is achieved.
        '''
        all_districts = (
            frozenset(cur_district_seats)
            | frozenset(tgt_district_seats)
        )
        under, over = [], []
        for d in all_districts:
            cur_d_seats = cur_district_seats.get(d, 0)
            tgt_d_seats = tgt_district_seats.get(d, 0)
            if cur_d_seats != tgt_d_seats:
                (under if cur_d_seats < tgt_d_seats else over).append(d)
        return under, over

    def _initial_solution(self,
                          votes: Dict[Constituency, Dict[Candidate, int]],
                          n_seats: Union[int, Dict[Constituency, int]],
                          ) -> Dict[Constituency, Dict[Candidate, int]]:
        '''Allocate seats proportionally along the party dimension.'''
        # First, allocate the total seats to parties.
        party_seats = self._eval.evaluate(
            votelib.convert.VoteTotals().convert(votes),
            n_seats if isinstance(n_seats, int) else sum(n_seats.values())
        )
        # Compute initial assignment through evaluation by party (columnwise)
        # to districts.
        solution = {d: {} for d in votes.keys()}
        for party, n_party_seats in party_seats.items():
            party_result = self._eval.evaluate(
                {district: votes[district].get(party, 0)
                 for district in votes},
                n_party_seats
            )
            for district, n_district_party_seats in party_result.items():
                if isinstance(district, votelib.evaluate.core.Tie):
                    # Tie on evaluation start, select an arbitrary district
                    # of the tied.
                    sel_district = list(sorted(district))[0]
                    solution[sel_district].setdefault(party, 0)
                    solution[sel_district][party] += n_district_party_seats
                else:
                    solution[district][party] = n_district_party_seats
        return solution

    def _initial_party_coefs(self,
                             votes: Dict[Constituency, Dict[Candidate, int]],
                             seats: Dict[Constituency, Dict[Candidate, int]],
                             ) -> Dict[Candidate, Fraction]:
        '''Determine initial party coefficients from their votes and seats.

        This is done to transpose the result obtained by conventional
        uniproportional evaluation to the biproportional format that used
        dimensional coefficients (inverse divisors). The initial form thus must
        be consistent with the seat counts awarded to parties by the initial
        evaluation. The coefficients will usually not differ much, only by the
        degree by which the initial solution is disproportional to parties.
        '''
        party_coefs = {}
        for party in votelib.convert.VoteTotals().convert(votes).keys():
            lowcoef = 0
            highcoef = INF
            for district, district_votes in votes.items():
                party_district_n_votes = district_votes.get(party, 0)
                if party_district_n_votes:
                    party_district_n_seats = seats[district].get(party, 0)
                    party_district_lowcoef = Fraction(
                        party_district_n_seats - self.signpost_q,
                        party_district_n_votes
                    )
                    if party_district_lowcoef > lowcoef:
                        lowcoef = party_district_lowcoef
                    party_district_highcoef = Fraction(
                        party_district_n_seats + 1 - self.signpost_q,
                        party_district_n_votes
                    )
                    if party_district_highcoef < highcoef:
                        highcoef = party_district_highcoef
            party_coefs[party] = Fraction(lowcoef + highcoef, 2)
        return party_coefs
