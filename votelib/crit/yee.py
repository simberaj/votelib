"""Create and plot Yee diagrams outlining single-winner voting system quality.

Yee diagrams distribute some candidates in a 2D issue space and then evaluate
a selected voting system on a grid over that space. In each cell of the grid,
an election is simulated with voter preferences proportional to the distances
of the grid cell to the candidate positions. Use :func:`diagram` to produce
this.

A good voting system's Yee diagram should closely approximate a Voronoi diagram
over the candidates. (A Voronoi diagram would assign each point of space to the
closest candidate.) [#yee]_ This can be produced by calling :func:`voronoi`.

The Yee diagram here is represented by a 2D list as a rectangular lattice
covering the 0-1 in both dimensions.

.. [#yee] Warren D. Smith. "Yee Pictures", Range Voting, 2007.
    https://rangevoting.org/IEVS/Pictures.html
"""

import math
import random
from typing import Tuple, List, Dict, Optional

try:
    import matplotlib.cm
    import matplotlib.colors
    import matplotlib.patches
    import matplotlib.pyplot as plt
except ImportError:
    matplotlib = None
    plt = None

import votelib.convert
import votelib.evaluate
import votelib.evaluate.auxiliary
import votelib.evaluate.cardinal
import votelib.generate
import votelib.vote
from votelib.candidate import Candidate


DEFAULT_SHAPE = (200, 200)


def diagram(evaluator: votelib.evaluate.Selector,
            candidates: Dict[Candidate, Tuple[float, float]],
            shape: Tuple[int, int] = DEFAULT_SHAPE,
            n_votes: int = 1000,
            random_state: Optional[int] = None,
            **kwargs) -> List[List[Candidate]]:
    """Produce a Yee diagram for the evaluator.

    Any superfluous keyword arguments are passed on to the vote generation
    sampler using :func:`sampler`.

    :param evaluator: The voting system evaluator for which to construct
        a Yee diagram.
    :param candidates: Candidate positions in the 2D issue space. The
        coordinates should both be between 0 and 1.
    :param shape: Number of cells along each dimension of the issue space.
        Enlarging this gives more detail but increases computing time.
    :param n_votes: Number of voters to consider in each simulated election.
        Lowering this will speed up the computation but may give unstable
        results.
    :param random_state: Seed for the vote generator.
    """
    # Ensure that we always have a decisive winner by breaking ties randomly.
    full_eval = votelib.evaluate.TieBreaking(
        evaluator,
        tiebreaker=votelib.evaluate.PreConverted(
            votelib.convert.ScoreToSimpleVotes(),
            votelib.evaluate.auxiliary.Sortitor(),
        ),
        subsetter=votelib.vote.ScoreSubsetter(),
    )
    if random_state is not None:
        random.seed(random_state)
    diag = []
    ys, xs = _diag_coors(shape)
    for y in ys:
        row = []
        for x in xs:
            votes = votelib.generate.IssueSpaceGenerator(
                candidates,
                sampler=sampler(x, y, **kwargs),
            ).generate(n_votes)
            result = full_eval.evaluate(votes, n_seats=1)
            row.append(result[0])
        diag.append(row)
    return diag


def _diag_coors(shape: Tuple[int, int]) -> Tuple[List[float], List[float]]:
    y_size_elem, x_size_elem = [1 / s for s in shape]
    return (
        [(i + .5) * y_size_elem for i in range(shape[0])],
        [(i + .5) * x_size_elem for i in range(shape[1])]
    )


def sampler(x: float,
            y: float,
            sigma: Tuple[float, float] = (.25, .25),
            ) -> votelib.generate.BoundedSampler:
    """Create a vote generation sampler for a given Yee issue space point.

    Gives a Gaussian sampler centered on the x-y point with a standard
    deviation given by sigma.
    """
    return bounded_sampler(votelib.generate.DistributionSampler(
        distribution='gauss', mu=(x, y), sigma=sigma
    ))


def bounded_sampler(samp: votelib.generate.Sampler
                    ) -> votelib.generate.BoundedSampler:
    """Bound a vote sampler to the Yee diagram bounding box."""
    return votelib.generate.BoundedSampler(samp, (0, 0, 1, 1))


def voronoi(candidates: Dict[Candidate, Tuple[float, float]],
            shape: Tuple[int, int] = DEFAULT_SHAPE,
            ) -> List[List[Candidate]]:
    """Produce a Voronoi Yee diagram for the given candidates.

    This gives the ideal Yee diagram that good voting systems should be
    close to.

    :param candidates: Candidate positions in the 2D issue space. The
        coordinates should both be between 0 and 1.
    :param shape: Number of cells along each dimension of the issue space.
        Enlarging this gives more detail but increases computing time.
    """
    ys, xs = _diag_coors(shape)
    return [
        [min(
            candidates.items(),
            key=lambda item: math.hypot(item[1][0] - x, item[1][1] - y)
        )[0] for x in xs]
        for y in ys
    ]


