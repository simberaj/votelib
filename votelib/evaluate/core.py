'''General voting system evaluator machinery.'''

from __future__ import annotations

import abc
import collections
import inspect
from fractions import Fraction
from typing import Any, List, Dict, Union, Optional
from numbers import Number

import votelib.convert
import votelib.util
import votelib.vote
from votelib.candidate import Candidate, Constituency, Person, ElectionParty
from votelib.persist import simple_serialization


class VotingSystemError(Exception):
    '''A voting system with a valid setup ended up in an unresolvable state.'''
    pass


class Tie(frozenset):
    '''Candidates tied for a seat.

    This object, a subclass of ``frozenset``, is produced by evaluators that do
    not resolve all evaluation ties - for example, a plurality evaluator when
    two or more candidates have an equal number of votes and only some of them
    fit into the number of seats to fill. It can either be presented in the
    result (such as in the case when the given voting system has no tiebreaking
    mechanism) or caught by a tiebreaking evaluator - use :class:`TieBreaking`
    for this.

    This object also provides some special static and class methods to handle
    ties in some basic ways.
    '''
    @classmethod
    def reconcile(cls,
                  elected: List[Union[Candidate, Tie]]
                  ) -> List[Candidate]:
        '''Reconcile multiply tied candidates.

        A placeholder implementation to account for the situation where e.g.
        partial evaluations gave ties but their multiple occurrence in the
        overall result means the ties can be unambiguously resolved.

        :param elected: Selection result - a list of candidates or ties.
        '''
        n_places = collections.defaultdict(float)
        for i, result in enumerate(elected):
            if isinstance(result, cls):
                fraction = Fraction(1, len(result))
                for cand in result:
                    n_places[cand] += fraction
        if any(val >= 1 for val in n_places.values()):
            raise NotImplementedError('tie reconciliation')
            # select tied candidates with n_places over 1, put them in as
            # elected and subset the remaining tie objects
        else:
            # no change
            return elected

    @staticmethod
    def any(result: List[Union[Candidate, Tie]]) -> bool:
        '''Return True if there is any tie in the list, False otherwise.'''
        return any(isinstance(item, Tie) for item in result)

    @staticmethod
    def tie_rankings(rankings: List[List[Candidate]]
                     ) -> List[Union[Candidate, Tie]]:
        '''Form a single ranking out of a list of rankings.

        Produces ties where the rankings do not agree.
        '''
        raise NotImplementedError

    @classmethod
    def break_by_list(cls,
                      elected: List[Union[Candidate, Tie]],
                      breaker: List[Candidate],
                      ) -> List[Candidate]:
        '''Break ties in the elected list according to ordering in breaker.'''
        broken = []
        ties = {}
        for item in elected:
            if isinstance(item, Tie):
                if item in ties:
                    broken.append(ties[item][0])
                    if len(ties[item]) > 1:
                        ties[item] = ties[item][1:]
                    else:
                        del ties[item]
                else:
                    sorted_item = list(sorted(item, key=breaker.index))
                    broken.append(sorted_item[0])
                    ties[item] = sorted_item[1:]
            else:
                broken.append(item)
        return broken


def get_n_best(votes: Dict[Candidate, Number],
               n_seats: int,
               ) -> List[Union[Candidate, Tie]]:
    '''Return n_seats candidates with the highest number of votes.

    Essentially a plurality selection function.
    Produces ties correctly so is useful as a component in many other systems
    that use selection by maximum somewhere in their process.

    :param votes: Mapping of candidates to the number of votes obtained.
    :param n_seats: Number of seats to be filled.
    :returns: A list of top n_seats candidates. If there is a tie, the last
        items will refer to a single Tie object containing the tied candidates.
    '''
    sorted_items = votelib.util.sorted_votes(votes)
    if len(sorted_items) > n_seats:
        # find if there is a tie between the last elected and first unelected
        threshold_votes = sorted_items[n_seats-1][1]
        if sorted_items[n_seats][1] == threshold_votes:
            # tie detected, find all tied
            tied = []
            n_untied = None
            for i, item in enumerate(sorted_items):
                cand, n_votes = item
                if n_votes == threshold_votes:
                    tied.append(cand)
                    if n_untied is None:
                        n_untied = i
            n_tie_places = n_seats - n_untied
            return (
                [item[0] for item in sorted_items[:n_untied]]
                + [Tie(tied)] * n_tie_places
            )
        else:
            return [cand for cand, n_votes in sorted_items[:n_seats]]
    else:
        return [cand for cand, n_votes in sorted_items]


class Evaluator(metaclass=abc.ABCMeta):
    '''Evaluate votes for candidates and allocate seats to them.

    A root abstract base class for all evaluators.
    '''
    @abc.abstractmethod
    def evaluate(self, votes, *args, **kwargs
                 ) -> Union[List[Candidate], Dict[Candidate, int]]:
        '''Evaluate votes for candidates and allocate seats to them.'''
        raise NotImplementedError


class UnknownEvaluator(Evaluator):
    def evaluate(self, votes, *args, **kwargs
                 ) -> Union[List[Candidate], Dict[Candidate, int]]:
        raise NotImplementedError


class Selector(Evaluator):
    '''Elect a given number of candidates.

    Requires a number of seats to determine the number of candidates to elect.
    '''
    @abc.abstractmethod
    def evaluate(self, votes, n_seats, *args, **kwargs) -> List[Candidate]:
        '''Elect n_seats candidates as a list.

        :param votes: Votes of any type.
        :param n_seats: Number of candidates to elect.
        :returns: A list of candidates elected, ordered by magnitude of victory
            (winner first).
        '''
        raise NotImplementedError


