"""Measure proportionality of election results.

These functions evaluate how proportionally the seats are allocated to parties
according to their votes received. For a review of such indicators, see
[#polrep]_ or [#kalog]_.

The functions only accept votes in simple format. To evaluate
disproportionality for elections using other vote types, you must use an
appropriate converter first; however, using the index for those election
systems might not be meaningful.

The seat counts must be in a dictionary format as returned by votelib's
distributors.

.. [#polrep] "polrep: Calculate Political Representation Scores", Didier
    Ruedin. https://rdrr.io/rforge/polrep/
.. [#kalog] "Measures of disproportionality", Kalogirou.
    http://www2.stat-athens.aueb.gr/~jpan/diatrives/Kalogirou/chapter5.pdf
"""


import math
from typing import Dict, Tuple
from numbers import Number

from votelib.candidate import Candidate


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

    :param votes: Numbers of votes for each candidate.
    :param results: Seat counts awarded to each candidate.

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

    :param votes: Numbers of votes for each candidate.
    :param results: Seat counts awarded to each candidate.

    .. [#lhind] "Loosemore–Hanby index", Wikipedia.
        https://en.wikipedia.org/wiki/Loosemore%E2%80%93Hanby_index
    """
    paired_fractions = _vote_seat_fractions(votes, results)
    return .5 * sum(
        abs(vote_frac - seat_frac)
        for vote_frac, seat_frac in paired_fractions.values()
    )


def rose(votes: Dict[Candidate, Number],
         results: Dict[Candidate, Number],
         ) -> float:
    """Compute the Rose disproportionality index (inverse LH). [#kalog]_

    This is an inverted version of the Loosemore-Hanby index which ranges from
    1 (no disproportionality) to 0 (total disproportionality).

    :param votes: Numbers of votes for each candidate.
    :param results: Seat counts awarded to each candidate.
    """
    return 1 - loosemore_hanby(votes, results)


def rae(votes: Dict[Candidate, Number],
        results: Dict[Candidate, Number],
        ) -> float:
    """Compute Rae's index of disproportionality. [#kalog]_

    Rae's index is the earliest known disproportionality measure. It is known
    to underestimate disproportionality in the presence of small parties.

    :param votes: Numbers of votes for each candidate.
    :param results: Seat counts awarded to each candidate.
    """
    paired_fractions = _vote_seat_fractions(votes, results)
    return sum(
        abs(vote_frac - seat_frac)
        for vote_frac, seat_frac in paired_fractions.values()
    ) / len(paired_fractions)


def lijphart(votes: Dict[Candidate, Number],
             results: Dict[Candidate, Number],
             ) -> float:
    """Compute the Lijphart's index of disproportionality. [#kalog]_

    Lijphart's index takes the single largest difference between vote and seat
    fractions.

    :param votes: Numbers of votes for each candidate.
    :param results: Seat counts awarded to each candidate.
    """
    paired_fractions = _vote_seat_fractions(votes, results)
    return max(
        abs(vote_frac - seat_frac)
        for vote_frac, seat_frac in paired_fractions.values()
    )


def sainte_lague(votes: Dict[Candidate, Number],
                 results: Dict[Candidate, Number],
                 ) -> float:
    """Compute the Sainte-Laguë index of disproportionality. [#kalog]_

    Sainte-Laguë index takes fractional differences.

    :param votes: Numbers of votes for each candidate.
    :param results: Seat counts awarded to each candidate.
    """
    paired_fractions = _vote_seat_fractions(votes, results)
    return sum(
        (vote_frac - seat_frac) ** 2 / vote_frac
        for vote_frac, seat_frac in paired_fractions.values()
    )


def d_hondt(votes: Dict[Candidate, Number],
            results: Dict[Candidate, Number],
            ) -> float:
    """Compute the D'Hondt index of disproportionality. [#kalog]_

    This is the index of disproportionality minimized by the D'Hondt highest
    averages evaluator. It uses the maximum ratio of seats to votes across
    parties.

    :param votes: Numbers of votes for each candidate.
    :param results: Seat counts awarded to each candidate.
    """
    paired_fractions = _vote_seat_fractions(votes, results)
    return max(
        seat_frac / vote_frac
        for vote_frac, seat_frac in paired_fractions.values()
    )


def regression(votes: Dict[Candidate, Number],
               results: Dict[Candidate, Number],
               ) -> float:
    """Compute the regression index of disproportionality. [#kalog]_

    This is obtained by performing linear regression to predict seat fractions
    from vote fractions. If the index is one, the allocation is perfectly
    proportional; values below one signal preference of the system for smaller
    parties, while values above one signal preference for larger parties.

    :param votes: Numbers of votes for each candidate.
    :param results: Seat counts awarded to each candidate.
    """
    num = 0
    denom = 0
    for vote_frac, seat_frac in _vote_seat_fractions(votes, results).values():
        num += vote_frac * seat_frac
        denom += vote_frac ** 2
    return num / denom


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
