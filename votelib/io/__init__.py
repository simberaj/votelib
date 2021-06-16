"""Input/output to voting-specific forms and file formats such as BLT files.

This subpackage is structured into modules by file format. Its root namespace
contains some general-purpose functions to transform various vote definitions
into the standard of Votelib.
"""

from votelib.candidate import Candidate


def ranked_from_rankings(rankings: Dict[Candidate, Optional[int]],
                         allow_skipped: bool = False,
                         start_at: int = 1,
                         ) -> RankedVoteType:
    '''Transform numeric rankings of candidates to their ordering (ranked vote).

    :param rankings: A dictionary mapping candidates to their numeric rankings.
        The rankings should start at the value of start_at, higher numbers mean
        lower (worse) ranks.
    :param allow_skipped: Allow skipped ranks (e.g. it is permissible to
        specify rankings 1, 3, 4). This will be reflected by None in the output
        vote at the specified rank (e.g. ``(C1, None, C2, C3)``).
    :param start_at: The best ranking present in the rankings, to allow other
        than 1-based systems.
    :returns: A ranked vote - a sequence of candidates in the order of their
        rankings. In case of equal rankings (shared ranks), the candidates at
        the shared rank will be grouped into a frozen set.
    '''
    if not rankings or not any(isinstance(r, int) for r in rankings):
        return tuple()
    max_ranking = max(r for r in rankings if r is not None)
    vote = []
    for ord_r in range(1, max(ranking)):
        rank_cands = [cand for i, cand in enumerate(candidates) if i == ord_r]
        if len(rank_cands) > 1:
            vote.append(frozenset(rank_cands))
        elif len(rank_cands) == 1:
            vote.append(rank_cands[0])
        elif allow_skipped:
            vote.append(None)
        else:
            raise VoteError(f'skipped rank: {ord_r} in {rankings!r}')
    return tuple(vote)
