'''Common functionality for components.

Functions to build function or class registers and retrievers around them.
There should normally be no need to use these functions directly.
'''

from typing import Callable, Dict, Union


def marker(register: Dict[str, Callable],
           name: str,
           signature,
           ) -> Callable[[Callable], Callable]:
    '''A registration decorator factory.'''
    def mark_function(func):
        register[func.__name__] = func
        return func
    return mark_function


def getter(register: Dict[str, Callable],
           name: str,
           signature,
           ) -> Callable[[Callable], Callable]:
    '''A register retriever factory.'''
    def get(func_def: str) -> signature:
        f'''Return a {name} function by its name.'''
        try:
            return register[func_def]
        except KeyError:
            raise KeyError(f'unknown {name}: {func_def}')
    return get


def constructer(register: Dict[str, Callable],
                name: str,
                signature,
                ) -> Callable[[Callable], Callable]:
    '''A register implicit retriever/passthrough function factory.'''
    get = getter(register, name, signature)

    def construct(func_def: Union[str, signature]
                  ) -> signature:
        f'''Construct a {name} function.

        Get a {name} function by its name from the register. If a custom
        callable is given, pass it through unchanged.
        '''
        return func_def if hasattr(func_def, '__call__') else get(func_def)

    return construct


def register_functions(*args, **kwargs):
    '''Construct the marker, getter and constructer functions at one call.'''
    return (
        marker(*args, **kwargs),
        getter(*args, **kwargs),
        constructer(*args, **kwargs),
    )
