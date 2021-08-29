"""Input/output to voting-specific forms and file formats such as BLT files.

This subpackage is structured into modules by file format. Its root namespace
contains some general-purpose functions to transform various vote definitions
into the standard of Votelib.
"""

from typing import Dict, Optional

from votelib.candidate import Candidate
from votelib.vote import RankedVoteType, VoteError


def ranked_from_rankings(rankings: Dict[Candidate, Optional[int]],
                         skipped: str = 'error',
                         start_at: int = 1,
                         ) -> RankedVoteType:
    '''Transform numeric rankings of candidates to their ordering (ranked vote).

    :param rankings: A dictionary mapping candidates to their numeric rankings.
        The rankings should start at the value of start_at, higher numbers mean
        lower (worse) ranks.
    :param skipped: How to behave for skipped ranks (e.g. rankings 1, 3, 4):

        -   ``error``: Raise a :class:`VoteError`.
        -   ``include``: Include None in the output vote at the specified rank
            (e.g. ``(C1, None, C2, C3)``).
        -   ``ignore``: Behave as if the skipped rank did not exist, do not
            include any None in the output vote.

        When equal ranks are used, it is permissible to skip the next rank(s)
        regardless of this setting (so that 1, 2, 2, 4 is always allowed).
    :param start_at: The best ranking present in the rankings, to allow other
        than 1-based systems.
    :returns: A ranked vote - a sequence of candidates in the order of their
        rankings. In case of equal rankings (shared ranks), the candidates at
        the shared rank will be grouped into a frozen set.
    '''
    filled_rankings = {
        cand: rank for cand, rank in rankings.items() if isinstance(rank, int)
    }
    if not filled_rankings:
        return tuple()
    max_ranking = max(filled_rankings.values())
    vote = []
    last_filled = 0
    for ord_r in range(1, max_ranking + 1):
        rank_cands = [
            cand for cand, rank in filled_rankings.items() if rank == ord_r
        ]
        if len(rank_cands) > 1:
            vote.append(frozenset(rank_cands))
            last_filled = ord_r
        elif len(rank_cands) == 1:
            vote.append(rank_cands[0])
            last_filled = ord_r
        elif vote and isinstance(vote[-1], frozenset) and ord_r < last_filled + len(vote[-1]):
            pass    # ignore skipped rank after shared rank
        elif skipped == 'include':
            vote.append(None)
        elif skipped == 'ignore':
            pass
        elif skipped == 'error':
            raise VoteError(f'skipped rank: {ord_r} in {rankings!r}')
        else:
            raise ValueError(f'invalid skipped setting: {skipped!r}')
    return tuple(vote)
