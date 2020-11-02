import math
from typing import Dict, Tuple
from numbers import Number

from .candidate import Candidate


def gallagher(votes: Dict[Candidate, Number],
              results: Dict[Candidate, Number],
              ) -> float:
    """Compute the Gallagher index of election result disproportionality.

    The Gallagher (LSq) index [#lsq]_ expresses the mismatch between the
    fraction of votes received and seats allocated for each candidate or party.
    The index ranges from zero (no disproportionality) to 1 (total
    disproportionality).
    Compared to the Loosemore–Hanby index, it highlights large deviations
    rather than small ones.

    :param votes: Numbers of votes for each candidate. This function only
        accepts votes in a simple format. To evaluate disproportionality
        for elections using other vote types, you must use an appropriate
        converter first; however, using the index for those election systems
        might not be meaningful.
        Gallagher also merges or excludes smaller parties or blank votes;
        this function does none of that. Apply an appropriate vote filter
        first.
    :param results: Seat counts awarded to each candidate. This is the
        distribution evaluator output format.

    .. [#lsq] "Gallagher index", Wikipedia.
        https://en.wikipedia.org/wiki/Gallagher_index
    """
    paired_fractions = _vote_seat_fractions(votes, results)
    return math.sqrt(.5 * sum(
        (vote_frac - seat_frac) ** 2
        for vote_frac, seat_frac in paired_fractions.values()
    ))


def loosemore_hanby(votes: Dict[Candidate, Number],
                    results: Dict[Candidate, Number],
                    ) -> float:
    """Compute the Loosemore–Hanby index of election result disproportionality.

    The Loosemore–Hanby (LH) index [#lhind]_ expresses the mismatch between the
    fraction of votes received and seats allocated for each candidate or party.
    The index ranges from zero (no disproportionality) to 1 (total
    disproportionality).
    Compared to the Gallagher index, it does not diminish the effect of smaller
    deviations.

    :param votes: Numbers of votes for each candidate. This function only
        accepts votes in a simple format. To evaluate disproportionality
        for elections using other vote types, you must use an appropriate
        converter first; however, using the index for those election systems
        might not be meaningful.
    :param results: Seat counts awarded to each candidate. This is the
        distribution evaluator output format.

    .. [#lhind] "Loosemore–Hanby index", Wikipedia.
        https://en.wikipedia.org/wiki/Loosemore%E2%80%93Hanby_index
    """
    paired_fractions = _vote_seat_fractions(votes, results)
    return .5 * sum(
        vote_frac - seat_frac
        for vote_frac, seat_frac in paired_fractions.values()
    )


def _vote_seat_fractions(votes: Dict[Candidate, Number],
                         results: Dict[Candidate, Number],
                         ) -> Dict[Candidate, Tuple[Number, Number]]:
    total_votes = sum(votes.values())
    total_seats = sum(results.values())
    merged = {
        cand: (n_votes / total_votes, results.get(cand, 0) / total_seats)
        for cand, n_votes in votes.items()
    }
    for cand, result in results.items():
        if cand not in merged:
            merged[cand] = (0, result)
    return merged
