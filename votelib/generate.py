"""Generate votes for voting system simulations.

The generators implemented here mostly produce score votes since those are
the most general type. For other types, convert the result using converters:

-   To get ranked votes from score votes, use
    :class:`votelib.convert.ScoreToRankedVotes`.
-   To get simple votes from score votes, use
    :class:`votelib.convert.ScoreToRankedVotes`
    and :class:`votelib.convert.RankedToFirstPreference`
    (wrapped in :class:`votelib.convert.Chain`).
-   To get approval votes over a threshold, use
    :class:`votelib.convert.ScoreToApprovalVotesThreshold`.
"""

import sys
import abc
import math
import string
import operator
import collections
import random
from numbers import Number
from typing import Any, Optional, List, Tuple, Dict, Union, Iterable

import votelib.vote
import votelib.convert
from votelib.candidate import Candidate


class Sampler(metaclass=abc.ABCMeta):
    """A generic sampler interface."""
    n_dims: int

    def sample(self,
               n: int,
               n_dims: Optional[int] = None,
               ) -> Iterable[Tuple[float, ...]]:
        raise NotImplementedError


class DistributionSampler(Sampler):
    """Sample points from the issue or score space by specifying a distribution.

    Uses a statistical probability distribution to produce randomly located
    points within the issue space or score space of given dimensionality.
    The distributions are taken from Python's *random* module by referencing
    the names of the generating functions.

    The outputs from this sampler need to be fed into
    :class:`IssueSpaceGenerator` to produce votes or specify candidate
    positions or into :class:`ScoreSpaceGenerator` to be converted to candidate
    scorings directly.

    Any superfluous keyword arguments are passed to the generating function
    from the random module. If no keyword arguments are given but are required
    (i.e. the distribution parameters need to be specified), for some
    distributions (uniform, gauss, triangular, beta), defaults are specified
    in this class and automatically used if necessary.

    :param distribution: The name of the distribution to use. Must refer to a
        name of a function in Python stdlib random module that produces random
        floats.
    :param n_dims: Dimensionality of the issue or score space to sample from.
    """
    DEFAULT_PARAMS: Dict[str, Dict[str, Union[Number, Tuple[Number, ...]]]] = {
        'gauss': {'mu': 0, 'sigma': 1},
        'uniform': {'a': 0, 'b': 1},
        'triangular': {'low': 0, 'high': 1, 'mode': .5},
        'beta': {'alpha': 2, 'beta': 2},
    }

    def __init__(self,
                 distribution: str = 'gauss',
                 n_dims: Optional[int] = None,
                 **kwargs):
        self.distro_fx = getattr(random, distribution)
        if not kwargs and distribution in self.DEFAULT_PARAMS:
            kwargs = self.DEFAULT_PARAMS[distribution].copy()
        for argname, argval in kwargs.items():
            if hasattr(argval, '__len__') and not isinstance(argval, str):
                if n_dims is None:
                    n_dims = len(argval)
                elif len(argval) != n_dims:
                    raise ValueError(
                        f'sampling {argname} parameter has'
                        f'{len(argval)} dimensions, expected {n_dims}'
                    )
            elif isinstance(argval, Number) and n_dims is not None:
                kwargs[argname] = tuple([argval] * n_dims)
        self.n_dims = n_dims
        if self.n_dims is None:
            self.gener_args = kwargs
        else:
            self.gener_args = tuple(
                {argname: argval[i] for argname, argval in kwargs.items()}
                for i in range(self.n_dims)
            )

    def sample(self,
               n: int,
               n_dims: Optional[int] = None,
               ) -> Iterable[Tuple[float, ...]]:
        """Sample n issue space samples from the distribution."""
        if self.n_dims is None:
            if n_dims is None:
                raise ValueError('need n_dims arg when not set on instance')
            else:
                gener_args = tuple([self.gener_args] * n_dims)
        elif n_dims is not None and n_dims != self.n_dims:
            raise ValueError(f'conflicting n_dims: got {n_dims}'
                             f'but {self.n_dims} set on instance')
        else:
            gener_args = self.gener_args
        for i in range(n):
            yield tuple(self.distro_fx(**kwargs) for kwargs in gener_args)


