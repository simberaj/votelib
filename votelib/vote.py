'''Vote type specifications and vote validators.

Vote types vary from system to system and are only loosely tied to the method
of evaluation (usually, the richer vote types can be reduced to use simple
evaluators but not vice versa). The following vote types are recognized by
Votelib:

-   **Simple** votes - a voter votes for a single candidate. Represented by the
    candidate object itself.
-   **Approval** votes - a voter selects a number of candidates and votes for
    them equally. Represented by a frozen set of candidate objects.
-   **Ranked** votes - a voter ranks a number of candidates. Represented by a
    tuple of candidate objects or frozen sets of them (to account for possible
    tied rankings).
-   **Score** votes - a voter assigns a score (label) to a number of
    candidates. The scores might either be selected from a predefined set or
    arbitrary numbers from a range.

Voting systems generally require one of the above types and usually impose
additional restrictions such as minimum and maximum number of candidates voted
for or ranked. These restrictions are handled by parameters accepted by the
vote validators.

Vote validators validate individual votes, i.e. the keys of the dictionaries
that should be passed to the evaluators. If a vote is invalid, they raise a
subclass of :class:`VoteError` (or :class:`CandidateError`, if a candidate
contained in the vote is invalid).
Some converter objects wrap these validators and catch these errors to remove
invalid votes, for example.
'''

import abc
from typing import Any, Tuple, FrozenSet, Dict, Union, Optional, Collection
from numbers import Number

import collections

import votelib.candidate
from votelib.candidate import Candidate
from votelib.persist import simple_serialization


class VoteError(Exception, metaclass=abc.ABCMeta):
    '''A vote is invalid given the election rules.'''
    pass


class VoteTypeError(VoteError):
    '''A vote is of an invalid type.

    E.g. ranked votes in place of simple votes.

    :param vtype: Vote type detected as invalid.
    :param expected: Vote type that was expected.
    '''
    def __init__(self, vtype: type, expected: type = None):
        self.vtype = vtype
        self.expected = expected
        message = f'invalid vote type: {vtype}'
        if expected:
            message += f', must be {expected}'
        super().__init__(message)


class VoteMagnitudeError(VoteError):
    '''A vote is too small or too large.

    :param value: Size of the vote that was found to be invalid.
    :param min_value: Minimum value permissible in the context.
    :param max_value: Maximum value permissible in the context.
    :param value_name: Role of the vote size (e.g. number of approval votes,
        number of ranked candidates...)
    '''
    def __init__(self,
                 value: Number,
                 min_value: Optional[Number] = None,
                 max_value: Optional[Number] = None,
                 value_name: str = 'count',
                 ):
        self.value = value
        self.min_value = min_value
        self.max_value = max_value
        message = f'invalid vote {value_name}: {value}'
        if min_value is not None or max_value is not None:
            message += ', must be '
            parts = []
            if min_value is not None:
                message += f'>={min_value}'
            if max_value is not None:
                message += f'<={max_value}'
            message += ', '.join(parts)
        super().__init__(message)


class VoteValueError(VoteError):
    '''An explicitly given vote value is invalid.

    :param value: Value of the vote that is invalid.
    :param candidate: A candidate that the vote was given for. If None, a
        specific candidate could not be pinpointed.
    :param allowed: A spectrum of values that is allowed at the given point.
    '''
    def __init__(self,
                 value: Any,
                 candidate: Optional[Candidate] = None,
                 allowed: Any = None,
                 ):
        self.value = value
        self.candidate = candidate
        self.allowed = allowed
        message = f'invalid vote: {value}'
        if candidate is not None:
            message += f' for candidate {candidate}'
        if allowed is not None:
            message += f', allowed: {allowed}'
        super().__init__(message)


SimpleVoteType = Candidate
ApprovalVoteType = FrozenSet[Candidate]
RankedVoteType = Tuple[Union[Candidate, FrozenSet[Candidate]], ...]
ScoreVoteType = FrozenSet[Tuple[Candidate, Any]]

