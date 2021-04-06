'''Evaluators for special partial purposes, especially tiebreaking.

These evaluators should not be used as the main component of an election
system (except for obscure ones). Many of them choose the winners randomly,
so they are useful for tiebreaking, but that is about it.

You can make the random evaluators outputs stable if you give them a seed for
the random generator, but be careful with that in a real-world setting.
'''

import re
import random
import struct
import hashlib
import unicodedata
import operator
from typing import Any, List, Dict, Collection, Optional, Union
from numbers import Number
from decimal import Decimal

from votelib.candidate import Candidate
from votelib.persist import simple_serialization
import votelib.util


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
        return votelib.util.select_n_random(votes, n_seats)


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
        return votelib.util.select_n_random({
            cand: 1 for cand, n_votes in votelib.util.sorted_votes(votes)
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


@simple_serialization
class CandidateNumberRanker:
    '''Select first N candidates with lowest candidate number.

    This is useful for tiebreaking with an externally determined sort order.
    '''
    def evaluate(self,
                 votes: Dict[Candidate, Any],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        '''Select the first candidates that appear in the votes dictionary.

        :param votes: Simple votes. The quantities of votes are disregarded.
        :param n_seats: Number of candidates to be selected.
        '''
        return list(
            sorted(votes.keys(), operator.attrgetter('number'))
        )[:n_seats]


@simple_serialization
class RFC3797Selector:
    '''Select candidates randomly by the algorithm from RFC 3797.

    This is a well-defined random selection method using external sources
    of randomness, that are to be provided as numbers or lists thereof.
    Once the sources of randomness are fixed in the constructor, the
    selection is deterministic with regard to the input order of candidates
    (candidate names or votes are disregarded).

    :param sources: Sources of randomness (seeds). For detailed
        recommendations on where to take them from, see the RFC. The
        list should contain an item per source. The list items may contain
        a number, a string (which will be stripped of accents and anything
        besides ASCII alphanumeric characters and uppercased) or a list of
        numbers. Strings and floats are STRONGLY not recommended.

    .. [#rfc3797] "RFC 3797: Publicly Verifiable Nominations Committee
        (NomCom) Random Selection", D. Eastlake 3rd.
        https://tools.ietf.org/html/rfc3797
    '''
    IMPURE_CHARS = re.compile('[^a-zA-Z0-9]')
    ORDER_STRUCT = struct.Struct('>H')
    UNPACK_STRUCT = struct.Struct('>Q')
    FIRST_PART_MULT = 1 << 64

    def __init__(self, sources: List[Union[Number, Collection[Number]]]):
        if not hasattr(hashlib, 'md5'):
            raise ImportError('need Python build with hashlib.md5()')
        self.sources = sources
        self.seed_bytes = self.source_bytestring(self.sources)

    def evaluate(self,
                 votes: Dict[Candidate, Any],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        '''Select the candidates by the algorithm from RFC 3797.

        :param votes: Simple votes. The quantities of votes are disregarded.
        :param n_seats: Number of candidates to be selected.
        '''
        cands = list(votes.keys())
        selected = []
        for i in range(n_seats):
            rand_int = self._random_value(i)
            selected.append(cands.pop(rand_int % len(cands)))
        return selected

    def _random_value(self, i: int) -> int:
        order_bytes = self.ORDER_STRUCT.pack(i)
        hash = hashlib.md5(
            order_bytes + self.seed_bytes + order_bytes
        ).digest()
        part1, part2 = self.UNPACK_STRUCT.iter_unpack(hash)
        return part1[0] * self.FIRST_PART_MULT + part2[0]

    @classmethod
    def source_bytestring(cls,
                          sources: List[Union[Number, Collection[Number]]]
                          ) -> bytes:
        '''Create the base randomness string from given randomness sources.

        Follows the procedure as given by Section 4 of the RFC.
        '''
        components = []
        for source in sources:
            if isinstance(source, str):
                component = cls._clean_string(source)
            elif hasattr(source, '__len__'):
                # collection of numbers, concatenate them ordered
                component = ''.join(
                    # order from smallest to largest
                    cls._num_to_str(num) for num in sorted(source)
                )
            else:
                # single item
                component = cls._num_to_str(source)
            # suffix by slash and concatenate as ascii
            components.append(component + '/')
        return ''.join(components).encode('ascii')

    @classmethod
    def _clean_string(cls, s: str) -> str:
        # rip off everything except ascii letters and numbers
        # and convert to uppercase
        deaccented = ''.join(
            c for c in unicodedata.normalize('NFD', s)
            if unicodedata.category(c) != 'Mn'
        )
        return cls.IMPURE_CHARS.sub('', deaccented).upper()

    @staticmethod
    def _num_to_str(num: Number) -> str:
        value = str(Decimal(num))
        if '.' not in value:
            value += '.'
        return value.rstrip('0')