class BoundedSampler(Sampler):
    """A sampler from a bounded issue space.

    Wraps another sampler to only produce issue space samples that lie within
    a specified multidimensional bounding box. Useful e.g. for the generation
    of Yee diagrams.

    The outputs from this sampler need to be fed into
    :class:`SamplingGenerator` to produce votes or specify candidate positions.

    :param inner: A sampler (e.g. :class:`DistributionSampler`) to wrap.
        Its samples are filtered by the specified bounding box.
    :param bbox: The bounding box to restrict the samples to. First, all
        minima per dimension are specified, then all maxima; for two
        dimensions, this would be ``(minx, miny, maxx, maxy)``. If the inner
        sampler has a defined number of dimensions, it is also possible
        to specify only two numbers, which will be interpreted as the minimum
        and maximum in each dimension.
    """
    def __init__(self, inner: Sampler, bbox: Tuple[Number, ...]):
        self.inner = inner
        if len(bbox) % 2 != 0:
            raise ValueError('bounding box must have an odd number of'
                             f'coordinates, got {len(bbox)}')
        if len(bbox) == 2 and self.inner.n_dims is not None:
            bbox = tuple(
                [bbox[0]] * self.inner.n_dims
                + [bbox[1]] * self.inner.n_dims
            )
        self.bbox = bbox
        self._mins = self.bbox[:len(bbox) // 2]
        self._maxs = self.bbox[len(bbox) // 2:]

    def sample(self, n: int, *args, **kwargs) -> Iterable[Tuple[float, ...]]:
        """A generator to sample n bbox-restricted issue space samples."""
        n_yielded = 0
        for coors in self.inner.sample(sys.maxsize, *args, **kwargs):
            is_in_bbox = (
                all(c >= m for c, m in zip(coors, self._mins))
                and all(c <= m for c, m in zip(coors, self._maxs))
            )
            if is_in_bbox:
                yield coors
                n_yielded += 1
                if n_yielded == n:
                    break


class Generator:
    def generate(self, n: int) -> Dict[Any, int]:
        raise NotImplementedError


class IssueSpaceGenerator:
    """Generate random votes by sampling from a multidimensional issue space.

    The most common paradigm for random vote generation is to spread some
    candidates as points into a multidimensional space (representing their
    opinions or characteristics), then sample voter points from a statistical
    distribution on that space and determine their votes based on their
    proximity to candidates. This class implements this paradigm, delegating
    the sampling to a contained instance of :class:`Sampler`.

    :param candidates: Positions of candidates in the issue space.
        It is also possible to specify just an integer; in that case, the
        candidate positions will be sampled in the same way the voters are.
    :param sampler: How to sample the voter points. Either an object with a
        ``sample()`` method that yields numerical tuples with the correct
        number of dimensions (such as instances of :class:`Sampler`
        subclasses), or a string referencing a name of a statistical
        distribution; in that case, :class:`DistributionSampler` will be
        invoked in two dimensions with default settings on the specified
        distribution. See the class documentation for more on supported
        distributions.
    :param vote_creation: How to transform voter-to-candidate proximities
        in the issue space to score votes:

        -   ``minmax``: The closest candidate is assigned a score of 1, the
            furthest is assigned a score of 0. Score votes are produced.
        -   ``closest``: The closest candidate is voted for. Simple votes are
            produced.
        -   Other transformations are not implemented.

    :param random_state: Seed for the sampler.
    """
    def __init__(self,
                 candidates: Union[int, Dict[Candidate, Tuple[float, ...]]],
                 sampler: Union[str, Sampler] = 'gauss',
                 vote_creation: str = 'minmax',
                 random_state: Optional[int] = None,
                 ):
        if not hasattr(self, vote_creation):
            raise ValueError(f'invalid vote creation method: {vote_creation}')
        self.sampler = _create_sampler(sampler, n_dims=2)
        self.vote_creation = vote_creation
        self.candidates = candidates
        self.random_state = random_state

    def generate(self, n: int) -> Dict[Any, int]:
        """Generate n votes for the candidate setup."""
        if self.random_state is not None:
            random.seed(self.random_state)
        if isinstance(self.candidates, int):
            candidates = self._create_candidates(n=self.candidates)
            n_dims = None
        else:
            candidates = self.candidates
            n_dims = len(next(iter(candidates.values())))

        return self.samples_to_votes(
            self.sampler.sample(n, n_dims=n_dims),
            candidates
        )

    def _create_candidates(self, n: int) -> Dict[Candidate, Tuple[float, ...]]:
        return dict(zip(
            candidate_names(n),
            self.sampler.sample(n=self.candidates)
        ))

    def samples_to_votes(self,
                         sample: Iterable[Tuple[float, ...]],
                         candidates: Dict[Candidate, Tuple[float, ...]],
                         ) -> Dict[Any, int]:
        """Convert issue space samples to votes."""
        vote_create_fx = getattr(self, self.vote_creation)
        votes = collections.defaultdict(int)
        cands = list(candidates.keys())
        cand_coors = list(candidates.values())
        for vote_coor in sample:
            dists = [
                math.hypot(*[v - c for v, c in zip(vote_coor, cand_coor)])
                for cand_coor in cand_coors
            ]
            votes[vote_create_fx(dists, cands)] += 1
        return dict(votes)

    @staticmethod
    def minmax(distances: List[float],
               candidates: List[Candidate],
               ) -> votelib.vote.ScoreVoteType:
        mindist, maxdist = min(distances), max(distances)
        distrange = maxdist - mindist
        return frozenset(zip(
            candidates,
            [(maxdist - dist) / distrange for dist in distances]
        ))

    @staticmethod
    def closest(distances: List[float],
                candidates: List[Candidate],
                ) -> Candidate:
        return min(zip(distances, candidates), key=operator.itemgetter(0))[1]


class ScoreSpaceGenerator:
    """Randomly sample independent candidate scorings.

    This generator is simpler than :class:`IssueSpaceGenerator` since it
    uses the underlying sampler to produce candidate scorings directly.
    The candidate scores are independent of each other.

    Under default settings, this generator produces the *Impartial Culture*
    (IC). By providing different settings for different dimensions
    of the passed sampler, score probabilities for individual candidates
    can be set. An example for two candidates, in which A will, on average,
    get higher scores (mean 0.7) than B (mean 0.3)::

        ScoreSpaceGenerator(
            candidates=['A', 'B'],
            sampler=BoundedSampler(
                DistributionSampler('gauss', mu=(0.7, 0.3), sigma=(1, 1)),
                bbox=(0, 1)
            )
        )

    :param candidates: Candidate objects (most straightforwardly, a list of
        candidate names as strings). It is also possible to specify just an
        integer; in that case, the candidate names are autogenerated as
        uppercase ASCII letters (A, B, C...).
    :param sampler: How to sample the scores. Either an object with a
        ``sample()`` method that yields numerical tuples with the correct
        number of dimensions (such as instances of :class:`Sampler`
        subclasses), or a string referencing a name of a statistical
        distribution; in that case, :class:`DistributionSampler` will be
        invoked with default settings on the specified distribution.
        See the class documentation for more on supported distributions.
    :param round_scores: Whether to round the scores (using round half to even)
        to integers.
    :param random_state: Seed for the sampler.
    """

    def __init__(self,
                 candidates: Union[int, List[Candidate]],
                 sampler: Union[str, Sampler] = 'uniform',
                 round_scores: bool = False,
                 random_state: Optional[int] = None,
                 ):
        if isinstance(candidates, int):
            if candidates > 26:
                raise NotImplementedError
            candidates = list(string.ascii_uppercase[:candidates])
        self.candidates = candidates
        self.sampler = _create_sampler(sampler, n_dims=None)
        self.round_scores = round_scores
        self.random_state = random_state

    def generate(self, n: int) -> Dict[Any, int]:
        """Generate n votes."""
        if self.random_state is not None:
            random.seed(self.random_state)
        n_cands = len(self.candidates)
        votes = collections.defaultdict(int)
        for scoring in self.sampler.sample(n, n_dims=n_cands):
            if self.round_scores:
                scoring = tuple(int(s) for s in scoring)
            votes[frozenset(zip(self.candidates, scoring))] += 1
        return dict(votes)


def _create_sampler(sampler: Union[str, Sampler], n_dims: Union[int, None]):
    if hasattr(sampler, 'sample'):
        return sampler
    else:
        return DistributionSampler(distribution=sampler, n_dims=n_dims)


def candidate_names(n: int) -> List[str]:
    if n > 26:
        raise NotImplementedError
    return list(string.ascii_uppercase[:n])
