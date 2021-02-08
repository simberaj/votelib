'''Objects to assign scores to ranks in ranked voting systems such as Borda.

A rank scorer returns a list of numerical scores to be assigned to ranks given
by voters. This is the essence of Borda count system, and rank scorers capture
most of the variations there are in that system.
'''

import abc
from fractions import Fraction
from typing import List, Any
from numbers import Number

from votelib.persist import simple_serialization


def select_padded(sequence: List[Any], n: int, pad_with: Any = 0) -> List[Any]:
    '''Select n leading elements from sequence, padding with pad_with.

    Padding with pad_with is used when sequence is not long enough to select
    n elements.
    '''
    selected = sequence[:n]
    if n > len(selected):
        selected += [pad_with] * (n - len(selected))
    return selected


class RankScorer(metaclass=abc.ABCMeta):
    '''An abstract base class for rank scorers.

    Rank scorers must provide a `scores()` method that returns a list of scores
    based on the number of ranks given. They may also provide a
    `set_n_candidates()` method that sets the total number of candidates
    participating in the election, which might be relevant for computing the
    rank scores. If this method is defined, it must be called before the
    `scores()` method is called first.
    '''
    @abc.abstractmethod
    def scores(self, n_ranked: int) -> List[Number]:
        raise NotImplementedError


@simple_serialization
class Borda(RankScorer):
    '''Borda rank scorer, corresponding to the original Borda count variant.

    Assigns the `base` score to the candidate ranked last, and one point more
    for each higher rank.

    This rank scorer needs to be initialized by the :func:`set_n_candidates()`
    before calling :func:`scores()`.

    :param base: The score to assign to the candidate ranked last. For the
        truly original Borda, this equals to 1; some variants set it to zero,
        and thus set the score for the first rank to the number of candidates
        minus one.
    '''

    def __init__(self, base: int = 1):
        self.base = base
        self._scores = None
        self.n_candidates = None

    def set_n_candidates(self, n_candidates: int) -> None:
        '''Set the total number of candidates that could be ranked.

        This helps to account for rankings that do not rank all candidates.

        :param n_candidates: The total number of candidates that could be
            ranked on any ballot (i.e. the number of candidates participating
            in the election in the particular constituency).
        '''
        self.n_candidates = n_candidates
        top_score = self.n_candidates + self.base - 1
        self._scores = [
            top_score - rank
            for rank in range(self.n_candidates)
        ]

    def get_n_candidates(self) -> int:
        return self.n_candidates

    def scores(self, n_ranked: int) -> List[int]:
        '''Return the scores for the first n_ranked ranks.

        This gives (number of candidates + base - 1 - rank) for ranks running
        from 0 (best rank) to n_ranked.

        :param n_ranked: Number of ranks to be returned. Equal to the length
            of the output list.
        :raises RuntimeError: If the scorer has not been initialized first by
            calling ``set_n_candidates()``.
        '''
        try:
            if n_ranked > self.n_candidates:
                raise ValueError(f'cannot rank {n_ranked} out of maximum'
                                 f' {self.n_candidates} candidates')
            else:
                return select_padded(self._scores, n_ranked)
        except TypeError:
            raise RuntimeError(
                'scorer not initialized, call set_n_candidates() first'
            )


@simple_serialization
class Dowdall(RankScorer):
    '''Dowdall (Nauru) rank scorer.

    Assigns the numbers of the harmonic series (1, 1/2, 1/3...) to
    progressively lower ranks.
    '''

    def scores(self, n_ranked: int) -> List[Fraction]:
        '''Return the scores for the first n_ranked ranks.

        This gives `1 / (rank + 1)` for ranks running
        from 0 (best rank) to n_ranked.

        :param n_ranked: Number of ranks to be returned. Equal to the length
            of the output list.
        '''
        return [Fraction(1, rank + 1) for rank in range(n_ranked)]


@simple_serialization
class Geometric(RankScorer):
    '''A geometric progression rank scorer.

    Assigns the numbers of a chosen inverse geometric progression
    (e.g. 1, 1/2, 1/4... for 2) to progressively lower ranks.

    :param base: Base of the geometric progression.
    '''
    # http://www.geometric-voting.org.uk/index.htm

    def __init__(self, base: int = 2):
        self.base = base

    def scores(self, n_ranked: int) -> List[Fraction]:
        '''Return the scores for the first n_ranked ranks.

        This gives `1 / (2 ** rank)` for ranks running
        from 0 (best rank) to n_ranked.

        :param n_ranked: Number of ranks to be returned. Equal to the length
            of the output list.
        '''
        return [Fraction(1, self.base ** rank) for rank in range(n_ranked)]


@simple_serialization
class ModifiedBorda(RankScorer):
    '''Modified Borda count rank scorer.

    In this system, the score for the highest rank is not constant (as is the
    case for the vanilla Borda count), but is equal to the number of ranked
    candidates; therefore, it encourages voters to rank many candidates.
    '''

    def scores(self, n_ranked: int) -> List[int]:
        '''Return the scores for the first n_ranked ranks.

        This gives `n_ranked - rank` for ranks running
        from 0 (best rank) to n_ranked.

        :param n_ranked: Number of ranks to be returned. Equal to the length
            of the output list.
        '''
        return [n_ranked - rank for rank in range(n_ranked)]


@simple_serialization
class FixedTop(RankScorer):
    '''A rank scorer with fixed score for the top rank.

    Assigns scores progressively decreased by one until hitting zero.

    :param top: The score for the top (best) ranked candidate on the ballot.
    '''

    def __init__(self, top: int):
        self.top = top

    def scores(self, n_ranked: int) -> List[int]:
        '''Return the scores for the first n_ranked ranks.

        This gives `max(top - rank, 0)` for ranks running
        from 0 (best rank) to n_ranked.

        :param n_ranked: Number of ranks to be returned. Equal to the length
            of the output list.
        '''
        return [max(self.top - rank, 0) for rank in range(n_ranked)]


@simple_serialization
class SequenceBased(RankScorer):
    '''A rank scorer with a predetermined sequence of scores.

    This is used in many competitions (Eurovision, Formula One, etc.)

    Assigns scores according to the given sequence until hitting zero, and zero
    scores afterwards.

    :param sequence: The scores for the top candidates on the ballot.
    '''

    def __init__(self, sequence: List[Number]):
        self.sequence = sequence

    def scores(self, n_ranked: int) -> List[Number]:
        '''Return the scores for the first n_ranked ranks.

        This gives values from the initial sequence, then zeros.

        :param n_ranked: Number of ranks to be returned. Equal to the length
            of the output list.
        '''
        return select_padded(self.sequence, n_ranked)
