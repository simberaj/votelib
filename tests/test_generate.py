
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import votelib.convert
import votelib.evaluate
import votelib.generate


def test_plurality_wins_in_center():
    gen = votelib.generate.SamplingGenerator(
        candidates={'A': (0., 0.), 'B': (-1., -1.), 'C': (1., 1.)},
        vote_creation='closest',
        random_state=1711,
    )
    votes = gen.generate(10000)
    winner = votelib.evaluate.Plurality().evaluate(votes)
    assert winner == ['A']


def test_score_vote_correctness():
    gen = votelib.generate.SamplingGenerator(
        candidates={'A': (0., 0.), 'B': (-1., -1.), 'C': (1., 1.)},
        random_state=1711,
    )
    votes = gen.generate(10000)
    assert sum(votes.values()) == 10000
    assert min(votes.values()) >= 1
    for vote in votes.keys():
        assert isinstance(vote, frozenset)
        assert set(c for c, s in vote) == {'A', 'B', 'C'}
        assert min(s for c, s in vote) >= 0
        assert max(s for c, s in vote) <= 1


def test_generator_infer_candidates():
    gen = votelib.generate.SamplingGenerator(candidates=4)
    votes = gen.generate(100)
    assert set(cand for vote in votes.keys() for cand, score in vote) == {'A', 'B', 'C', 'D'}


def test_sampler_infer_dims():
    samp = votelib.generate.DistributionSampler(mu=(.5, .5, .5), sigma=(2, 2, 2))
    assert samp.n_dims == 3


def test_bounded_sampler():
    samp = votelib.generate.BoundedSampler(
        votelib.generate.DEFAULT_SAMPLER,
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