class SeatlessSelector(Evaluator):
    '''Elect some candidates.

    Does not allow to pass a number of seats to determine the number of
    candidates to elect; it arises naturally from the votes and other selector
    settings.
    '''
    @abc.abstractmethod
    def evaluate(self, votes, *args, **kwargs) -> List[Candidate]:
        '''Elect a list of candidates without a guaranteed count.

        :param votes: Votes of any type.
        :returns: A list of candidates elected, ordered by magnitude of victory
            (winner first).
        '''
        raise NotImplementedError


class Distributor(Evaluator):
    '''Allocate seats to candidates based on collective preference.'''

    @abc.abstractmethod
    def evaluate(self,
                 votes: Dict[Any, int],
                 n_seats: int,
                 prev_gains: Dict[Candidate, int] = {},
                 max_seats: Dict[Candidate, int] = {},
                 ) -> Dict[Candidate, int]:
        '''Allocate n_seats to candidates as a dictionary.

        :param votes: Votes of any type.
        :param n_seats: Number of seats to allocate to candidates.
        :param prev_gains: Seats gained by the candidate/party in previous
            election rounds.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total (including previous gains).
        :returns: Numbers of seats allocated to respective candidates.
            Candidates with no allocated seats do not appear in the dictionary.
            The ordering of the dictionary is unspecified.
        '''
        raise NotImplementedError


class SeatlessDistributor(Evaluator):
    '''Give seats to candidates based on collective preference.

    The number of seats cannot be specified - it stems from the nature of the
    election system.
    '''

    @abc.abstractmethod
    def evaluate(self,
                 votes: Dict[Any, int],
                 prev_gains: Dict[Candidate, int] = {},
                 max_seats: Dict[Candidate, int] = {},
                 ) -> Dict[Candidate, int]:
        '''Determine numbers of seats given to candidates, as a dictionary.

        :param votes: Votes of any type.
        :param prev_gains: Seats gained by the candidate/party in previous
            election rounds.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total (including previous gains).
        :returns: Numbers of seats allocated to respective candidates.
            Candidates with no allocated seats do not appear in the dictionary.
            The ordering of the dictionary is unspecified.
        '''
        raise NotImplementedError


class SeatCountCalculator:
    def calculate(self,
                  votes: Dict[Any, int],
                  n_seats: int,
                  prev_gains: Dict[Candidate, int],
                  max_seats: Dict[Candidate, int] = {},
                  ) -> int:
        raise NotImplementedError


class OpenListEvaluator(metaclass=abc.ABCMeta):
    '''An abstract class for open list selection evaluators.

    Apart from votes and a number of seats, also requires the specification
    of a list of candidates to serve as the default (party-determined closed
    list) ordering to be overridden by preferential votes for candidates.
    '''
    @abc.abstractmethod
    def evaluate(self,
                 votes: Dict[Any, Number],
                 n_seats: int,
                 candidate_list: List[Candidate],
                 ) -> List[Candidate]:
        '''Elect n_seats candidates as a list.

        :param votes: Votes of any type.
        :param n_seats: Number of candidates to elect.
        :param candidate_list: Candidates in the order determined by their
            party.
        :returns: A list of candidates elected, ordered by magnitude of victory
            (winner first).
        '''
        raise NotImplementedError


@simple_serialization
class MultistageDistributor:
    '''A distribution evaluator with several rounds of awarding seats.

    Useful for several systems, e.g. multi-member proportional systems where
    the first round evaluates the constituencies and the second one evaluates
    the national level.

    :param rounds: Partial distributors. Will be called one by one, with the
        subsequent distributors getting the results of the previous steps as
        previous gains.
    :param depth: Nesting depth of the results. Use numbers larger than 1 when
        the results from the rounds are nested by constituency levels (2 for
        one constituency level, etc.)
    '''

    def __init__(self, rounds: List[Distributor], depth: int = 1):
        self.rounds = rounds
        self.depth = depth

    def evaluate(self,
                 votes: Union[Dict[Any, int], List[Dict[Any, int]]],
                 n_seats: int,
                 prev_gains: Dict[Candidate, int] = {},
                 max_seats: Dict[Candidate, int] = {},
                 ) -> Dict[Candidate, int]:
        '''Evaluate all rounds of the distribution.

        :param votes: Votes to be evaluated. Either a single set to be passed
            to all rounds, or separate sets of votes for each round.
        :param n_seats: Number of seats to be filled in total.
        :param prev_gains: Seats gained by the candidate/party in previous
            election rounds.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total (including previous gains).
        '''
        elected = prev_gains.copy()
        if hasattr(votes, 'items'):
            votes = [votes] * len(self.rounds)
        for stage, stage_votes in zip(self.rounds, votes):
            stage_res = stage.evaluate(
                stage_votes, n_seats, prev_gains=elected, max_seats=max_seats
            )
            self._add_stage_results(elected, stage_res, self.depth)
        return elected

    def _add_stage_results(self, elected, stage_res, depth):
        if depth == 1:
            votelib.util.add_dict_to_dict(elected, stage_res)
        else:
            for constituency in set(elected.keys()) | set(stage_res.keys()):
                self._add_stage_results(
                    elected.setdefault(constituency, {}),
                    stage_res.get(constituency, {}),
                    depth - 1
                )


