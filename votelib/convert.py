'''Converters between vote and result formats.

These objects have a `convert()` method that converts between different formats
of votes or election results.
'''

import collections
import statistics
import builtins
import operator
import itertools
import decimal
from fractions import Fraction
from decimal import Decimal
from typing import Any, List, Tuple, Dict, FrozenSet, Union, Callable, \
                   Iterable, Collection
from numbers import Number

import votelib.candidate
import votelib.util
import votelib.vote
from votelib.candidate import \
    Candidate, Constituency, IndividualElectionOption, ElectionParty
from votelib.vote import RankedVoteType, ScoreVoteType
from votelib.component import rankscore
from votelib.persist import simple_serialization


def _subtract_lowest(scores: Dict[Any, int],
                     sorted_scores: List[Any],
                     cutoff: int,
                     ) -> None:
    cut = 0
    for score in sorted_scores:
        if scores[score] <= (cutoff - cut):
            cut += scores[score]
            del scores[score]
        else:
            scores[score] -= (cutoff - cut)
            break


class Converter:
    def convert(self, *args, **kwargs):
        raise NotImplementedError


# Aggregators from more complicated votes to simple magnitudes
@simple_serialization
class ApprovalToSimpleVotes:
    '''Aggregate approval votes to simple votes.

    Aggregate votes for candidate sets (approval votes) to separate votes
    for individual candidates. Useful for example in approval voting.

    :param split: Whether to split the vote power among all the candidates
        in the set (as in satisfaction approval voting) [#wsav]_
        or give full vote to each (as in ordinary approval voting) [#wav]_.

    .. [#wsav] "Satisfaction approval voting", Wikipedia.
        https://en.wikipedia.org/wiki/Satisfaction_approval_voting

    .. [#wav] "Approval voting", Wikipedia.
        https://en.wikipedia.org/wiki/Approval_voting
    '''
    def __init__(self, split: bool = False):
        self.split = split

    def convert(self,
                votes: Dict[FrozenSet[Candidate], int]
                ) -> Dict[Candidate, Number]:
        '''Convert approval votes to simple votes.'''
        agg_votes = collections.defaultdict(int)
        for bulk, n_votes in votes.items():
            if self.split:
                n_votes = Fraction(n_votes, len(bulk))
            for cand in bulk:
                agg_votes[cand] += n_votes
        return dict(agg_votes)