IntBoundsTupleType = Tuple[Optional[int], Optional[int]]
NumBoundsTupleType = Tuple[Optional[Number], Optional[Number]]


class VoteMagnitudeChecker:
    '''A helper class to check if a value is in a specified range.

    :param bounds: A tuple with lower and upper bounds (inclusive) for the
        value to be checked. None means the respective bound is not checked.
    :param value_name: Name of the value to be checked (included in the error
        message).
    '''
    def __init__(self,
                 bounds: NumBoundsTupleType = (None, None),
                 value_name: str = 'count',
                 ):
        self.min_value, self.max_value = bounds
        self.value_name = value_name
        self._active = self.min_value is not None or self.max_value is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'bounds': [self.min_value, self.max_value],
            'value_name': self.value_name
        }

    def __bool__(self) -> bool:
        '''Return True if the checker contains any constraints to check.'''
        return self._active

    def is_valid(self, value: Number) -> bool:
        '''Return True if the value is within the given range.'''
        return (
            (self.min_value is None or value >= self.min_value)
            and (self.max_value is None or value <= self.max_value)
        )

    def check(self, value: Number) -> None:
        '''Check if the value is within the given range.

        :raises VoteMagnitudeError: If the value is outside the given
            range.
        '''
        if not self.is_valid(value):
            raise VoteMagnitudeError(
                value, self.min_value, self.max_value, self.value_name
            )


class VoteValidator(metaclass=abc.ABCMeta):
    '''Validate that a single vote is valid under the election rules.

    Base class, not intended for direct use.
    '''
    @abc.abstractmethod
    def validate(self, vote: Any) -> None:
        '''Check if the vote satisfies criteria given by the voting system.

        :raises NotImplementedError:
        '''
        raise NotImplementedError


DEFAULT_NOMINATOR = votelib.candidate.BasicNominator()


@simple_serialization
class SimpleVoteValidator:
    '''Validate a simple vote (voting directly for a single candidate).

    The candidate must be a valid atomic candidate object according to the
    nominator object specified.

    :param nominator: Nominator used to check candidates. The default uses only
        technical criteria specified by the :class:`Candidate` class.
    '''
    def __init__(self,
                 nominator: votelib.candidate.Nominator = DEFAULT_NOMINATOR,
                 ):
        self.nominator = nominator

    def validate(self, vote: Candidate) -> None:
        '''Check if the candidate is valid.

        :param vote: Simple vote to be checked.
        :raises CandidateError: If the candidate is invalid.
        '''
        self.nominator.validate(vote)


@simple_serialization
class ApprovalVoteValidator:
    '''Validate an approval vote (voting for a number of candidates equally).

    The vote must be a frozen set containing valid atomic candidates. The
    atomic candidates must not be tuples.

    :param vote_count_bounds: A tuple with lower and upper bounds
        (inclusive) for the number of candidates any vote can contain.
        None means the respective bound is not checked.
        Ignored if count_checker is given.
    :param count_checker: A :class:`VoteMagnitudeChecker` that checks the
        number of candidates any vote can contain.
    :param nominator: Nominator used to check candidates. The default uses the
        technical criteria specified by the :class:`Candidate` class.
    '''
    serialize_params = ['count_checker', 'nominator']

    def __init__(self,
                 vote_count_bounds: IntBoundsTupleType = (None, None),
                 count_checker: Optional[VoteMagnitudeChecker] = None,
                 nominator: votelib.candidate.Nominator = DEFAULT_NOMINATOR,
                 ):
        if count_checker is None:
            count_checker = VoteMagnitudeChecker(vote_count_bounds)
        self.count_checker = count_checker
        self.nominator = nominator

    def validate(self, vote: FrozenSet[Candidate]) -> None:
        '''Check if the approval vote is valid.

        :param vote: Approval vote to be checked.
        :raises VoteTypeError: If the vote is not a frozen set.
        :raises CandidateError: If any of the contained candidates
            is invalid.
        :raises VoteMagnitudeError: If the number of candidates voted
            for is out of allowed bounds.
        '''
        if not isinstance(vote, frozenset):
            raise VoteTypeError(vote, frozenset)
        for item in vote:
            self.nominator.validate(item)
        self.count_checker.check(len(vote))