@simple_serialization
class AdjustedSeatCount:
    '''Distribute an adjusted total number of seats according to votes cast.

    Useful in multi-member proportional systems where overhang seats are
    accounted for, e.g. by leveling.

    :param calculator: A calculator determining how many seats to award. It is
        called with the evaluation parameters (votes, intended number of seats,
        previously gained seats...).
    :param evaluator: A distribution evaluator producing the actual results
        with the adjusted number of seats.
    '''
    def __init__(self,
                 calculator: SeatCountCalculator,
                 evaluator: Distributor,
                 ):
        self.calculator = calculator
        self.evaluator = evaluator

    def evaluate(self,
                 votes: Dict[Any, int],
                 n_seats: int,
                 prev_gains: Dict[Candidate, int],
                 max_seats: Dict[Candidate, int] = {},
                 ) -> Dict[Candidate, int]:
        '''Distribute an adjusted total number of seats.

        :param votes: Votes to be evaluated, of any type accepted by the
            calculator and evaluator.
        :param n_seats: Intended (baseline) number of seats that would arise
            if no adjustment was necessary.
        :param prev_gains: Seats gained by the candidate/party in previous
            election rounds.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total (including previous gains).
        '''
        seat_adj = self.calculator.calculate(
            votes, n_seats, prev_gains=prev_gains, max_seats=max_seats
        )
        return self.evaluator.evaluate(
            votes,
            n_seats + seat_adj,
            prev_gains=prev_gains,
            max_seats=max_seats,
        )


@simple_serialization
class AllowOverhang:
    '''Increase the total number of seats to allow keeping overhang seats.

    Overhang seats arise in multi-member proportional systems when a party
    gains more seats in the first round (usually local and plurality-based)
    than its proportional share according to second round (national,
    proportional party-based) votes. This calculator increases the number
    of seats so that all parties keep their overhang seats while the number of
    seats awarded in the second round stays constant. This leads to parties
    that performed strong in the first round but weak in the second round
    gaining more representation than would be decided by the second round only.

    This is the system used in New Zealand legislative elections.

    :param evaluator: A distribution evaluator producing the proportional
        results from the second round votes to determine which seats are
        overhang. Usually will be the same or very similar to the evaluator
        used in the second round directly.
    '''
    def __init__(self, evaluator: Distributor):
        self.evaluator = evaluator

    def calculate(self,
                  votes: Dict[Any, int],
                  n_seats: int,
                  prev_gains: Dict[Candidate, int],
                  max_seats: Dict[Candidate, int] = {},
                  ) -> int:
        '''Return an adjustment to the total number of seats to allow overhang.

        :param votes: Second round votes to produce the proportional result to
            determine overhang.
        :param n_seats: Intended (baseline) number of seats that would arise
            if no adjustment was necessary. This is passed to the internal
            evaluator to determine the proportional result.
        :param prev_gains: Seats gained in the first round results.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total, including first round results.
        :returns: Zero if no adjustment is necessary, a positive integer if it
            is, amounting to the number of overhang seats detected.
        '''
        prop_result = self.evaluator.evaluate(
            votes, n_seats, max_seats=max_seats,
        )
        adj = 0
        for cand, n_prev_gained in prev_gains.items():
            prop_cand = prop_result.get(cand, 0)
            if prop_cand < n_prev_gained:
                adj += n_prev_gained - prop_cand
        return adj


@simple_serialization
class LevelOverhang:
    '''Increase the total number of seats to proportional, keeping overhang.

    Overhang seats arise in multi-member proportional systems when a party
    gains more seats in the first round (usually local and plurality-based)
    than its proportional share according to second round (national,
    proportional party-based) votes. This calculator increases the number
    of seats so that all parties keep their overhang seats while the overall
    seat counts for parties remain proportional according to the second round
    votes. This means that even when the first round seats end up dominated by
    a single party which has a huge overhang, the other parties still get
    enough *leveling* seats on the national level to maintain a representation
    proportional to their second round votes.

    :param evaluator: A distribution evaluator producing the proportional
        results from the second round votes to determine which seats are
        overhang. Usually will be the same or very similar to the evaluator
        used in the second round directly.
    '''
    def __init__(self, evaluator: Distributor):
        self.evaluator = evaluator

    def calculate(self,
                  votes: Dict[Any, int],
                  n_seats: int,
                  prev_gains: Dict[Candidate, int],
                  max_seats: Dict[Candidate, int] = {},
                  ) -> int:
        '''Return an adjustment to the total number of seats to level overhang.

        :param votes: Second round votes to produce the proportional result to
            determine overhang.
        :param n_seats: Intended (baseline) number of seats that would arise
            if no adjustment was necessary. This is passed to the internal
            evaluator to determine the proportional result.
        :param prev_gains: Seats gained in the first round results.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total, including first round results.
        :returns: Zero if no adjustment is necessary, a positive integer if it
            is, amounting to the sum of overhang seats detected and leveling
            seats required.
        '''
        prop_result = self.evaluator.evaluate(
            votes, n_seats, max_seats=max_seats,
        )
        lowest_allowed = {
            party: max(prev_gains.get(party, 0), prop_gain)
            for party, prop_gain in prop_result.items()
        }
        nonprop_drop = 0
        for party, prev_gain in prev_gains.items():
            if party not in lowest_allowed:
                nonprop_drop += prev_gain
        adj_count = n_seats - nonprop_drop
        pmins = list(lowest_allowed.items())
        while any(prop_result[party] < minimum for party, minimum in pmins):
            adj_count += 1
            prop_result = self.evaluator.evaluate(
                votes, adj_count, max_seats=max_seats,
            )
        return adj_count + nonprop_drop - n_seats