@simple_serialization
class ScoreToSimpleVotes:
    '''Aggregate scores (cardinal votes) to simple votes.

    Useful for score voting (range voting) systems. Note that, if the usual
    central value function such as mean or median are used, this does not
    give scores that could be passed to ordinary magnitude-based evaluators
    since they do not scale with the number of voters.

    This can be used directly in combination with a simple-vote plurality
    evaluator but is also a component in several cardinal vote evaluators.

    The scores can be arbitrary values as long as the aggregation function
    can cope with them, but numeric scores are the most common.

    :param function: A function to aggregate all scores given to a candidate
        to a single score. It can also be specified by name (string); this
        looks into the exact aggregator register in the utility module (which
        reimplements some common aggregation functions to use exact arithmetic,
        such as the mean, which is the default here) and then searches builtin
        functions and the statistics stdlib module namespaces.
    :param unscored_value: Score to give to a candidate that was not assigned
        a score by the voter. None means such ballots will not be considered
        for the candidate. A function can be specified to determine the value
        from all assigned scores (such as assigning the minimum). Builtin
        functions and functions from the statistics stdlib module can be
        specified by their names.
    :param min_count: Minimum count of voter scores for the candidate to be
        considered. Candidates below this threshold will be assigned
        bottom_value.
    :param truncation: Fraction (if lower than 1) or count (if at least 1)
        of lowest and highest scores to disregard before aggregating, to
        stabilize the result. (Both ends are trimmed using this, so the
        number/fraction of scores disregarded is twice the count/fraction).
    :param bottom_value: Value to assign to candidates with less voter scores
        than min_count. This would usually be the lowest possible aggregate
        score.
    '''
    FUNCTION_NAMESPACES = [
        statistics,
        builtins,
    ]

    def __init__(self,
                 function: Union[
                     Callable[[List[Any]], Any], str
                 ] = 'mean',
                 unscored_value: Union[
                     Callable[[List[Any]], Any], Any, None
                 ] = None,
                 min_count: int = 0,
                 truncation: Number = 0,
                 bottom_value: Any = 0,
                 ):
        self.function = self._get_function(function)
        if isinstance(unscored_value, str):
            unscored_value = self._get_function(unscored_value)
        self.unscored_value = unscored_value
        self.min_count = min_count
        self.truncation = truncation
        self.bottom_value = bottom_value

    def _get_function(self, fdef) -> Callable[[List[Number]], Number]:
        if isinstance(fdef, str):
            if fdef in votelib.util.EXACT_AGGREGATORS:
                return votelib.util.EXACT_AGGREGATORS[fdef]
            for namespace in self.FUNCTION_NAMESPACES:
                if hasattr(namespace, fdef):
                    return getattr(namespace, fdef)
            raise ValueError(f'unknown function definition: {fdef!r}')
        else:
            if not hasattr(fdef, '__call__'):
                raise ValueError(f'not a callable function: {fdef!r}')
            return fdef

    def convert(self,
                votes: Dict[ScoreVoteType, int],
                ) -> Dict[Candidate, Any]:
        '''Convert score votes to simple votes.

        :param votes: Uncorrected score votes.
        :returns: A mapping from candidates to their aggregate scores.
        '''
        return self.aggregate(self.corrected_scores(votes))

    def corrected_scores(self,
                         votes: Dict[ScoreVoteType, int],
                         ) -> Dict[Candidate, Dict[Any, int]]:
        '''Correct score votes to an intermediate format.

        This forms the first part of the conversion (the second is
        :meth:`aggregate`) and is exposed independently to allow for repeated
        aggregation which is used by some score voting evaluators.

        The correction adds values for unscored candidates, assigns a fixed
        value to candidates with too few votes, and potentially truncates the
        scores to enable truncated central values.

        :param votes: Uncorrected score votes.
        :returns: Corrected scores in a nested dictionary (candidates are
            mapped to dictionaries mapping score values to numbers of their
            occurrences).
        '''
        scores = collections.defaultdict(lambda: collections.defaultdict(int))
        for one_vote, n in votes.items():
            for cand, score in one_vote:
                scores[cand][score] += n
        n_votes = sum(votes.values())
        return {
            cand: self._correct_candidate_scores(cscores, n_votes)
            for cand, cscores in scores.items()
        }

    def aggregate(self,
                  scores: Dict[Candidate, Dict[Any, int]]
                  ) -> Dict[Candidate, Any]:
        '''Aggregate corrected score votes to scores per candidate.

        :param scores: Corrected scores in an intermediate format of a nested
            dict (candidates are mapped to dictionaries mapping score values to
            numbers of their occurrences).
        :returns: A mapping from candidates to their aggregate scores.
        '''
        return {
            cand: self.aggregate_one(cscores)
            for cand, cscores in scores.items()
        }

    def aggregate_one(self, cscores: Dict[Any, int]) -> Any:
        '''Aggregate corrected scores for a candidate to a single score.'''
        return self.function([
            score for score, count in cscores.items() for i in range(count)
        ])

    def _correct_candidate_scores(self,
                                  scores: Dict[Any, int],
                                  n_votes: int = None,
                                  ) -> Dict[Any, int]:
        n_scores = sum(scores.values())
        if n_scores < self.min_count:
            return {self.bottom_value: self.min_count}
        copied = False
        if n_votes is not None and self.unscored_value is not None:
            if hasattr(self.unscored_value, '__call__'):
                unscored = self.unscored_value([
                    score for score, count in scores.items()
                        for i in range(count)    # noqa: E131
                ])
            else:
                unscored = self.unscored_value
            if not copied:
                scores = scores.copy()
                copied = True
            scores[unscored] = n_votes - n_scores + scores.get(unscored, 0)
        if self.truncation > 0:
            if not copied:
                scores = scores.copy()
                copied = True
            if self.truncation < 1:
                cutoff = int(
                    (n_votes if n_votes else n_scores) * self.truncation
                )
            else:
                cutoff = self.truncation
            sorted_scores = list(sorted(scores.keys()))
            _subtract_lowest(scores, sorted_scores, cutoff)
            _subtract_lowest(scores, sorted_scores[::-1], cutoff)
        return scores


