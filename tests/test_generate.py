
import sys
import os

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import votelib.convert
import votelib.evaluate
import votelib.generate


def test_plurality_wins_in_center():
    gen = votelib.generate.IssueSpaceGenerator(
        candidates={'A': (0., 0.), 'B': (-1., -1.), 'C': (1., 1.)},
        vote_creation='closest',
        random_state=1711,
    )
    votes = gen.generate(1000)
    winner = votelib.evaluate.Plurality().evaluate(votes)
    assert winner == ['A']


def test_score_vote_correctness():
    gen = votelib.generate.IssueSpaceGenerator(
        candidates={'A': (0., 0.), 'B': (-1., -1.), 'C': (1., 1.)},
        random_state=1711,
    )
    votes = gen.generate(100)
    assert sum(votes.values()) == 100
    assert min(votes.values()) >= 1
    for vote in votes.keys():
        assert isinstance(vote, frozenset)
        assert set(c for c, s in vote) == {'A', 'B', 'C'}
        assert min(s for c, s in vote) >= 0
        assert max(s for c, s in vote) <= 1


def test_generator_infer_candidates():
    gen = votelib.generate.IssueSpaceGenerator(candidates=4)
    votes = gen.generate(100)
    assert set(cand for vote in votes.keys() for cand, score in vote) == {'A', 'B', 'C', 'D'}


def test_sampler_infer_dims():
    samp = votelib.generate.DistributionSampler(mu=(.5, .5, .5), sigma=(2, 2, 2))
    assert samp.n_dims == 3


def test_bounded_sampler():
    samp = votelib.generate.BoundedSampler(
        votelib.generate.DistributionSampler(n_dims=2),
        (-1, -1, 1, 1)
    )
    minval, maxval = float('inf'), -float('inf')
    for coors in samp.sample(1000):
        for coor in coors:
            if coor < minval:
                minval = coor
            elif coor > maxval:
                maxval = coor
    assert minval >= -1
    assert maxval <= 1


def test_score_space_generator_biased():
    gen = votelib.generate.ScoreSpaceGenerator(
        candidates=['A', 'B'],
        sampler=votelib.generate.BoundedSampler(
            votelib.generate.DistributionSampler('gauss', mu=(0.7, 0.3), sigma=(1, 1)),
            bbox=(0, 1)
        ),
        random_state=1711,
    )
    score_votes = gen.generate(1000)
    mean_votes = votelib.convert.ScoreToSimpleVotes('sum').convert(score_votes)
    assert votelib.evaluate.Plurality().evaluate(mean_votes) == ['A']


def test_iac():
    gen = votelib.generate.ScoreSpaceGenerator(candidates=2)
    score_votes = gen.generate(1000)
    mean_votes = votelib.convert.ScoreToSimpleVotes('mean').convert(score_votes)
    assert abs(mean_votes['A'] - mean_votes['B']) < (2 * 0.01433)    # five-sigma confidence interval


def test_need_dims():
    samp = votelib.generate.DistributionSampler()
    with pytest.raises(ValueError):
        list(samp.sample(20))


def test_need_consistent_dims():
    with pytest.raises(ValueError):
        samp = votelib.generate.DistributionSampler(mu=(2, 3, 4), sigma=(1, 2))


def test_instance_dims_mismatch():
    samp = votelib.generate.DistributionSampler(n_dims=2)
    with pytest.raises(ValueError):
        list(samp.sample(10, n_dims=3))


def test_need_even_bbox():
    with pytest.raises(ValueError):
        votelib.generate.BoundedSampler(votelib.generate.DistributionSampler(), bbox=(0, 0, 1))
