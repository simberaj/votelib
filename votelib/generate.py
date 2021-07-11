
import sys
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


class Sampler:
    """A generic sampler interface."""

    def sample(self, n: int) -> Iterable[Tuple[float, ...]]:
        raise NotImplementedError


class DistributionSampler:
    """Sample points from the issue space by specifying a distribution.

    Uses a statistical probability distribution to produce randomly located
    points within the issue space of given dimensionality. The distributions
    are taken from Python's *random* module by referencing the names of the
    generating functions.

    The outputs from this sampler need to be fed into :class:`SamplingGenerator`
    to produce votes or specify candidate positions.

    Any superfluous keyword arguments are passed to the generating function
    from the random module. If no keyword arguments are given but are required
    (i.e. the distribution parameters need to be specified), for some
    distributions (uniform, gauss, triangular, beta), defaults are specified
    in this class and automatically used if necessary.

    :param distribution: The name of the distribution to use. Must refer to a
        name of a function in Python stdlib random module that produces random
        floats.
    :param n_dims: Dimensionality of the issue space to sample from.
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
            if hasattr(argval, '__len__'):
                if n_dims is None:
                    n_dims = len(argval)
                elif len(argval) != n_dims:
                    raise ValueError(f'sampling {argname} parameter has'
                                     f'{len(argval)} dimensions, expected {n_dims}')
            elif isinstance(argval, Number):
                kwargs[argname] = tuple([argval] * n_dims)
        if n_dims is None:
            raise ValueError('need number of sampling dimensions but no'
                             'dimension-bearing parameter specified')
        self.n_dims = n_dims
        self.gener_args = tuple(
            {argname: argval[i] for argname, argval in kwargs.items()}
            for i in range(self.n_dims)
        )

    def sample(self, n: int) -> Iterable[Tuple[float, ...]]:
        """A generator to sample n issue space samples from the distribution."""
        for i in range(n):
            yield tuple(self.distro_fx(**kwargs) for kwargs in self.gener_args)


class BoundedSampler:
    """A sampler from a bounded issue space.

    Wraps another sampler to only produce issue space samples that lie within
    a specified multidimensional bounding box. Useful e.g. for the generation
    of Yee diagrams.

    The outputs from this sampler need to be fed into :class:`SamplingGenerator`
    to produce votes or specify candidate positions.

    :param inner: A sampler (e.g. :class:`DistributionSampler`) to wrap.
        Its samples are filtered by the specified bounding box.
    :param bbox: The bounding box to restrict the samples to. First, all
        minima per dimension are specified, then all maxima; for two dimensions,
        this would be ``(minx, miny, maxx, maxy)``.
    """
    def __init__(self, inner: Sampler, bbox: Tuple[Number, ...]):
        self.inner = inner
        if len(bbox) % 2 != 0:
            raise ValueError('bounding box must have an odd number of'
                             f'coordinates, got {len(bbox)}')
        self.bbox = bbox
        self._mins = self.bbox[:len(bbox) // 2]
        self._maxs = self.bbox[len(bbox) // 2:]

    def sample(self, n: int) -> Iterable[Tuple[float, ...]]:
        """A generator to sample n bbox-restricted issue space samples."""
        n_yielded = 0
        for coors in self.inner.sample(sys.maxsize):
            is_in_bbox = (
                all(c >= m for c, m in zip(coors, self._mins))
                and all(c <= m for c, m in zip(coors, self._maxs))
            )
            if is_in_bbox:
                yield coors
                n_yielded += 1
                if n_yielded == n:
                    break


DEFAULT_SAMPLER = DistributionSampler(n_dims=2)


class SamplingGenerator:
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
        number of dimensions (such as instances of :class:`Sampler` subclasses),
        or a string referencing a name of a statistical distribution; in that
        case, :class:`DistributionSampler` will be invoked in two dimensions
        with default settings on the specified distribution. See the class
        documentation for more on supported distributions.
    :param vote_creation: How to transform voter-to-candidate proximities
        in the issue space to score votes:

        -   ``minmax``: The closest candidate is assigned a score of 1, the
            furthest is assigned a score of 0. Score votes are produced.
        -   ``closest``: The closest candidate is voted for. Simple votes are
            produced.
        -   Other transformations are not implemented.

    :param converter: An optional converter to turn the votes generated by the
        vote creation method into a different type:

        -   To get ranked votes from score votes, use
            :class:`votelib.convert.ScoreToRankedVotes`.
        -   To get simple votes from score votes, use
            :class:`votelib.convert.ScoreToRankedVotes`
            and :class:`votelib.convert.RankedToFirstPreference`
            (wrapped in :class:`votelib.convert.Chain`), or you can use
            ``vote_creation='closest'`` directly.
        -   To get approval votes over a threshold, use
            :class:`votelib.convert.ScoreToApprovalVotesThreshold`.

    :param random_state: Seed for the sampler.
    """
    def __init__(self,
                 candidates: Union[int, Dict[Candidate, Tuple[float, ...]]],
                 sampler: Union[str, Sampler] = 'gauss',
                 vote_creation: str = 'minmax',
                 converter: Optional[votelib.convert.Converter] = None,
                 random_state: Optional[int] = None,
                 ):
        if not hasattr(self, vote_creation):
            raise ValueError(f'invalid vote creation method: {vote_creation}')
        if not hasattr(sampler, 'sample'):
            sampler = DistributionSampler(distribution=sampler, n_dims=2)
        self.sampler = sampler
        self.vote_creation = vote_creation
        self.converter = converter
        self.candidates = candidates
        self.random_state = random_state

    def generate(self, n: int) -> Dict[Any, int]:
        """Generate n votes for the candidate setup."""
        if self.random_state is not None:
            random.seed(self.random_state)
        if isinstance(self.candidates, int):
            candidates = self._create_candidates(n=self.candidates)
        else:
            candidates = self.candidates

        votes = self.samples_to_votes(self.sampler.sample(n), candidates)
        if self.converter is not None:
            return self.converter.convert(votes)
        else:
            return votes

    def _create_candidates(self, n: int) -> Dict[Candidate, Tuple[float, ...]]:
        coors = self.sampler.sample(n=self.candidates)
        if n > 26:
            raise NotImplementedError
        return dict(zip(string.ascii_uppercase, coors))

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