@simple_serialization
class RankedToFirstPreference:
    '''Aggregate ranked votes to simple votes, taking each voter's first choice.

    This is useful to determine the plurality winner in ranked choice voting
    systems.
    '''
    def convert(self,
                votes: Dict[RankedVoteType, int],
                ) -> Dict[Candidate, int]:
        '''Convert ranked votes to simple votes by taking first choices.'''
        output = collections.defaultdict(int)
        for ranking, n_votes in votes.items():
            if ranking:
                output[ranking[0]] += n_votes
        return dict(output)


@simple_serialization
class RankedToPresenceCounts:
    '''Count candidate occurrences in ranked votes regardless of rank.

    Returns simple votes. The candidates will be ordered in the order of the
    ranked votes - first, all candidates appearing on any first rank will be
    listed in the order of their first such votes, then all candidates
    that appear on second and lower ranks only, etc.
    '''
    def convert(self,
                votes: Dict[RankedVoteType, Number],
                ) -> Dict[Candidate, Number]:
        '''Convert ranked votes to simple votes, disregarding rank.'''
        output = collections.defaultdict(int)
        for cand, rank_i, n_votes in votelib.util.all_rankings(votes):
            output[cand] += votes
        return dict(output)


@simple_serialization
class RankedToApprovalVotes:
    '''Convert ranked votes to approval votes (disregarding rank).

    Returns approval (set) votes by lumping together all candidates ranked on
    a particular ballot regardless of rank.
    '''
    def convert(self,
                votes: Dict[RankedVoteType, Number],
                ) -> Dict[FrozenSet[Candidate], Number]:
        approval = {}
        for ranking, n_votes in votes.items():
            vote_cands = set()
            for positioned in ranking:
                if isinstance(positioned, collections.abc.Set):
                    vote_cands.update(positioned)
                else:
                    vote_cands.add(positioned)
            approval[frozenset(vote_cands)] = n_votes
        return approval


@simple_serialization
class RankedToPositionalVotes:
    '''Aggregate ranked votes to simple votes.

    Useful for Borda count systems. Assigns a score to each rank and then
    sums the scores.

    :param rank_scorer: A rank scorer that determines which score to assign to
        which rank through its `scores()` method.
        You can use any object that honors the interface of
        :class:`rankscore.RankScorer`, such as any of its subclasses.
    :param unranked_scoring: What score to assign to candidates not ranked by
        the given voter. So far only the `'zero'` option, which assigns a score
        of zero, is supported.
    '''
    def __init__(self,
                 rank_scorer: rankscore.RankScorer,
                 unranked_scoring: str = 'zero',
                 ):
        self.rank_scorer = rank_scorer
        self.unranked_scoring = unranked_scoring
        if self.unranked_scoring != 'zero':
            raise NotImplementedError

    def convert(self,
                votes: Dict[RankedVoteType, int],
                ) -> Dict[Candidate, Number]:
        '''Convert ranked votes to simple votes by scoring their positions.'''
        all_candidates = votelib.util.all_ranked_candidates(votes)
        if hasattr(self.rank_scorer, 'set_n_candidates'):
            self.rank_scorer.set_n_candidates(len(all_candidates))
        rank_scores = collections.defaultdict(list)
        agg_votes = {cand: 0 for cand in all_candidates}
        for ranked, n_votes in votes.items():
            n_ranks = len(ranked)
            this_rank_scores = rank_scores.setdefault(
                n_ranks,
                self.rank_scorer.scores(n_ranks)
            )
            for rank, positioned in enumerate(ranked):
                score = this_rank_scores[rank] * n_votes
                if hasattr(positioned, '__len__'):
                    for cand in positioned:
                        agg_votes[cand] += score
                else:
                    agg_votes[positioned] += score
        return votelib.util.descending_dict(agg_votes)