@simple_serialization
class RankedVoteValidator:
    '''Validate a ranked vote (ranking of a number of candidates).

    The vote must be a tuple of candidates or frozen sets thereof. Usage of
    sets indicates tied rankings, which are not common but allowed in some
    systems.

    :param total_vote_count_bounds: A tuple with lower and upper bounds
        (inclusive) for the number of candidates any vote can rank.
        None means the respective bound is not checked.
        Ignored if total_count_checker is given.
    :param rank_vote_count_bounds: A tuple with lower and upper bounds
        (inclusive) for the number of candidates allowed to share any rank.
        The default settings disallow tied rankings. None means the respective
        bound is not checked. Alternatively, a dictionary can be specified
        that maps ranks (1-indexed) to bound tuples.
        Ignored if rank_vote_count_checkers is given.
    :param total_count_checker: A :class:`VoteMagnitudeChecker` that checks the
        total number of candidates any vote can rank.
    :param rank_vote_count_checkers: A mapping of integer ranks to instances
        of :class:`VoteMagnitudeChecker` to check numbers of candidates
        allowed to share any rank.
    :param nominator: Nominator used to check candidates. The default uses only
        technical criteria specified by the :class:`Candidate` class.
    '''
    serialize_params = [
        'total_count_checker',
        'rank_vote_count_checkers',
        'nominator'
    ]

    def __init__(self,
                 total_vote_count_bounds: IntBoundsTupleType = (None, None),
                 rank_vote_count_bounds: Union[
                     IntBoundsTupleType,
                     Dict[int, IntBoundsTupleType],
                 ] = (1, 1),
                 total_count_checker: Optional[VoteMagnitudeChecker] = None,
                 rank_vote_count_checkers: Optional[
                     Dict[int, VoteMagnitudeChecker]
                 ] = None,
                 nominator: votelib.candidate.Nominator = DEFAULT_NOMINATOR,
                 ):
        if total_count_checker is None:
            total_count_checker = VoteMagnitudeChecker(total_vote_count_bounds)
        self.total_count_checker = total_count_checker
        if rank_vote_count_checkers is None:
            if hasattr(rank_vote_count_bounds, 'items'):
                rank_vote_count_checkers = collections.defaultdict(
                    lambda: VoteMagnitudeChecker((None, None))
                )
                for rank, bounds in rank_vote_count_bounds.items():
                    rank_vote_count_checkers[rank] = VoteMagnitudeChecker(
                        bounds
                    )
            else:
                rank_checker = VoteMagnitudeChecker(rank_vote_count_bounds)
                rank_vote_count_checkers = collections.defaultdict(
                    lambda: rank_checker
                )
        self.rank_vote_count_checkers = rank_vote_count_checkers
        self.nominator = nominator

    def validate(self, vote: RankedVoteType) -> None:
        '''Check if the ranked vote is valid.

        :param vote: Ranked vote to be checked.
        :raises VoteTypeError: If the vote is not a tuple.
        :raises VoteError: If any candidate is specified more than once
            in the ranking.
        :raises CandidateError: If any of the contained candidates
            is invalid.
        :raises VoteMagnitudeError: If the number of candidates (total
            or at particular ranking tier) is out of the specified bounds.
        '''
        if not isinstance(vote, tuple):
            raise VoteTypeError(vote, tuple)
        total_votes = 0
        all_candidates = set()
        for rank_i, item in enumerate(vote):
            if isinstance(item, collections.abc.Set):
                self.rank_vote_count_checkers[rank_i+1].check(len(item))
                all_candidates.update(item)
                total_votes += len(item)
            else:
                all_candidates.add(item)
                total_votes += 1
        self.total_count_checker.check(total_votes)
        if len(all_candidates) < total_votes:
            raise VoteError(f'duplicated candidates: {vote}')
        for cand in all_candidates:
            self.nominator.validate(cand)