@simple_serialization
class LevelOverhangByConstituency:
    '''Increase the total number of seats to proportional in constituencies.

    This is a variant :class:`LevelOverhang` that works out overhang and
    leveling seats on a constituency level (such as Länder in Germany)
    while still maintaining nationwide proportionality. For a detailed
    description of the overhang leveling process, see that class. This
    variant detects overhang seats for each constituency separately and
    progressively increases the number of leveling seats until proportionality
    is satisfied on a national level.

    This is the system used for the election to German Bundestag.

    :param constituency_evaluator: Evaluates the total party result per
        constituency.
    :param overall_evaluator: Evaluates the total party result nationwide;
        if not given, an aggregate of the constituency result is used
        instead.
    '''
    def __init__(self,
                 constituency_evaluator: Distributor,
                 overall_evaluator: Optional[Distributor] = None,
                 ):
        self.constituency_evaluator = constituency_evaluator
        self.overall_evaluator = overall_evaluator

    def calculate(self,
                  votes: Dict[Constituency, Dict[Any, int]],
                  n_seats: int,
                  prev_gains: Dict[Constituency, Dict[Candidate, int]],
                  max_seats: Dict[Constituency, Dict[Candidate, int]] = {},
                  ) -> int:
        '''Adjust the seat count to level overhang by constituency.

        :param votes: Second round votes to produce the proportional result to
            determine overhang, by constituency.
        :param n_seats: Intended (baseline) number of seats that would arise
            if no adjustment was necessary. This is passed to the internal
            evaluator to determine the proportional result.
        :param prev_gains: Seats gained in the first round results by parties,
            by constituency.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total, including first round results,
            by constituency.
        :returns: Zero if no adjustment is necessary, a positive integer if it
            is, amounting to the sum of overhang seats detected and leveling
            seats required for all constituencies.
        '''
        # Get lowest amount of seats per party and constituency as the maximum
        # of the party's first round count and its theoretical proportional
        # second round result.
        cty_results = self.constituency_evaluator.evaluate(
            votes, n_seats, max_seats=max_seats,
        )
        lowest_allowed = votelib.convert.VoteTotals().convert({
            cty: {
                party: max(prev_gains.get(cty, {}).get(party, 0), prop_seats)
                for party, prop_seats in cty_prop_seats.items()
            }
            for cty, cty_prop_seats in cty_results.items()
        })
        # If any party did not make it to the second round, subtract
        # its first round result from the total number of seats when
        # determining the proportional national result, add them back at the
        # end.
        nonprop_drop = 0
        for cty_gains in prev_gains.values():
            for party, prev_gain in cty_gains.items():
                if party not in lowest_allowed:
                    nonprop_drop += prev_gain
        adj_count = n_seats - nonprop_drop
        overall_evaluator = self.overall_evaluator
        if overall_evaluator:
            party_votes = votelib.convert.VoteTotals().convert(votes)
        else:
            overall_evaluator = votelib.convert.PostConverted(
                self.constituency_evaluator,
                votelib.convert.DistributionMerger()
            )
            party_votes = votes
        # Progressively increase the number of seats until all parties get at
        # least to the minimum given for each of its constituencies.
        prop_result = overall_evaluator.evaluate(
            party_votes, adj_count, max_seats=max_seats
        )
        while any(prop_result.get(party, 0) < minimum
                  for party, minimum in lowest_allowed.items()):
            adj_count += 1
            # Slow since it re-runs the whole proportional evaluation, but
            # I haven't found a general analytical solution finding the overall
            # result directly.
            prop_result = overall_evaluator.evaluate(
                party_votes, adj_count, max_seats=max_seats,
            )
        return adj_count + nonprop_drop - n_seats


@simple_serialization
class PostConverted:
    '''An evaluator whose results are run through a converter.

    Useful when the evaluator is a part of a larger system and its output needs
    to be adapted to it, e.g. in multi-member proportional systems where first
    votes are received by candidates in a selection evaluation but the second
    votes are evaluated by distribution to parties.

    :param evaluator: An evaluator to run.
    :param converter: A converter to apply on the results of the evaluator.
    '''
    def __init__(self, evaluator, converter):
        self.evaluator = evaluator
        self.converter = converter

    def evaluate(self, votes, n_seats=None, *args, **kwargs):
        '''Run the evaluator and return its result, converted.

        All other arguments are passed through to the evaluator.

        :param votes: Votes for the evaluator.
        :param n_seats: Number of seats to allocate by the evaluator.
        '''
        return self.converter.convert(
            self.evaluator.evaluate(votes, n_seats, *args, **kwargs)
        )


@simple_serialization
class PreConverted:
    '''An evaluator whose votes are first run through a converter.

    Useful when the evaluator accepts a different type of votes than the
    actual ballots, where the converter adapts them - e.g. when the votes are
    by constituency but the evaluation is nationwide, or when ranked votes are
    given but a part of the system runs on simple votes.

    :param evaluator: An evaluator to run.
    :param converter: A converter to apply on the votes before passing them to
        the evaluator.
    '''
    def __init__(self, converter, evaluator):
        self.converter = converter
        self.evaluator = evaluator

    def evaluate(self, votes, *args, **kwargs):
        '''Convert the votes by and evaluate them through the evaluator.

        All other arguments are passed through to the evaluator.

        :param votes: Votes to be passed to the converter.
        :param n_seats: Number of seats to allocate by the evaluator.
        '''
        conv_votes = self.converter.convert(votes)
        return self.evaluator.evaluate(conv_votes, *args, **kwargs)