@simple_serialization
class RankedToCondorcetVotes:
    '''Aggregate ranked votes to counts of pairwise wins.

    Basic component for Condorcet methods. For each ballot that ranks a pair
    of candidates in a given order, adds one to the count of the first
    candidate over the second.

    :param unranked_at_bottom: Whether to consider candidates not ranked on a
        ballot as being ranked last. If False, these candidates are not
        considered (the voter is assumed not to have any preferences there).
    '''
    def __init__(self, unranked_at_bottom: bool = True):
        self.unranked_at_bottom = unranked_at_bottom

    def convert(self,
                votes: Dict[RankedVoteType, int],
                ) -> Dict[Tuple[Candidate, Candidate], int]:
        '''Convert ranked votes to counts of pairwise wins.'''
        all_cands = frozenset(votelib.util.all_ranked_candidates(votes))
        counts = collections.defaultdict(int)
        for ranking, n_votes in votes.items():
            is_bulk = []
            ranked = []
            for item in ranking:
                is_item_bulk = isinstance(item, collections.abc.Set)
                is_bulk.append(is_item_bulk)
                if is_item_bulk:
                    ranked.extend(item)
                else:
                    ranked.append(item)
            if self.unranked_at_bottom:
                unranked = all_cands.difference(ranked)
            for i, upper_item in enumerate(ranking):
                if not is_bulk[i]:
                    upper_item = (upper_item, )
                for upper_cand in upper_item:
                    for j, lower_item in enumerate(ranking[i+1:]):
                        if not is_bulk[i+1+j]:
                            lower_item = (lower_item, )
                        for lower_cand in lower_item:
                            counts[upper_cand, lower_cand] += n_votes
                    if self.unranked_at_bottom:
                        for unranked_cand in unranked:
                            counts[upper_cand, unranked_cand] += n_votes
        return dict(counts)


@simple_serialization
class ScoreToRankedVotes:
    '''Convert score votes to ranked votes.

    This is useful to employ ranked voting methods for run-off in some score
    voting systems to reduce their susceptibility to tactical voting (e.g. STAR
    voting).

    :param unscored_value: Score to give to a candidate that was not assigned
        a score by the voter. None means such ballots will not be considered
        for the candidate. A callable is not accepted.
    '''
    def __init__(self,
                 unscored_value: Union[str, Number, None] = None,
                 ):
        if hasattr(unscored_value, '__call__'):
            raise ValueError('callables are not accepted')
        self.unscored_value = unscored_value

    def convert(self,
                votes: Dict[ScoreVoteType, int],
                ) -> Dict[RankedVoteType, int]:
        '''Convert score votes to ranked votes.

        :param votes: Score votes.
        '''
        all_candidates = frozenset(
            cand for vote, n_votes in votes.items() for cand, score in vote
        )
        return {
            self.convert_one(vote, all_candidates): n_votes
            for vote, n_votes in votes.items()
        }

    def convert_one(self,
                    vote: ScoreVoteType,
                    all_candidates: FrozenSet[Candidate],
                    ) -> RankedVoteType:
        key_fx = operator.itemgetter(1)
        if self.unscored_value is not None:
            unscored = all_candidates.difference(cand for cand, score in vote)
            if unscored:
                vote |= ((cand, self.unscored_value) for cand in unscored)
        sorted_iter = sorted(vote, key=key_fx)
        ranked = []
        for score, tuple_iter in itertools.groupby(sorted_iter, key=key_fx):
            tuples = list(tuple_iter)
            if len(tuples) == 1:
                ranked.append(tuples[0][0])
            else:
                ranked.append(frozenset(t[0] for t in tuples))
        return tuple(reversed(ranked))


# Inverters
@simple_serialization
class InvertedSimpleVotes:
    '''Vote inverter to represent negative simple votes.

    In some voting systems, voters vote against rather than for candidates.
    '''
    def convert(self,
                votes: Dict[Candidate, Number]
                ) -> Dict[Candidate, Number]:
        '''Invert the count signs of single votes.'''
        return {cand: -n_votes for cand, n_votes in votes.items()}


# Individual/party converters
@simple_serialization
class IndividualToPartyVotes:
    '''Aggregate votes for individual candidates to votes for their parties.

    Useful for cases where votes are received by candidates but also considered
    by party, e.g. in panachage systems.

    :param mapper: A mapper object specifying the mapping from individuals to
        parties.
    '''
    DEFAULT_MAPPER = votelib.candidate.IndividualToPartyMapper()

    def __init__(self,
                 mapper: votelib.candidate.IndividualToPartyMapper = DEFAULT_MAPPER
                 ):
        self.mapper = mapper

    def convert(self,
                votes: Dict[IndividualElectionOption, int],
                ) -> Dict[ElectionParty, int]:
        '''Convert individual simple votes to party-based simple votes.'''
        aggregated = collections.defaultdict(int)
        for cand, n in votes.items():
            party = self.mapper(cand)
            if party is not votelib.candidate.IndividualToPartyMapper.IGNORE:
                aggregated[party] += n
        return dict(aggregated)


