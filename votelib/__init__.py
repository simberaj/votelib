'''Votelib - a library for evaluating election results.

Votelib objects provide the means to evaluate elections under many known
election systems, be it simple or complicated, obscure or ubiquitous.

An election system usually specifies the following:

-   Who can stand for the election (what is a valid nomination). This can be
    checked using the nominators from the ``candidate`` module.
-   What forms of votes are valid. This can be checked using the vote
    validators from the ``vote`` module for different vote types from ranked
    to range votes.
-   How to determine who is elected. This is the task of the ``evaluate``
    subpackage and its many modules, which contains evaluators for most of the
    world's known systems. Many of those considered standalone evaluation
    methods are actually reducible variants that can use an another evaluator;
    for these cases, the ``convert`` module provides converters for votes and
    results to create more complex systems.

The evaluator can be combined with the validator and nominator by the machinery
in the :mod:`evaluate` subpackage. The :class:`VotingSystem` object can then
wrap it into a formalized and named election system.
'''

import votelib.evaluate
from votelib.persist import simple_serialization    # noqa: F401


@simple_serialization
class VotingSystem:
    '''A named voting system. Wraps an election evaluator.

    :param name: Name of the system; usually mainly includes the body or
        position to be elected.
    :param evaluator: Evaluator representing the system. Can be combined with
        the validator and nominator by machinery in the :mod:`evaluate`
        subpackage.
    '''
    def __init__(self, name: str, evaluator: votelib.evaluate.Evaluator):
        self.name = name
        self.evaluator = evaluator

    def evaluate(self, *args, **kwargs):
        '''Return the evaluator's results of the system for the votes given.'''
        return self.evaluator.evaluate(*args, **kwargs)
