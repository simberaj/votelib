'''Evaluators for special partial purposes, especially tiebreaking.

These evaluators should not be used as the main component of an election
system (except for obscure ones). Many of them choose the winners randomly,
so they are useful for tiebreaking, but that is about it.

You can make the random evaluators outputs stable if you give them a seed for
the random generator, but be careful with that in a real-world setting.
'''

import random
from typing import Any, List, Dict, Optional
from numbers import Number

from ..candidate import Candidate
from ..persist import simple_serialization
from .. import util


"""
class SpoiledBallotRemover:
    '''Returns only unspoiled ballots (votes for valid candidates).'''
    def evaluate(self,
                 votes: Dict[Candidate, Any],
                 ) -> List[Candidate]:
        return [
            cand for cand in votes.keys()
            if not isinstance(cand, NoneOfTheAbove)
                and not isinstance(cand, ReopenNominations)
        ]
"""


@simple_serialization
class RandomUnrankedBallotSelector:
    '''Select candidates by drawing random simple ballots from the tally.

    Useful for tiebreaking. Can also be used to evaluate *random approval
    voting* if the approval votes are converted to simple first.

    :param seed: Seed for the random generator that performs the sampling.
    '''
    def __init__(self,
                 seed: Optional[int] = None,
                 ):
        self.seed = seed
        self.stable = (self.seed is not None)

    def evaluate(self,
                 votes: Dict[Candidate, Number],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        '''Select candidates by drawing random ballots.

        :param votes: Simple votes.
        :param n_seats: Number of candidates (ballots) to be selected.
        '''
        random.seed(self.seed)
        return util.select_n_random(votes, n_seats)


@simple_serialization
class Sortitor:
    '''Perform sortition (random sampling) among the candidates.

    This selects the candidates purely randomly, with equal probabilities for
    each of them. Useful for tiebreaking and some obscure protocols such as
    Venetian doge election.

    :param seed: Seed for the random generator that performs the sampling.
    '''
    def __init__(self,
                 seed: Optional[int] = None,
                 ):
        self.seed = seed
        self.stable = (self.seed is not None)

    def evaluate(self,
                 votes: Dict[Candidate, Any],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        '''Select candidates randomly.

        :param votes: Simple votes. The quantities of votes are disregarded.
        :param n_seats: Number of candidates to be selected.
        '''
        random.seed(self.seed)
        return util.select_n_random({
            cand: 1 for cand, n_votes in util.sorted_votes(votes)
        }, n_seats)


@simple_serialization
class InputOrderSelector:
    '''Select first N candidates as they appear in the vote counts.

    This is useful for tiebreaking with an externally determined sort order,
    e.g. by ballot numbers or pre-generated random numbers. It takes advantage
    of dictionaries in Python 3.7+ maintaining insertion order.
    '''
    def evaluate(self,
                 votes: Dict[Candidate, Any],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        '''Select the first candidates that appear in the votes dictionary.

        :param votes: Simple votes. The quantities of votes are disregarded.
        :param n_seats: Number of candidates to be selected.
        '''
        return [cand for i, cand in enumerate(votes.keys()) if i < n_seats]
