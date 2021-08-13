
import math
import random
from typing import Tuple, List, Dict, Union, Optional

try:
    import matplotlib.cm
    import matplotlib.patches
    import matplotlib.pyplot as plt
except ImportError as e:
    plt = None

import votelib.convert
import votelib.evaluate
import votelib.evaluate.auxiliary
import votelib.evaluate.cardinal
import votelib.generate
import votelib.vote
from votelib.candidate import Candidate


DEFAULT_SHAPE = (100, 100)
VORONOI_EVALUATOR = votelib.evaluate.cardinal.ScoreVoting()


def diagram(evaluator: votelib.evaluate.Selector,
            candidates: Dict[Candidate, Tuple[float, float]],
            shape: Tuple[int, int] = DEFAULT_SHAPE,
            n_votes: int = 1000,
            random_state: Optional[int] = None,
            **kwargs) -> List[List[Candidate]]:
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
    return bounded_sampler(votelib.generate.DistributionSampler(
        distribution='gauss', mu=(x, y), sigma=sigma
    ))


def bounded_sampler(sampler: votelib.generate.Sampler) -> votelib.generate.Sampler:
    return votelib.generate.BoundedSampler(sampler, (0, 0, 1, 1))


def voronoi(candidates: Dict[Candidate, Tuple[float, float]],
            shape: Tuple[int, int] = DEFAULT_SHAPE,
            ) -> List[List[Candidate]]:
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
    shape = (len(results), len(results[0]))
    voronoi_diagram = voronoi(candidates, shape=shape)
    return [
        [results[i][j] == voronoi_diagram[i][j] for j in range(shape[1])]
        for i in range(shape[0])
    ]


def voronoi_conformity(results: List[List[Candidate]],
                       candidates: Dict[Candidate, Tuple[float, float]],
                       ) -> float:
    shape = (len(results), len(results[0]))
    matches = voronoi_matches(results, candidates)
    return sum(m for row in matches for m in row) / (shape[0] * shape[1])


def circular_candidates(n: int,
                        r: float = .25,
                        center: Tuple[float, float] = (.5, .5),
                        ) -> Dict[Candidate, Tuple[float, float]]:
    unit_angle = 2 * math.pi / n
    cx, cy = center
    return dict(zip(votelib.generate.candidate_names(n), (
        (
            cx + r * math.cos(unit_angle * i),
            cy + r * math.sin(unit_angle * i)
        ) for i in range(n)
    )))


def random_candidates(n: int,
                      sampler: Optional[votelib.generate.Sampler] = None,
                      ) -> Dict[Candidate, Tuple[float, float]]:
    if sampler is None:
        sampler = votelib.generate.DistributionSampler('uniform', n_dims=2)
    sampler = bounded_sampler(sampler)
    return dict(zip(
        votelib.generate.candidate_names(n),
        sampler.sample(n)
    ))


def plot(results: List[List[Candidate]],
         candidates: Dict[Candidate, Tuple[float, float]],
         cmap: str = 'tab10',
         ax=None) -> None:
    if plt is None:
        raise ImportError('votelib.crit.yee.plot requires matplotlib')
    if ax is None:
        ax = plt.gca()
    if isinstance(cmap, str):
        cmap = matplotlib.cm.get_cmap(cmap)
    cand_list = list(sorted(candidates.keys()))
    cand_coors = [candidates[c] for c in cand_list]
    cand_x, cand_y = zip(*cand_coors)
    results_int = [[cand_list.index(cand) for cand in row] for row in results]
    # import numpy as np
    # print(np.array(results_int))
    # print(np.bincount(np.array(results_int).flatten()))
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