@simple_serialization
class IndividualToPartyResult:
    '''Aggregate individual elected candidates to results for their parties.

    Useful to determine party results in systems (or parts thereof) where
    party affiliation is not taken into account during evaluation,
    e.g. in STV systems (Ireland) or in mixed-member proportional systems
    (Germany) to determine the number of directly elected candidates
    before party-based seats are allocated.

    :param mapper: A mapper object specifying the mapping from individuals to
        parties.
    '''
    DEFAULT_MAPPER = votelib.candidate.IndividualToPartyMapper()

    def __init__(self,
                 mapper: votelib.candidate.IndividualToPartyMapper = DEFAULT_MAPPER
                 ):
        self.mapper = mapper

    def convert(self,
                results: List[IndividualElectionOption],
                ) -> Dict[ElectionParty, int]:
        '''Convert individual selection results to party-based counts.'''
        aggregated = collections.defaultdict(int)
        for cand in results:
            party = self.mapper(cand)
            if party is not votelib.candidate.IndividualToPartyMapper.IGNORE:
                aggregated[party] += 1
        return dict(aggregated)


@simple_serialization
class GroupVotesByParty:
    '''Group individual simple votes to a dict nested by their parties.

    Useful when the votes are provided for individual candidates and should be
    retained as such, but are evaluated per-party (e.g. in panachage
    open-list systems, where this can combine list votes for party list
    evaluation).

    :param mapper: A mapper object specifying the mapping from individuals to
        parties.
    '''

    DEFAULT_MAPPER = votelib.candidate.IndividualToPartyMapper()

    def __init__(self,
                 mapper: votelib.candidate.IndividualToPartyMapper = DEFAULT_MAPPER
                 ):
        self.mapper = mapper

    def convert(self,
                votes: Dict[IndividualElectionOption, int],
                ) -> Dict[ElectionParty, Dict[IndividualElectionOption, int]]:
        '''Group individual simple votes by individuals' parties.'''
        aggregated = {}
        for cand, n in votes.items():
            party = self.mapper(cand)
            if party is not votelib.candidate.IndividualToPartyMapper.IGNORE:
                aggregated.setdefault(party, {})[cand] = n
        return aggregated


@simple_serialization
class SelectionToDistribution:
    '''Adapt selection results to distribution (seat count) format.

    This can be used e.g. for majority bonus systems where the largest party
    gets a predetermined amount of additional reserved seats, or in
    mixed-member proportional systems to determine party-wise results of the
    constituency round.

    :param amount: How many votes to attribute to each winner of the selection.
    '''
    def __init__(self, amount: Number = 1):
        self.amount = amount

    def convert(self, elected: List[Candidate]) -> Dict[Candidate, int]:
        '''Convert selection results to distribution results.'''
        return {cand: self.amount for cand in elected}


@simple_serialization
class MergedSelections:
    '''Compile candidates elected in constituencies to a single result list.

    The candidates are ordered by their positions in the district-wide result
    lists.

    Useful e.g. in mixed-member proportional systems to list all candidates
    elected in constituencies.
    '''
    def convert(self, elected: Union[
                    Dict[Constituency, List[Candidate]],
                    List[List[Candidate]]
                ]) -> List[Candidate]:
        '''Compile constituency election results to a single result list.

        :param elected: Partial selection results in a list or dictionary;
            if a dictionary, its keys are ignored and values treated as a list.
        '''
        # TODO: reconcile ties when merging?
        if hasattr(elected, 'values'):
            elected = elected.values()
        ranks = self._get_ranks(elected)
        return list(sorted(
            ranks.keys(),
            key=(lambda cand: (-len(ranks[cand]), -sum(ranks[cand])))
        ))

    def _get_ranks(self, elected: Iterable[List[Candidate]]):
        ranks = {}
        for clist in elected:
            max_rank = len(clist) - 1
            for i, cand in enumerate(clist):
                if cand not in ranks:
                    ranks[cand] = []
                ranks[cand].append(max_rank - i)
        return ranks


