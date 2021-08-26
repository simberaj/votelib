
import sys
import os
import random
import itertools

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.component.divisor as d
import votelib.evaluate.proportional

TEST_ORDERS = list(range(10)) + [100, 1000, 10000]

@pytest.mark.parametrize(
    'order', TEST_ORDERS
)
def test_result(order):
    for fx in d.DIVISORS.values():
        divisor = fx(order)
        assert divisor >= 0
        assert order == 0 or divisor > 0


def test_modified_first_coef():
    for fx in d.DIVISORS.values():
        modif = d.modified_first_coef(fx, 8654)
        assert modif(0) == 8654
        for i in TEST_ORDERS[1:]:
            assert modif(i) == fx(i)


def test_get():
    for fx_name, fx in d.DIVISORS.items():
        assert d.get(fx_name) == fx
    for bad_name in ('oapsdjf', '', None):
        with pytest.raises(KeyError):
            d.get(bad_name)


def test_construct():
    for fx_name, fx in d.DIVISORS.items():
        assert d.construct(fx_name) == d.get(fx_name) == fx
    for bad_name in ('oapsdjf', '', None):
        with pytest.raises(KeyError):
            d.construct(bad_name)
    def own_divf(ord):
        return ord + 2
    assert d.construct(own_divf) == own_divf


def test_modified_first_coef_default():
    evaluator = votelib.evaluate.proportional.HighestAverages(
        divisor_function=d.modified_first_coef(
            d.sainte_lague
        )
    )
    result = evaluator.evaluate({"muncip1": 20, "muncip2": 10}, 20)