DEFAULT_SUBSETTER = votelib.vote.SimpleSubsetter()


@simple_serialization
class Conditioned:
    '''An evaluator whose votes are pre-selected to exclude some variants.

    Before passing the votes to the main evaluator, an eliminator is evaluated
    first, and only the candidates returned by it are allowed to proceed to the
    main evaluation. This is useful for implementing vote thresholds in
    proportional systems.

    :param evaluator: The main evaluator to produce the results.
    :param eliminator: A selector to determine which variants proceed to the
        main evaluator - only those that are returned by its evaluate method
        do so. It can accept previous gain counts but should not need
        the number of seats (it should be independent of it).
    :param subsetter: A subsetter to subset a vote to just concern the
        candidates returned by the eliminator.
    '''
    def __init__(self,
                 eliminator: SeatlessSelector,
                 evaluator: Evaluator,
                 subsetter: Optional[votelib.vote.SimpleSubsetter] = None,
                 ):
        self.eliminator = eliminator
        self.evaluator = evaluator
        if subsetter is None:
            subsetter = DEFAULT_SUBSETTER
        self.subsetter = subsetter

    def evaluate(self,
                 votes: Dict[Any, int],
                 n_seats: Optional[int] = None,
                 prev_gains: Dict[Candidate, int] = {},
                 **kwargs) -> Union[List[Candidate], Dict[Candidate, int]]:
        '''Evaluate the main evaluator for variants that passed the eliminator.

        All other keyword arguments are passed through to the main evaluator.

        :param votes: Votes to be passed to the main evaluator and eliminator.
        :param n_seats: Number of seats to allocate by the main evaluator.
        :param prev_gains: Numbers of seats previously gained by the candidates
            (e.g. in previous scrutinia). Will be passed to both the main
            evaluator and eliminator, if they accept them (as determined by
            the `accepts_seats` function).
        '''
        if accepts_prev_gains(self.eliminator):
            not_eliminated = self.eliminator.evaluate(
                votes, prev_gains=prev_gains
            )
        else:
            not_eliminated = self.eliminator.evaluate(votes)
        elim_votes = votelib.convert.SubsettedVotes(self.subsetter).convert(
            votes, not_eliminated
        )
        if accepts_prev_gains(self.evaluator):
            kwargs = kwargs.copy()
            kwargs['prev_gains'] = prev_gains
        if accepts_seats(self.evaluator):
            return self.evaluator.evaluate(
                elim_votes, n_seats, **kwargs
            )
        else:
            return self.evaluator.evaluate(elim_votes, **kwargs)


@simple_serialization
class ByConstituency:
    '''Perform constituency-wise evaluation of given system.

    Evaluates and returns the results of the given system separately per each
    constituency it is given votes for. If desired, apportions the seats to
    constituencies according to the total numbers of votes cast in each.

    The selector and vote subsetter perform what the :class:`Conditioned`
    evaluator wrapper would do; however, they are only used after apportionment
    is performed, because that is often defined before candidates are excluded.
    If this is not desired, define the selector and vote subsetter on a
    :class:`Conditioned` wrapper, with the selector wrapped in an additional
    :class:`PreConverted` with :class:`votelib.convert.VoteTotals`,
    and leave the selector undefined here.

    :param evaluator: Evaluator to use on the constituency level.
    :param apportioner: An optional distribution evaluator to allocate seats to
        constituencies according to the total numbers of votes cast in each.
        Can also be an integer stating the uniformly valid number of seats for
        each constituency, or a dictionary giving the numbers per constituency.
        If None, the number of seats must be specified to :meth:`evaluate`.
    :param preselector: An optional selection evaluator to select candidates
        eligible for constituency-wise evaluation. Votes for candidates that
        do not pass its selection will be removed for all constituencies before
        evaluation. If not given, no preselection will be applied.
    :param subsetter: A subsetter to subset a vote to just concern the
        candidates returned by the selector. The default option needs to be
        modified if the votes are more deeply nested.
    '''
    def __init__(self,
                 evaluator: Evaluator,
                 apportioner: Union[
                     Distributor, Dict[Constituency, int], int, None
                 ] = None,
                 preselector: Optional[Selector] = None,
                 subsetter: votelib.vote.VoteSubsetter = DEFAULT_SUBSETTER,
                 ):
        self.evaluator = evaluator
        self.apportioner = apportioner
        self.preselector = preselector
        self.subsetter = subsetter

    def evaluate(self,
                 votes: Dict[Constituency, Dict[Any, int]],
                 n_seats: Union[int, Dict[Constituency, int], None] = None,
                 prev_gains: Dict[Constituency, Dict[Candidate, int]] = {},
                 max_seats: Dict[Constituency, Dict[Candidate, int]] = {},
                 ) -> Union[
                     Dict[Constituency, Dict[Candidate, int]],
                     Dict[Constituency, List[Candidate]],
                 ]:
        '''Return the election results evaluated by constituency.

        :param votes: Votes in the format accepted by the inner evaluator.
        :param n_seats: Number of seats to be allocated:

            -   If ``None``, the apportioner must be a distributor that does
                not accept seat count, and will be called with the total
                numbers of votes cast in each constituency to provide a seat
                count for each constituency.
            -   If an integer and the apportioner is None, regarded as the
                uniform number of seats for each constituency.
            -   If an integer and the apportioner is a distributor, the
                apportioner will be called with this integer as the total
                number of seats to distribute it to the constituencies.
            -   If a dictionary, it will be regarded as the mapping of
                constituencies to their numbers of seats.

        :param prev_gains: Seats gained by the candidate/party in previous
            election rounds in each constituency, to inform the underlying
            evaluator.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total per constituency
            (including previous gains).
        :returns: Results of the evaluation by constituency.
        '''
        apportionment = apportion(
            votes, n_seats, apportioner=self.apportioner
        )
        preselected = self._preselect(votes, n_seats)
        results = {}
        no_value_districts = []
        for district, dvotes in votes.items():
            result = self._evaluate_district(
                dvotes,
                apportionment.get(district),
                preselected,
                prev_gains.get(district, {}),
                max_seats.get(district, {}),
            )
            if result is None:
                no_value_districts.append(district)
            else:
                results[district] = result
        result_type = type(next(iter(results.values())))
        for district in no_value_districts:
            results[district] = result_type()
        return results

    def _evaluate_district(self,
                           votes: Dict[Any, Number],
                           n_seats: int,
                           preselected: List[Candidate],
                           prev_gains: Dict[Candidate, int],
                           max_seats: Dict[Candidate, int],
                           ) -> Union[Dict[Candidate, int], List[Candidate]]:
        if n_seats == 0:
            return None
        else:
            if preselected is not None:
                votes = votelib.convert.SubsettedVotes(self.subsetter).convert(
                    votes, preselected
                )
            if accepts_prev_gains(self.evaluator):
                return self.evaluator.evaluate(
                    votes, n_seats,
                    prev_gains=prev_gains,
                    max_seats=max_seats,
                )
            else:
                return self.evaluator.evaluate(votes, n_seats)

    def _preselect(self, votes, n_seats):
        if self.preselector:
            # select candidates that passed national level conditions
            nat_agg = votelib.convert.VoteTotals()
            nat_votes = nat_agg.convert(votes)
            if accepts_seats(self.preselector):
                return self.preselector.evaluate(nat_votes, n_seats)
            else:
                return self.preselector.evaluate(nat_votes)
        else:
            return None