class ScoreVoteValidator:
    # parent class for EnumScoreVoteValidator and RangeVoteValidator
    def __init__(self,
                 allowed_scorings: IntBoundsTupleType = (None, None),
                 sum_bounds: Union[
                     NumBoundsTupleType, Dict[int, NumBoundsTupleType]
                 ] = (None, None),
                 n_scorings_checker: Optional[VoteMagnitudeChecker] = None,
                 sum_checkers: Optional[
                     Dict[int, VoteMagnitudeChecker]
                 ] = None,
                 nominator: votelib.candidate.Nominator = DEFAULT_NOMINATOR,
                 ):
        if n_scorings_checker is None:
            n_scorings_checker = VoteMagnitudeChecker(allowed_scorings)
        if sum_checkers is None:
            if hasattr(sum_bounds, 'items'):
                no_sc = VoteMagnitudeChecker((None, None), 'sum')
                sum_checkers = collections.defaultdict(lambda: no_sc)
                for n_scorings, bounds in sum_bounds.items():
                    sum_checkers[n_scorings] = VoteMagnitudeChecker(
                        bounds, 'sum'
                    )
            else:
                default_sc = VoteMagnitudeChecker(sum_bounds, 'sum')
                sum_checkers = collections.defaultdict(lambda: default_sc)
        self.n_scorings_checker = n_scorings_checker
        self.sum_checkers = sum_checkers
        self.nominator = nominator

    def validate(self, vote: ScoreVoteType) -> bool:
        if not isinstance(vote, frozenset):
            raise VoteTypeError(vote, frozenset)
        n_scorings = len(vote)
        self.n_scorings_checker.check(n_scorings)
        for item in vote:
            if not isinstance(item, tuple):
                raise VoteTypeError(item, tuple)
            if not len(item) == 2:
                raise VoteMagnitudeError(
                    len(item), 2, 2, 'scoring pair length'
                )
            self.nominator.validate(item[0])
        sum_checker = self.sum_checkers[n_scorings]
        if sum_checker:
            sum_checker.check(sum(scoring[1] for scoring in vote))