@simple_serialization
class MergedDistributions:
    '''Merge many distribution election results into one.

    Aggregates distribution election results from a list or dictionary of
    partial results (e.g. by constituency) into a single candidate-wise
    dictionary.
    Neither reconciles ties nor preserves result ordering.

    Use :class:`VoteTotals` to aggregate votes.
    '''
    def convert(self, elected: Union[
                    Dict[Constituency, Dict[Candidate, int]],
                    List[Dict[Candidate, int]]
                ]) -> Dict[Candidate, int]:
        '''Aggregate many distribution election results into one.

        :param elected: Partial distribution election results in a list or
            dictionary; if a dictionary, its keys are ignored and values
            treated as a list.
        '''
        # TODO: reconcile ties when merging? keep result ordering?
        if hasattr(elected, 'values'):
            elected = elected.values()
        merged = {}
        for cdict in elected:
            votelib.util.add_dict_to_dict(merged, cdict)
        return merged


# Constituency-defined vote aggregators by party or district
@simple_serialization
class VoteTotals:
    '''Count total votes/results for each candidate in all constituencies.

    If votes of other type than simple are given, counts the totals of
    votes. Use :class:`MergedDistributions` to aggregate distribution election
    results.
    '''
    def convert(self,
                votes: Dict[Constituency, Dict[Any, int]],
                ) -> Dict[Any, int]:
        '''Count total votes for each candidate in all constituencies.

        :param votes: Votes of any type.
        '''
        all_districts = {}
        for dvotes in votes.values():
            votelib.util.add_dict_to_dict(all_districts, dvotes)
        return all_districts


@simple_serialization
class ConstituencyTotals:
    '''Count total votes (or results) for all candidates in each constituency.

    Accepts any type of votes or distribution election results.

    Useful for apportionment of seats to districts.
    '''
    def convert(self,
                votes: Dict[Constituency, Dict[Any, int]],
                ) -> Dict[Constituency, int]:
        '''Return total votes for all candidates in each constituency.

        :param votes: Votes of any type, or distribution election results.
        '''
        return {
            district: sum(dvotes.values())
            for district, dvotes in votes.items()
        }


@simple_serialization
class PartyTotals:
    '''Count total votes for parties from grouped votes for its candidates.

    Accepts any type of votes or distribution election results.

    Useful for evaluating party-based results in systems where votes can be
    received by individual candidates (panachage) if the results are already
    grouped by party in a nested dictionary, e.g. after applying
    :class:`GroupVotesByParty`.
    '''
    def convert(self,
                votes: Dict[ElectionParty, Dict[Any, int]],
                ) -> Dict[ElectionParty, int]:
        '''Return total votes for all candidates of each party.

        :param votes: Votes of any type, or distribution election results.
        '''
        return {
            party: sum(pvotes.values())
            for party, pvotes in votes.items()
        }


@simple_serialization
class ByConstituency:
    '''Perform conversion for each constituency votes/results separately.

    :param converter: A converter to wrap. Will be called to convert votes (or
        results) for each constituency separately.
    '''
    def __init__(self, converter: Converter):
        self.converter = converter

    def convert(self,
                values: Dict[Constituency, Dict[Any, Any]],
                ) -> Dict[Constituency, Dict[Any, Any]]:
        '''Convert the votes/results for each constituency.

        :param values: Mapping of constituencies to votes or results. The
            keys of this dictionary will be transferred unchanged to the
            result, with their values converted by the wrapped converter.
        '''
        return {
            district: self.converter.convert(dvalues)
            for district, dvalues in values.items()
        }


@simple_serialization
class InvalidVoteEliminator:
    '''Only allow through votes that are declared valid by a given validator.

    Calls the `validate()` method of the validator for each of the keys of the
    input dictionary; if an :class:`vote.VoteError` is raised, does not
    include the vote in the output.

    :param validator: The vote validator to use. Look for some in the
        :mod:`vote` module.
    '''
    def __init__(self, validator: votelib.vote.VoteValidator):
        self.validator = validator

    def convert(self, votes: Dict[Any, int]) -> Dict[Any, int]:
        '''Copy the votes dictionary, removing invalid votes.

        If no invalid votes are detected, does not make a copy.
        '''
        to_remove = []
        for one_vote in votes.keys():
            try:
                self.validator.validate(one_vote)
            except votelib.vote.VoteError:
                to_remove.append(one_vote)
        if to_remove:
            votes = votes.copy()
            for one_vote in to_remove:
                del votes[one_vote]
        return votes


