"""Votelib - a library for evaluating election results.

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
in the :mod:`evaluate` subpackage. The :class:`VotingSystem` object from the
:mod:`system` module can then wrap it into a formalized and named election
system.
"""
