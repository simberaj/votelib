'''Various utility functions for other modules of Votelib.

There should normally be no need to use these functions directly.
'''

import operator
import itertools
import collections
import bisect
import random
import inspect
from fractions import Fraction
from decimal import Decimal
from typing import Any, List, Tuple, Dict, FrozenSet, Union, Callable
from numbers import Number

from .vote import RankedVoteType
from .candidate import Candidate


def add_dict_to_dict(dict1: Dict[Any, Number],
                     dict2: Dict[Any, Number],
                     ) -> None:
    for key, addition in dict2.items():
        dict1[key] = dict1.get(key, 0) + addition


def sum_dicts(dict1: Dict[Any, Number],
              dict2: Dict[Any, Number],
              ) -> Dict[Any, Number]:
    summed = dict1.copy()
    add_dict_to_dict(summed, dict2)
    return summed


def descending_dict(d: Dict[Any, Number]) -> Dict[Any, Number]:
    return dict(sorted(d.items(), key=operator.itemgetter(1), reverse=True))


def all_ranked_candidates(votes: Dict[RankedVoteType, Any]
                          ) -> FrozenSet[Candidate]:
    '''Return the set of all candidates appearing in any of the rankings.

    :param votes: Ranked votes.
    '''
    all_candidates = set()
    for ranked in votes.keys():
        for positioned in ranked:
            if isinstance(positioned, collections.abc.Set):
                all_candidates.update(positioned)
            else:
                all_candidates.add(positioned)
    return frozenset(all_candidates)


def sorted_votes(votes: Dict[Any, Number],
                 descending: bool = True,
                 ) -> List[Tuple[Any, Number]]:
    '''Return votes items sorted by value.'''
    return list(sorted(
        votes.items(),
        key=operator.itemgetter(1),
        reverse=descending
    ))


def select_n_random(votes: Dict[Any, Number],
                    n: int = 1,
                    ) -> List[Any]:
    candidates, weights = zip(*sorted_votes(votes))
    candidates = list(candidates)
    cum_weights = list(itertools.accumulate(weights))
    weight_total = cum_weights[-1]
    if isinstance(weight_total, int):    # we have all integers
        return _select_n_random_int(candidates, cum_weights, n)
    elif isinstance(weight_total, Fraction):  # we have fractions, still exact
        last_denom = weight_total.denominator
        return _select_n_random_int(
            candidates, [w * last_denom for w in cum_weights], n
        )
    else:
        # TODO raise inexact arithmetics warning
        return _select_n_random_float(candidates, cum_weights, n)


def _select_n_random_int(candidates: List[Any],
                         cum_weights: List[int],
                         n: int,
                         ) -> List[Any]:
    if n > len(candidates):
        return candidates
    chosen = []
    while len(chosen) < n:
        new_cand_i = bisect.bisect_left(
            cum_weights,
            random.randrange(1, cum_weights[-1] + 1)
        )
        chosen.append(candidates.pop(new_cand_i))
        subtract_wt = cum_weights.pop(new_cand_i)
        if new_cand_i != 0 and cum_weights:
            subtract_wt -= cum_weights[new_cand_i-1]
        cum_weights = (
            cum_weights[:new_cand_i]
            + [wt - subtract_wt for wt in cum_weights[new_cand_i:]]
        )
    return chosen


def _select_n_random_float(candidates: List[Any],
                           cum_weights: List[Number],
                           n: int,
                           ) -> List[Any]:
    return random.choices(
        candidates,
        cum_weights=cum_weights,
        k=n
    )


def exact_mean(values: List[Union[int, Fraction]]) -> Fraction:
    return Fraction(sum(values), len(values))


EXACT_AGGREGATORS = {
    'mean': exact_mean,
}


