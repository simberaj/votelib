
import sys
import inspect
import builtins
import importlib
from fractions import Fraction
from decimal import Decimal
from typing import Any, List, Dict, Callable


ZERO_PARAMS: List[str] = ['args', 'kwargs']


def simple_serialization(class_: type) -> type:
    '''A decorator to provide a simple to_dict() serialization method.

    The resulting method will serialize all object attributes corresponding
    to the class's constructor parameter names. Therefore, this decorator
    is only useful when the class stores all its original parameters
    unchanged (or in any other form acceptable to its constructor).

    :param class_: The class to add the method to.
    '''
    if hasattr(class_, 'serialize_params'):
        param_names = class_.serialize_params
    else:
        param_names = list(inspect.signature(
            class_.__init__
        ).parameters.keys())
        if 'self' in param_names:
            param_names.remove('self')
        if param_names == ZERO_PARAMS and class_.__init__ == object.__init__:
            param_names = []

    def to_dict(self) -> Dict[str, Any]:
        out_dict = {'class': scoped_class_name(self)}
        for attr in param_names:
            out_dict[attr] = serialize_value(getattr(self, attr))
        return out_dict

    class_.to_dict = to_dict
    return class_


def serialize_value(value: Any) -> Any:
    if hasattr(value, 'to_dict'):
        return value.to_dict()
    elif isinstance(value, tuple(ATOMIC_TYPES)):
        return value
    elif type(value) in CONVERTIBLE_TYPES:
        return CONVERTIBLE_TYPES[type(value)](value)
    elif hasattr(value, '__iter__'):
        if hasattr(value, 'items') and hasattr(value, 'keys'):
            if all(isinstance(key, str) for key in value.keys()):
                return {
                    key: serialize_value(val)
                    for key, val in value.items()
                }
            else:
                return {
                    'type': 'dict',
                    'keys': [serialize_value(key) for key in value.keys()],
                    'values': [serialize_value(val) for val in value.values()]
                }
        else:
            return [serialize_value(val) for val in value]
    elif hasattr(value, '__call__'):
        return {'callable': '.'.join((value.__module__, value.__name__))}
    else:
        raise ValueError(f'cannot serialize {value!r} to dict format')


def deserialize_value(value: Any) -> Any:
    if isinstance(value, dict):
        if 'type' in value and is_scoped_identifier(value['type']):
            return deserialize_typed(value)
        elif 'class' in value and is_scoped_identifier(value['class']):
            return deserialize_class(value)
        elif 'callable' in value and is_scoped_identifier(value['callable']):
            return get_object(value['callable'])
        else:
            return {key: deserialize_value(val) for key, val in value.items()}
    elif isinstance(value, tuple(ATOMIC_TYPES)):
        return value
    elif isinstance(value, list):
        return [deserialize_value(val) for val in value]
    else:
        raise ValueError(f'cannot deserialize {value!r}, type unknown')


def deserialize_typed(typedef: Dict[str, Any]) -> Any:
    typeobj = get_object(typedef['type'])
    if typeobj is dict:
        return dict(zip(
            [deserialize_value(key) for key in typedef['keys']],
            [deserialize_value(val) for val in typedef['values']]
        ))
    elif 'value' in typedef:
        return typeobj(deserialize_value(typedef['value']))
    elif 'arguments' in typedef:
        return typeobj(*[
            deserialize_value(val) for val in typedef['arguments']
        ])
    elif 'parameters' in typedef:
        return typeobj(**{
            param: deserialize_value(val)
            for param, val in typedef['parameters'].items()
        })
    else:
        raise ValueError(f'invalid typed value contents: {typedef!r}')


def deserialize_class(clsdef: Dict[str, Any]) -> Any:
    cls = get_object(clsdef['class'])
    params = clsdef.copy()
    del params['class']
    if hasattr(cls, 'from_dict'):
        return cls.from_dict(params)
    else:
        for key, inner_val in params.items():
            params[key] = deserialize_value(inner_val)
        return cls(**params)


def get_object(identifier: str) -> Any:
    if '.' not in identifier:
        global_vars = globals()
        if identifier in global_vars:
            return global_vars[identifier]
        else:
            return getattr(builtins, identifier)
    else:
        module, name = identifier.rsplit('.', 1)
        if module not in sys.modules:
            importlib.import_module(module)
        return getattr(sys.modules[module], name)


def from_dict(value: Dict[str, Any]) -> Any:
    """Parse an election evaluator object from a JSON-like dictionary.

    :param value: A dictionary created by :func:`to_dict`.
    """
    if not isinstance(value, dict):
        raise ValueError('invalid votelib object def: dict expected,'
                         f'got {value!r}')
    elif 'class' not in value:
        raise ValueError('invalid votelib object def: must have a class key')
    elif not is_scoped_identifier(value['class']):
        inval_cls = value['class']
        raise ValueError(f"invalid votelib class def: {inval_cls}")
    else:
        return deserialize_value(value)


def to_dict(obj: Any) -> Dict[str, Any]:
    """Serialize an election evaluator object to a JSON-ready dictionary.

    :param obj: An election evaluator object or similar. It should provide
        a `to_dict()` method (all the standard evaluators, converters and the
        like from Votelib should have it, courtesy of the simple_serialization
        decorator).
    """
    return serialize_value(obj)


def is_scoped_identifier(value: Any):
    return (
        isinstance(value, str)
        and not value.startswith('.')
        and all(chunk.isidentifier() for chunk in value.split('.'))
    )


def scoped_class_name(value: Any):
    cls = value.__class__
    return '.'.join((cls.__module__, cls.__name__))


def fraction_to_json(f: Fraction) -> Dict[str, Any]:
    return {'type': 'Fraction', 'arguments': f.as_integer_ratio()}


def decimal_to_json(d: Decimal) -> Dict[str, Any]:
    return {'type': 'Decimal', 'value': str(d)}


def sequence_to_json_factory(typeobj):
    typename = typeobj.__name__

    def sequence_to_json(seq) -> Dict[str, Any]:
        return {'type': typename, 'value': [serialize_value(v) for v in seq]}

    return sequence_to_json


ATOMIC_TYPES: List[type] = [
    str, int, float, bool, type(None),
]

CONVERTIBLE_TYPES: Dict[type, Callable] = {
    Fraction: fraction_to_json,
    Decimal: decimal_to_json,
}

SEQUENCE_TYPES: List[type] = [frozenset, tuple]

for seqtype in SEQUENCE_TYPES:
    CONVERTIBLE_TYPES[seqtype] = sequence_to_json_factory(seqtype)
