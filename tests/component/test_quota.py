
import sys
import os
import random
import itertools

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.component.quota as q

VOTES = [1, 2, 5, 1000, 5, 1000, 42, 15000000, 150000000]
SEATS = [1, 1, 1, 1, 2, 2, 42, 200, 1]

# add some random stuff to n_votes and n_seats
random.seed(1711)
for i in range(25):
    n_votes = random.randint(1, 1000000)
    n_seats = random.randint(1, 10000)
    if n_seats > n_votes:
        n_votes, n_seats = n_seats, n_votes
    VOTES.append(n_votes)
    SEATS.append(n_seats)


@pytest.mark.parametrize(
    ('n_votes', 'n_seats', 'quota_name'),
    [vs + (q,) for vs, q in itertools.product(
        list(zip(VOTES, SEATS)), q.QUOTAS.keys()
    )]
)
def test_result(n_votes, n_seats, quota_name):
    quota_fx = q.get(quota_name)
    quota = quota_fx(n_votes, n_seats)
    assert 0 < quota <= n_votes


def test_get():
    for fx_name, fx in q.QUOTAS.items():
        assert q.get(fx_name) == fx
    for bad_name in ('oapsdjf', '', None):
        with pytest.raises(KeyError):
            q.get(bad_name)


def test_construct():
    for fx_name, fx in q.QUOTAS.items():
        assert q.construct(fx_name) == q.get(fx_name) == fx
    for bad_name in ('oapsdjf', '', None):
        with pytest.raises(KeyError):
            q.construct(bad_name)
    def own_quotaf(nv, ns):
        return nv / (ns + 3)
    assert q.construct(own_quotaf) == own_quotaf
