
import math
import random
from typing import Tuple, List, Dict, Union, Optional

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
        tiebreaker=votelib.evaluate.auxiliary.Sortitor(),
        subsetter=votelib.vote.ScoreSubsetter(),
    )
    y_size_elem, x_size_elem = [1 / s for s in shape]
    if random_state is not None:
        random.seed(random_state)
    diag = []
    for i in range(shape[0]):
        y = (i + .5) * y_size_elem
        row = []
        for j in range(shape[1]):
            x = (j + .5) * x_size_elem
            votes = votelib.generate.IssueSpaceGenerator(
                candidates,
                sampler=sampler(x, y, **kwargs),
            ).generate(n_votes)
            row.append(full_eval.evaluate(votes, n_seats=1)[0])
        diag.append(row)
    return diag


def sampler(x: float,
            y: float,
            sigma: Tuple[float, float] = (.25, .25),
            ) -> votelib.generate.BoundedSampler:
    return votelib.generate.BoundedSampler(
        votelib.generate.DistributionSampler(
            distribution='gauss', mu=(x, y), sigma=sigma
        ),
        (0, 0, 1, 1),
    )


def voronoi(candidates: Dict[Candidate, Tuple[float, float]],
            shape: Tuple[int, int] = DEFAULT_SHAPE,
            ) -> List[List[Candidate]]:
    return diagram(VORONOI_EVALUATOR, candidates, shape=shape)


def voronoi_matches(results: List[List[str]],
                    candidates: Dict[Candidate, Tuple[float, float]],
                    ) -> List[List[bool]]:
    shape = (len(results), len(results[0]))
    voronoi_diagram = voronoi(candidates, shape=shape)
    return [
        [results[i][j] == voronoi_diagram[i][j] for j in range(shape[1])]
        for i in range(shape[0])
    ]


def voronoi_conformity(results: List[List[str]],
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