@simple_serialization
class RoundedVotes:
    '''Round vote counts to the given number of decimal digits.

    In some systems, rounding of fractional values to a given number of digits
    is specified (e.g. Scottish STV). This rounds vote counts of any vote type
    to this number of decimals.

    :param decimals: Number of digits to round to. Negative values are not
        accepted.
    :param round_method: A rounding method accepted by Python's ``decimal``
        module.
    :raises ValueError: If an invalid number of decimal digits is given.
    '''
    def __init__(self, decimals: int, round_method=decimal.ROUND_HALF_UP):
        self.decimals = decimals
        self.round_method = round_method
        self._rounder = self._construct_rounder()

    def _exponent(self):
        if self.decimals < 0:
            raise ValueError(f'invalid number of decimals: {self.decimals}')
        elif self.decimals == 0:
            return Decimal('1')
        elif self.decimals == 1:
            return Decimal('.1')
        else:
            return Decimal('.' + ('0' * (self.decimals - 1)) + '1')

    def _construct_rounder(self):
        decprec = self._exponent()

        # using default arguments to speed up lookups
        def _rounder(val, round_prec=decprec, round_method=self.round_method):
            if isinstance(val, Fraction):
                decimal_val = Decimal(val.numerator) / Decimal(val.denominator)
            else:
                decimal_val = Decimal(val)
            return decimal_val.quantize(round_prec, round_method)

        return _rounder

    def convert(self, votes: Dict[Any, Number]) -> Dict[Any, Decimal]:
        '''Round all vote counts to the specified number of votes.

        The vote counts must be convertible to :class:`Decimal`
        (:class:`Fraction` and any types accepted by the decimal constructor
        are supported).

        :param votes: Votes whose counts should be rounded.
        '''
        return {
            vote: self._rounder(n_votes) for vote, n_votes in votes.items()
        }


@simple_serialization
class SubsettedVotes:
    '''Subset the votes to only concern a subset of candidates.

    A wrapper over :class:`vote.VoteSubsetter` that takes the entire vote count
    dictionary, not just a single vote object (key).
    Useful when some candidates should be excluded because they do not pass
    an electoral threshold, or when evaluating ties.

    :param vote_subsetter: A vote subsetter that turns a single vote object
        (key) into a vote object that only concerns the specified candidates,
        with other candidates removed.
    '''
    DEFAULT_SUBSETTER = votelib.vote.SimpleSubsetter()

    def __init__(self,
                 vote_subsetter: votelib.vote.VoteSubsetter = DEFAULT_SUBSETTER,
                 depth: int = 0,
                 ):
        self.vote_subsetter = vote_subsetter
        self.depth = depth

    def convert(self,
                votes: Dict[Any, Number],
                subset: Collection[Candidate],
                ) -> Dict[Any, Number]:
        '''Subset the votes to only concern a subset of candidates.

        :param votes: Votes to be subsetted. Their type should be in accordance
            with the wrapped vote subsetter.
        :param subset: The only candidates that should be contained in the
            output.
        '''
        return self._convert(votes, subset, depth=self.depth)

    def _convert(self,
                 votes: Dict[Any, Number],
                 subset: Collection[Candidate],
                 depth: int,
                 ) -> Dict[Any, Number]:
        if depth == 0:
            sub = collections.defaultdict(int)
            for full_vote, n_votes in votes.items():
                sub_vote = self.vote_subsetter.subset(full_vote, subset)
                if sub_vote is not None:
                    sub[sub_vote] += n_votes
            return dict(sub)
        else:
            return {
                nester: self._convert(nested, subset, depth - 1)
                for nester, nested in votes.items()
            }


RANKED_TO_SIMPLE: List[type] = [
    RankedToPositionalVotes,
    RankedToFirstPreference,
    RankedToPresenceCounts,
]