@simple_serialization
class EnumScoreVoteValidator(ScoreVoteValidator):
    '''Validate an enumeration-based score vote.

    An enumeration-based score vote assigns scores from a predefined finite set
    to candidates. It should be represented as a frozen set of doubles
    containing a candidate and the associated score. This variant is the most
    common for score-based voting systems since the voters are usually given
    a predefined finite set of (possibly non-numeric) scores; for true range
    voting where the voters might specify arbitrary score values, use
    :class:`RangeVoteValidator`.

    If numeric scores are used, the usage of exact numeric types (integers,
    fractions, decimals) is encouraged.

    :param score_levels: A collection of allowed scores.
    :param allowed_scorings: A tuple with lower and upper bounds
        (inclusive) for the number of candidates allowed to appear in any
        single vote. None means the respective bound is not checked.
        Ignored if n_scorings_checker is given.
    :param sum_bounds: A tuple with lower and upper bounds
        (inclusive) for the total sum of numeric scores allowed for any
        single vote. None means the respective bound is not checked. You can
        also provide a dictionary that gives different sum bounds for different
        numbers of candidates scored (numbers of candidates scored that do not
        have a corresponding key will not have their sums checked then).
        Ignored if sum_checkers are given.
    :param n_scorings_checker: A :class:`VoteMagnitudeChecker` that checks the
        total number of candidates any vote can score.
    :param sum_checkers: A mapping of integer numbers of scored
        candidates to instances of :class:`VoteMagnitudeChecker` checking the
        allowed total score allocated to all candidates.
    :param nominator: Nominator used to check candidates. The default uses only
        technical criteria specified by the :class:`Candidate` class.
    '''
    serialize_params = [
        'score_levels',
        'n_scorings_checker',
        'sum_checkers',
        'nominator'
    ]

    def __init__(self,
                 score_levels: Collection[Any],
                 allowed_scorings: IntBoundsTupleType = (None, None),
                 sum_bounds: Union[
                     NumBoundsTupleType, Dict[int, NumBoundsTupleType]
                 ] = (None, None),
                 n_scorings_checker: Optional[VoteMagnitudeChecker] = None,
                 sum_checkers: Optional[
                     Dict[int, VoteMagnitudeChecker]
                 ] = None,
                 nominator: votelib.candidate.Nominator = DEFAULT_NOMINATOR,
                 ):
        super().__init__(
            allowed_scorings, sum_bounds,
            n_scorings_checker, sum_checkers,
            nominator
        )
        self.score_levels = list(score_levels)

    def validate(self, vote: ScoreVoteType) -> bool:
        '''Check if the enumeration-based score vote is valid.

        :param vote: Score vote to be checked.
        :raises VoteTypeError: If the vote is not a frozen set.
        :raises CandidateError: If any of the contained candidates
            is invalid.
        :raises VoteMagnitudeError: If the number of candidates scored
            or the total sum of scores is out of the specified bounds, or any
            of the items in the vote is not a tuple pair.
        :raises VoteValueError: If any of the scores is not in the
            predefined set of allowed scores.
        '''
        super().validate(vote)
        for cand, score in vote:
            if score not in self.score_levels:
                raise VoteValueError(score, cand, self.score_levels)


@simple_serialization
class RangeVoteValidator(ScoreVoteValidator):
    '''Validate a range (non-enumerative score) vote.

    An range vote assigns scores from a predefined interval to candidates.
    It should be represented as a frozen set of doubles
    containing a candidate and the associated score. This variant is mostly
    theoretical since most systems only allow choice from a finite set of
    scores; for that variant, use :class:`EnumScoreVoteValidator`.

    The usage of exact numeric types (integers, fractions, decimals) for scores
    is encouraged.

    :param range: A tuple with lower and upper bounds
        (inclusive) for any single score value. None means the respective bound
        is not checked.
    :param allowed_scorings: A tuple with lower and upper bounds
        (inclusive) for the number of candidates allowed to appear in any
        single vote. None means the respective bound is not checked.
        Ignored if n_scorings_checker is given.
    :param sum_bounds: A tuple with lower and upper bounds
        (inclusive) for the total sum of numeric scores allowed for any
        single vote. None means the respective bound is not checked.
        Ignored if sum_checkers are given.
    :param n_scorings_checker: A :class:`VoteMagnitudeChecker` that checks the
        total number of candidates any vote can score.
    :param sum_checkers: A mapping of integer numbers of scored
        candidates to instances of :class:`VoteMagnitudeChecker` checking the
        allowed total score allocated to all candidates.
    :param nominator: Nominator used to check candidates. The default uses only
        technical criteria specified by the :class:`Candidate` class.
    '''
    serialize_params = [
        'range_checker',
        'n_scorings_checker',
        'sum_checkers',
        'nominator'
    ]

    def __init__(self,
                 range: NumBoundsTupleType = (None, None),
                 allowed_scorings: IntBoundsTupleType = (None, None),
                 sum_bounds: Union[
                     NumBoundsTupleType, Dict[int, NumBoundsTupleType]
                 ] = (None, None),
                 range_checker: Optional[VoteMagnitudeChecker] = None,
                 n_scorings_checker: Optional[VoteMagnitudeChecker] = None,
                 sum_checkers: Optional[
                     Dict[int, VoteMagnitudeChecker]
                 ] = None,
                 nominator: votelib.candidate.Nominator = DEFAULT_NOMINATOR,
                 ):
        super().__init__(
            allowed_scorings, sum_bounds,
            n_scorings_checker, sum_checkers,
            nominator
        )
        if range_checker is None:
            range_checker = VoteMagnitudeChecker(range, 'range vote value')
        self.range_checker = range_checker

    def validate(self, vote: ScoreVoteType) -> bool:
        '''Check if the range vote is valid.

        :param vote: Range (score) vote to be checked.
        :raises VoteTypeError: If the vote is not a frozen set.
        :raises CandidateError: If any of the contained candidates
            is invalid.
        :raises VoteMagnitudeError: If the number of candidates scored,
            the total sum of scores or any single score is out of the specified
            bounds, or any of the items in the vote is not a tuple pair.
        '''
        super().validate(vote)
        for cand, score in vote:
            self.range_checker.check(score)