@simple_serialization
class ByParty:
    '''Distribute overall party results among its constituency lists.

    This is an inverted variant of the :class:`ByConstituency` evaluator.
    Here, the total seat counts for each party are determined by an overall
    evaluator on nationally aggregated votes and an allocation distributor is
    subsequently used to disaggregate the result of the party to
    constituencies.

    Useful for some mixed-member proportional system such as the German
    Bundestag one, where this mechanism is used to distribute overhang leveling
    seats.

    :param overall_evaluator: Evaluator to use on the central (national) level.
    :param allocator: An optional distribution evaluator to allocate seats of
        the party to individual constituencies. If None, the overall evaluator
        is reused. In either case, the allocator must accept simple votes
        for constituencies as candidates.
    :param subsetter: A subsetter according to the vote type used, to
        extract votes for any single party from the overall votes.
    '''
    def __init__(self,
                 overall_evaluator: Distributor,
                 allocator: Optional[Distributor] = None,
                 subsetter: votelib.vote.VoteSubsetter = DEFAULT_SUBSETTER,
                 ):
        self.overall_evaluator = overall_evaluator
        self.allocator = allocator
        self.subsetter = subsetter

    def evaluate(self,
                 votes: Dict[Constituency, Dict[Any, int]],
                 n_seats: Optional[int] = None,
                 prev_gains: Dict[Constituency, Dict[Candidate, int]] = {},
                 max_seats: Dict[Constituency, Dict[Candidate, int]] = {},
                 ) -> Dict[Constituency, Dict[Candidate, int]]:
        '''Return constituency-wise election results evaluated by party.

        :param votes: Votes in the format accepted by the overall evaluator.
            They will be subsetted and aggregated to simple votes for
            constituencies for the allocator evaluation.
        :param n_seats: Number of seats to be allocated. If ``None``, the
            overall evaluator must be seatless.
        :param prev_gains: Seats gained by the candidate/party in previous
            election rounds in each constituency, to inform the allocator.
            Not passed to the overall evaluator.
        :param max_seats: Maximum number of seats that the given
            candidate/party can obtain in total per constituency
            (including previous gains). Not passed to the overall evaluator.
        :returns: Results of the evaluation by constituency.
        '''
        overall_votes = votelib.convert.VoteTotals().convert(votes)
        overall_result = self.overall_evaluator.evaluate(
            overall_votes, n_seats
        )
        allocator = self.allocator
        if allocator is None:
            allocator = self.overall_evaluator
        subset_conv = votelib.convert.SubsettedVotes(self.subsetter)
        results = collections.defaultdict(dict)
        for party, n_party_seats in overall_result.items():
            party_votes = {
                constituency: sum(
                    subset_conv.convert(cvotes, [party]).values()
                ) for constituency, cvotes in votes.items()
            }
            if accepts_prev_gains(allocator):
                party_prev_gains = {
                    constituency: cg[party]
                    for constituency, cg in prev_gains.items() if party in cg
                }
                party_max_seats = {
                    constituency: cm[party]
                    for constituency, cm in max_seats.items() if party in cm
                }
                allocated = allocator.evaluate(
                    party_votes, n_party_seats,
                    prev_gains=party_prev_gains, max_seats=party_max_seats
                )
            else:
                allocated = allocator.evaluate(party_votes, n_party_seats)
            for constituency, cseats in allocated.items():
                results[constituency][party] = cseats
        for constituency in votes.keys():
            if constituency not in results:
                results[constituency] = {}
        return dict(results)