def default_serialization(class_):
    '''A class decorator to provide a to_dict() method for voting system component persistence.'''
    param_names = inspect.signature(cls.__init__).parameters.keys()

    def to_dict(self) -> Dict[str, Any]:
        out_dict = {'class': self.__class__.__name__}
        for attr in param_names:
            out_dict[attr] = serialize_value(getattr(self, attr))
        return out_dict

    class_.to_dict = to_dict
    return class_


def serialize_value(value: Any) -> Any:
    if hasattr(value, 'to_dict'):
        return value.to_dict()
    elif isinstance(value, ATOMIC_TYPES):
        return value
    elif type(value) in CONVERTIBLE_TYPES:
        return CONVERTIBLE_TYPES[type(value)](value)
    elif hasattr(value, '__iter__'):
        if hasattr(value, 'items'):
            return {key: serialize_value(val) for key, val in value.items()}
        else:
            return [serialize_value(val) for val in value]
    elif hasattr(value, '__call__'):
        return {'callable': '.'.join((value.__module__, value.__name__))}
    else:
        raise ValueError(f'cannot serialize {value!r} to dict format')


def deserialize_value(value: Any) -> Any:
    if isinstance(value, dict):
        if 'type' in value and is_scoped_identifier(value['type']):
            typeobj = get_object(value['type'])
            if 'value' in value:
                return typeobj(value['value'])
            elif 'arguments' in value:
                return typeobj(*value['arguments'])
            elif 'parameters' in value:
                return typeobj(**value['parameters'])
            else:
                raise ValueError(f'invalid dict contents: {value!r}')
        elif 'class' in value and is_scoped_identifier(value['class']):
            cls = get_object(value['class'])
            return cls(**{
                key: deserialize_value(inner_val)
                for key, inner_val in value.items() if key != 'class'
            })
        elif 'callable' in value and is_scoped_identifier(value['callable']):
            return get_object(value['callable'])
        else:
            return {key: deserialize_value(val) for key, val in value.items()}
    elif isinstance(value, ATOMIC_TYPES):
        return value
    elif isinstance(value, list):
        return [deserialize_value(val) for val in value]
    else:
        raise ValueError(f'cannot deserialize {value!r}, type unknown')


def get_object(identifier: str) -> Any:
    if '.' not in str:
        return eval(identifier)
    else:
        module, name = identifier.rsplit('.', 1)
        if module not in sys.modules:
            importlib.import_module(module)
        return getattr(sys.modules[module], name)


def from_dict(value: Dict[str, Any]) -> Any:
    if not isinstance(value, dict):
        raise ValueError(f'invalid votelib object definition: must be a dict, got {type(value)}')
    elif 'class' not in value:
        raise ValueError(f'invalid votelib object definition: must have a class key')
    elif not is_scoped_identifier(value['class']):
        raise ValueError(f"invalid votelib class definition: {value['class']}")
    else:
        return deserialize_value(value)


def is_scoped_identifier(value: Any):
    return (
        isinstance(value, str)
        and not value.startswith('.')
        and all(chunk.isidentifier() for chunk in value.split('.'))
    )


def fraction_to_json(f: Fraction) -> Dict[str, Any]:
    return {'type': 'Fraction', 'arguments': f.as_integer_ratio()}


def decimal_to_json(d: Decimal) -> Dict[str, Any]:
    return {'type': 'Decimal', 'value': str(d)}


def sequence_to_json_factory(typeobj):
    typename = typeobj.__name__
    def sequence_to_json(seq) -> Dict[str, Any]:
        return {'type': typename, 'value': [serialize_value(v) for v in t]}
    return sequence_to_json


ATOMIC_TYPES: List[type] = [
    str, int, float, bool, None,
]

CONVERTIBLE_TYPES: Dict[type, Callable] = {
    Fraction: fraction_to_json,
    Decimal: decimal_to_json,
}

SEQUENCE_TYPES: List[type] = [frozenset, tuple]

for seqtype in SEQUENCE_TYPES:
    CONVERTIBLE_TYPES[seqtype] = sequence_to_json_factory(seqtype)