class VoteSubsetter(metaclass=abc.ABCMeta):
    '''Abstract class for vote subsetters.

    Vote subsetters reduce a single vote (object) to a smaller variant in which
    only a specified subset of candidates is featured.
    This is trivial for simple votes but is important to do properly for ranked
    votes.

    Vote subsetters should return None if the vote is to be discarded in the
    subset.

    Subsetted votes are handy in some cases such as tiebreaking. If you need to
    subset an entire voting dictionary, wrap the vote subsetter into an
    :class:`votelib.convert.SubsettedVotes` instance.
    '''
    @abc.abstractmethod
    def subset(self,
               vote: Any,
               subset: Collection[Candidate],
               ) -> Union[Any, None]:
        raise NotImplementedError


@simple_serialization
class SimpleSubsetter:
    '''A subsetter for simple votes.'''

    def subset(self,
               vote: Candidate,
               subset: Collection[Candidate],
               ) -> Union[Candidate, None]:
        '''Return vote if it is in subset, else None.'''
        return vote if vote in subset else None


@simple_serialization
class ApprovalSubsetter:
    '''A subsetter for approval votes.'''

    def subset(self,
               vote: FrozenSet[Candidate],
               subset: Collection[Candidate],
               ) -> FrozenSet[Candidate]:
        '''Return a subset of the approval vote by intersection.

        :returns: An intersection of the vote with the candidate subset.
        '''
        return vote.intersection(subset)


@simple_serialization
class RankedSubsetter:
    '''A subsetter for ranked votes.'''
    # TODO: implement keeping ranks as skipped

    def subset(self,
               vote: RankedVoteType,
               subset: Collection[Candidate],
               ) -> RankedVoteType:
        '''Return a ranked vote ranking only the candidates in the subset.

        Ranks that contain only candidates outside the subset are removed and
        the list is shortened. Shared ranks that only have one of their
        candidates in the subset are converted to simple ranks.

        :returns: A ranked vote ranking only the candidates in the subset.
        '''
        sub_ranking = []
        for rank in vote:
            if isinstance(rank, collections.abc.Set):
                sub_rank = rank.intersection(subset)
                if sub_rank:
                    if len(sub_rank) == 1:
                        sub_ranking.append(next(iter(sub_rank)))
                    else:
                        sub_ranking.append(sub_rank)
            elif rank in subset:
                sub_ranking.append(rank)
        return tuple(sub_ranking)


@simple_serialization
class ScoreSubsetter:
    '''A subsetter for score votes.'''

    def subset(self,
               vote: ScoreVoteType,
               subset: Collection[Candidate],
               ) -> ScoreVoteType:
        '''Return a score vote scoring only the candidates in the subset.

        Scores for candidates outside the subset are removed.

        :returns: A score vote scoring only the candidates in the subset.
        '''
        sub_score = set()
        for cand, score in vote:
            if cand in subset:
                sub_score.add((cand, score))
        return frozenset(sub_score)