@simple_serialization
class FixedSeatCount:
    accepts_seats = False

    '''An evaluator wrapper that provides a fixed seat count.

    Useful when the seat count for a given system is predefined and constant.
    Then, you do not need to specify it each time you call the evaluator, just
    provide the votes.

    :param evaluator: The evaluator to wrap. Must accept number of seats into
        its evaluate method.
    :param n_seats: The fixed number of seats to provide to the evaluator at
        each call.
    '''
    def __init__(self, evaluator: Evaluator, n_seats: int):
        if not accepts_seats(evaluator):
            raise ValueError(f'cannot wrap seatless evaluator {evaluator}'
                             f'into FixedSeatCount')
        self.evaluator = evaluator
        self.n_seats = n_seats

    def evaluate(self,
                 votes: Dict[Any, int],
                 **kwargs) -> Union[List[Candidate], Dict[Candidate, int]]:
        '''Run the inner evaluator with the predefined number of seats.

        All other keyword parameters are passed through to the wrapped
        evaluator.

        :param votes: Votes of the type accepted by the wrapped evaluator.
        '''
        return self.evaluator.evaluate(
            votes, self.n_seats, **kwargs
        )


@simple_serialization
class PartyListEvaluator:
    '''Evaluate which candidates are elected from party lists.

    Useful to determine the actual representatives elected when the result is
    first evaluated by party. This wrapper evaluates the party-based result
    first, then uses a party list evaluator to determine which candidates from
    the given party lists actually get elected.

    :param party_eval: A distribution evaluator determining the party-based
        election result.
    :param list_eval: An open list evaluator determining which candidates from
        the party list to elect, according to the preferential votes for the
        candidates. Look to the :mod:`votelib.evaluate.openlist` for some
        of these. If None, the party lists are considered closed and the
        elected candidates are taken from the top of each list, without
        considering the list votes.
    :param list_votes_converter: A converter to apply to list votes before
        passing to the list evaluator. The converter should produce a result
        where the candidate votes are grouped by party
        (such as :class:`votelib.convert.GroupVotesByParty`). If not given,
        the list votes are passed unchanged.
    '''
    def __init__(self,
                 party_eval: Distributor,
                 list_eval: Optional[OpenListEvaluator] = None,
                 list_votes_converter: Optional[
                     votelib.convert.Converter
                 ] = None,
                 ):
        self.party_eval = party_eval
        self.list_eval = list_eval
        self.list_votes_converter = list_votes_converter

    def evaluate(self,
                 votes: Dict[Any, Number],
                 n_seats: int, *,
                 party_lists: Dict[ElectionParty, List[Candidate]],
                 list_votes: Dict[ElectionParty, Dict[Any, Number]] = None,
                 **kwargs) -> Dict[ElectionParty, List[Person]]:
        '''Return lists of candidates elected for each party.

        All keyword arguments are passed to the party evaluator.

        :param votes: Votes in the format accepted by the party evaluator.
        :param n_seats: Number of seats to be allocated, to be passed to the
            party evaluator.
        :param party_lists: Lists of candidates for each party in the order
            they were submitted for election.
        :param list_votes: Votes for individual candidates on the party lists.
            If not given, the list evaluator must be None and the party lists
            are considered closed.
        :raises ValueError: If only one of list votes and a list evaluator
            is given.
        '''
        party_result = self.party_eval.evaluate(votes, n_seats, **kwargs)
        if self.list_eval is None:
            # evaluate closed lists
            if list_votes:
                raise ValueError('list votes given but no list evaluator')
            return {
                party: party_lists[party][:n_party_seats]
                for party, n_party_seats in party_result.items()
            }
        else:
            # evaluate open lists
            if not list_votes:
                raise ValueError('no list votes for open list evaluation')
            if self.list_votes_converter:
                list_votes = self.list_votes_converter.convert(list_votes)
            return {
                party: self.list_eval.evaluate(
                    list_votes[party], n_party_seats, party_lists[party]
                )
                for party, n_party_seats in party_result.items()
            }


def accepts_seats(evaluator: Evaluator) -> bool:
    '''Whether evaluator takes seat count as an argument to evaluate().'''
    if hasattr(evaluator, 'accepts_seats'):
        return evaluator.accepts_seats
    else:
        params = inspect.signature(evaluator.evaluate).parameters
        return 'n_seats' in params or _has_generic(params)


def accepts_prev_gains(evaluator: Evaluator) -> bool:
    '''Whether evaluator takes previous gains as an argument to evaluate().'''
    return 'prev_gains' in inspect.signature(evaluator.evaluate).parameters


def _has_generic(params: Dict[str, inspect.Parameter]) -> bool:
    return any(
        param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD
        )
        for param in params.values()
    )