def voronoi_matches(results: List[List[Candidate]],
                    candidates: Dict[Candidate, Tuple[float, float]],
                    ) -> List[List[bool]]:
    """Give a 2D boolean mask how a Yee diagram matches a Voronoi diagram.

    :param results: A Yee diagram of winning candidates.
    :param candidates: Candidate positions in the 2D issue space. The
        coordinates should both be between 0 and 1.
    """
    shape = (len(results), len(results[0]))
    voronoi_diagram = voronoi(candidates, shape=shape)
    return [
        [results[i][j] == voronoi_diagram[i][j] for j in range(shape[1])]
        for i in range(shape[0])
    ]


def voronoi_conformity(results: List[List[Candidate]],
                       candidates: Dict[Candidate, Tuple[float, float]],
                       ) -> float:
    """Calculate the percentage of how a Yee diagram matches a Voronoi diagram.

    :param results: A Yee diagram of winning candidates.
    :param candidates: Candidate positions in the 2D issue space. The
        coordinates should both be between 0 and 1.
    """
    shape = (len(results), len(results[0]))
    matches = voronoi_matches(results, candidates)
    return sum(m for row in matches for m in row) / (shape[0] * shape[1])


def circular_candidates(n: int,
                        r: float = .25,
                        center: Tuple[float, float] = (.5, .5),
                        ) -> Dict[Candidate, Tuple[float, float]]:
    """Generate Yee diagram candidate issue space positions in a circle.

    :param n: Number of candidates. The candidates will be evenly spaced
        along the circumference of the circle.
    :param r: Radius of the circle.
    :param center: Center of the circle coordinates.
    """
    unit_angle = 2 * math.pi / n
    cx, cy = center
    return dict(zip(votelib.generate.candidate_names(n), (
        (
            cx + r * math.cos(unit_angle * i),
            cy + r * math.sin(unit_angle * i)
        ) for i in range(n)
    )))


def random_candidates(n: int,
                      cand_sampler: Optional[votelib.generate.Sampler] = None,
                      ) -> Dict[Candidate, Tuple[float, ...]]:
    """Generate Yee diagram candidate issue space positions randomly.

    :param n: Number of candidates.
    :param cand_sampler: A sampler to generate the candidate positions.
        The default (None) is to sample from a uniform 2D distribution, i.e.
        all points of the diagram are equally probable.
    """
    if cand_sampler is None:
        cand_sampler = votelib.generate.DistributionSampler(
            'uniform', n_dims=2
        )
    cand_sampler = bounded_sampler(cand_sampler)
    return dict(zip(
        votelib.generate.candidate_names(n),
        cand_sampler.sample(n)
    ))


def plot(results: List[List[Candidate]],
         candidates: Dict[Candidate, Tuple[float, float]],
         cmap: str = 'tab10',
         ax=None) -> None:
    """Plot the Yee diagram.

    Requires Matplotlib. Plots the Yee diagram cells and candidate positions
    on the current/chosen axes and adds a legend. You normally need to follow
    up on this with the ``show()`` call to show the figure.

    :param results: The Yee diagram to plot.
    :param candidates: Candidate positions in the 2D issue space. The
        coordinates should both be between 0 and 1.
    :param cmap: Colormap to use for plotting. The default is sufficient
        for up to 10 candidates unambiguously. References the Matplotlib
        colormap register.
    :param ax: Axes to plot on.
    """
    if plt is None:
        raise ImportError('votelib.crit.yee.plot requires matplotlib')
    if ax is None:
        ax = plt.gca()
    if isinstance(cmap, str):
        cmap = matplotlib.cm.get_cmap(cmap)
    # Convert candidate objects in the diagram to integers to plot easily.
    cand_list = list(sorted(candidates.keys()))
    cand_coors = [candidates[c] for c in cand_list]
    cand_x, cand_y = zip(*cand_coors)
    results_int = [[cand_list.index(cand) for cand in row] for row in results]
    norm = matplotlib.colors.Normalize(vmin=0, vmax=len(cmap.colors)-1)
    ax.imshow(
        results_int,
        cmap=cmap,
        extent=(0, 1, 0, 1),
        interpolation='none',
        resample=False,
        norm=norm,
        alpha=.75,
        origin='lower',
    )
    ax.scatter(
        cand_x, cand_y,
        c=range(len(cand_list)),
        cmap=cmap,
        norm=norm,
        edgecolors='white',
    )
    legend_handles = [
        matplotlib.patches.Patch(color=cmap(i), label=str(cand))
        for i, cand in enumerate(cand_list)
    ]
    ax.legend(handles=legend_handles)
