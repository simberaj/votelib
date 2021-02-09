'''Functions to score magnitudes of wins between pairs of candidates.

These are used in some Condorcet methods to determine ranking priority.
'''

from typing import Callable, Dict, Tuple
from numbers import Number

import votelib.component.core
from votelib.vote import Candidate


PAIRWIN_SCORERS = {}


pairwin_scorer_mark, get, construct = \
    votelib.component.core.register_functions(
        PAIRWIN_SCORERS, 'pairwise win scorer', Callable[
            [Dict[Tuple[Candidate, Candidate], Number]],
            Dict[Tuple[Candidate, Candidate], Number]
        ]
    )


@pairwin_scorer_mark
def winning_votes(counts: Dict[Tuple[Candidate, Candidate], Number]
                  ) -> Dict[Tuple[Candidate, Candidate], Number]:
    '''Winning votes pairwise win scorer. Counts wins fully, zero otherwise.

    This is the most common pairwise win scorer. When the number of votes
    for the pair ranked in one direction is larger than the other direction,
    assigns all those votes as the pairwise win strength.

    :param counts: Condorcet votes (counts of pairwise preferences).
    '''
    return {
        pair: (count if count > counts.get(tuple(reversed(pair)), 0) else 0)
        for pair, count in counts.items()
    }


@pairwin_scorer_mark
def margins(counts: Dict[Tuple[Candidate, Candidate], Number]
            ) -> Dict[Tuple[Candidate, Candidate], Number]:
    '''Margins pairwise win scorer. Takes the difference from reverse option.

    Also called margin of victory or defeat strength. Assigns the number of
    votes ranking the pair in the given order minus the number of votes doing
    the reverse as the win strength (which is thus negative for pairwise
    losses).

    :param counts: Condorcet votes (counts of pairwise preferences).
    '''
    return {
        pair: count - counts.get(tuple(reversed(pair)), 0)
        for pair, count in counts.items()
    }


@pairwin_scorer_mark
def pairwise_opposition(counts: Dict[Tuple[Candidate, Candidate], Number]
                        ) -> Dict[Tuple[Candidate, Candidate], Number]:
    '''Pairwise opposition win scorer. Returns the win counts unchanged.

    This gives the number of votes ranking the pair in the given order
    directly as the measure of pairwise win, regardless of the number of votes
    preferring the opposite pairwise ranking.

    :param counts: Condorcet votes (counts of pairwise preferences).
    '''
    return counts
