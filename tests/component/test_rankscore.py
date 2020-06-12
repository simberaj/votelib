
import sys
import os
import itertools

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.component.rankscore as rs

N_RANKED = [0, 1, 2, 3, 5, 10, 100]


def build_unprep_rank_scorers():
    return [rs.Borda(), rs.Borda(base=0)]


def build_rank_scorers():
    rankers = [
        rs.Dowdall(),
        rs.ModifiedBorda(),
        rs.FixedTop(1),
        rs.FixedTop(3),
        rs.FixedTop(20),
        rs.SequenceBased([3, 2, 1]),  # Toastmasters
        rs.SequenceBased([12, 10, 8, 7, 6, 5, 4, 3, 2, 1]), # Eurovision
        rs.SequenceBased([10, 6, 4, 3, 2, 1]), # Formula 1 (old)
        rs.SequenceBased([25, 18, 15, 12, 10, 8, 6, 4, 2, 1]), # Formula 1 (current)
    ]
    for n_cands in N_RANKED:
        for r in build_unprep_rank_scorers():
            r.set_n_candidates(n_cands)
            rankers.append(r)
    return rankers


UNPREP_RANKERS = build_unprep_rank_scorers()
RANKERS = build_rank_scorers()


@pytest.mark.parametrize('n_ranked, rank_scorer', list(itertools.product(N_RANKED, RANKERS)))
def test_all(n_ranked, rank_scorer):
    if hasattr(rank_scorer, 'set_n_candidates') and n_ranked > rank_scorer.get_n_candidates():
        return
    scores = rank_scorer.scores(n_ranked)
    assert len(scores) == n_ranked
    assert all(score >= 0 for score in scores)
    assert list(sorted(scores, reverse=True)) == scores


@pytest.mark.parametrize('rank_scorer', UNPREP_RANKERS)
def test_err_init(rank_scorer):
    with pytest.raises(RuntimeError):
        rank_scorer.scores(10)
    rank_scorer.set_n_candidates(5)
    with pytest.raises(ValueError):
        rank_scorer.scores(10)