@simple_serialization
class Plurality:
    '''Plurality voting / maximum score evaluator. Elects a list of candidates.

    This encompasses the following voting systems:

    -   *First-past-the-post* (simple plurality, FPTP) for a single seat and
        one vote per person.
    -   *Single non-transferable vote* (SNTV) for multiple seats and one vote
        per voter.
    -   *Plurality-at-large* (multiple non-transferable vote) for
        multiple seats and number of votes equal the number of seats.
    -   *Limited voting* for multiple seats
        and number of votes per voter fixed and less than the number of seats.
    -   *Cumulative voting*, a very similar variant where the number of
        available votes per voter is not tied to the number of candidates
        or seats.
    -   *Approval voting* (AV) for number of available votes per voter equal
        to the number of candidates (but not the more advanced variants
        of approval voting such as proportional approval voting - see the
        :mod:`approval` for that). A multiwinner variant of approval voting
        is sometimes called block approval voting and exhibits very different
        properties. Use :class:`votelib.convert.ApprovalToSimpleVotes` to
        convert approval votes to simple votes accepted by this evaluator.
    -   *Satisfaction approval voting* (SAV), with one arbitrarily splittable
        vote per voter. Use :class:`votelib.convert.ApprovalToSimpleVotes`
        to convert approval votes to simple votes accepted by this evaluator.
    -   *Score voting* after the votes are aggregated by a score vote
        aggregator such as :class:`votelib.convert.ScoreToSimpleVotes`
        (:class:`votelib.evaluate.cardinal.ScoreVoting` can be used instead).

    These voting systems all use this evaluator together with some vote
    conversion or validation criteria.
    '''

    def evaluate(self,
                 votes: Dict[Candidate, Number],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        '''Select candidates by plurality voting.

        In case of a tie, returns :class:`Tie` objects at the end of the list
        of elected candidates.
        There will be as many ties as the number of tied seats;
        each tie will group the tied candidates.

        :param votes: Simple votes (mapping the candidates to a quantity, the
            more the better).
        :param n_seats: Number of candidates to select.
        :returns: A list of elected candidates, sorted in descending order by
            the input votes.
        '''
        return get_n_best(votes, n_seats)


@simple_serialization
class TieBreaking:
    '''Break ties from the main evaluation through a dedicated tiebreaker.

    Runs the main evaluator on the input, and if ties are present in its
    output, runs them through a separately specified selector with the
    original votes subsetted to just those concerning the tied candidates.

    Tiebreakers can be nested if there are more tiebreaking methods with
    different priority. To do so, wrap the core evaluator with the highest
    priority tiebreaker first, and then supply the result as the main evaluator
    to another tiebreaker with lower priority.

    :param main: The main evaluator; might be a selector or a distributor.
    :param tiebreaker: A selector to evaluate ties.
    :param vote_subsetter: A subsetter to subset a vote to just concern the
        tied candidates.
    '''
    def __init__(self,
                 main: Evaluator,
                 tiebreaker: Selector,
                 subsetter: votelib.vote.VoteSubsetter = DEFAULT_SUBSETTER,
                 ):
        self.main = main
        self.tiebreaker = tiebreaker
        self.subsetter = subsetter

    def evaluate(self, votes, *args, **kwargs):
        '''Evaluate the election, breaking ties if they arise.

        Any arguments besides the votes dictionary are passed unchanged to the
        main evaluator.

        :param votes: Votes for the election; will be used to feed the main
            evaluator (and the tiebreaker, after subsetting).
        '''
        main_result = self.main.evaluate(votes, *args, **kwargs)
        subset_conv = votelib.convert.SubsettedVotes(self.subsetter)
        if Tie.any(main_result):
            main_result = main_result.copy()
            ties = self._collect_ties(main_result)
            for tie, n_tied_seats in ties.items():
                sub_votes = subset_conv.convert(votes, tie)
                broken = self.tiebreaker.evaluate(sub_votes, n_tied_seats)
                if hasattr(main_result, 'items'):
                    self._replace_distr_ties(main_result, tie, broken)
                else:
                    self._replace_sel_ties(main_result, tie, broken)
        return main_result

    @staticmethod
    def _collect_ties(result: Union[List[Candidate], Dict[Candidate, int]]
                      ) -> Dict[Tie, int]:
        ties = collections.defaultdict(int)
        if hasattr(result, 'items'):
            for elected, n_seats in result.items():
                if isinstance(elected, Tie):
                    ties[elected] += n_seats
        else:
            for elected in result:
                if isinstance(elected, Tie):
                    ties[elected] += 1
        return ties

    @staticmethod
    def _replace_distr_ties(result: Dict[Candidate, int],
                            tie: Tie,
                            repl: List[Candidate],
                            ) -> None:
        del result[tie]
        for cand in repl:
            result[cand] = result.get(cand, 0) + 1

    @staticmethod
    def _replace_sel_ties(result: List[Candidate],
                          tie: Tie,
                          repl: List[Candidate],
                          ) -> None:
        for cand in repl:
            result[result.index(tie)] = cand


def apportion(votes: Dict[Constituency, Dict[Candidate, Number]],
              n_seats: Union[int, Dict[Constituency, int]],
              apportioner: Union[
                  Distributor, Dict[Constituency, int], int, None
              ] = None,
              ) -> Dict[Constituency, int]:
    if isinstance(apportioner, int):
        # fixed seats for each constituency
        return {c: apportioner for c in votes.keys()}
    elif hasattr(apportioner, 'items'):
        # seats per district are pre-determined statically
        return apportioner
    elif hasattr(n_seats, 'items'):
        # seats per district are determined dynamically outside this
        return n_seats
    elif apportioner:
        constituency_votes = {
            c: sum(c_votes.values()) for c, c_votes in votes.items()
        }
        if isinstance(n_seats, int):
            # apportion seats across districts by number of votes cast
            return apportioner.evaluate(constituency_votes, n_seats)
        elif n_seats is None:
            # apportionment without fixed total
            return apportioner.evaluate(constituency_votes)
        else:
            raise ValueError('unknown apportionment scheme')
    elif isinstance(n_seats, int):
        # delegate to subevaluator
        return {c: n_seats for c in votes.keys()}
    else:
        raise ValueError('invalid apportionment setup')
