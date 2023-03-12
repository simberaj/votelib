import math
from numbers import Real
from typing import Dict, Optional, List, Iterable, Union, Tuple

from votelib.candidate import Candidate


def minimal_feasible_coalitions(
    seats: Dict[Candidate, int],
    disallowed_links: Optional[Dict[Candidate, List[Candidate]]] = None,
    min_seats: Union[int, Real, None] = None,
    min_margin: Union[int, Real, None] = None,
) -> Dict[Tuple[Candidate, ...], int]:
    """Find coalitions of parties that command a sufficient number of seats.

    Creates minimal coalitions (i.e. coalitions where no party can be removed
    if the specified minimum number of seats is to be reached).

    :param seats: Numbers of seats commanded by each party. Might be reused
        directly from a distribution election evaluator.
    :param disallowed_links: For each party, a list of parties it is not
        permitted to make a coalition with.
    :param min_seats: Minimum number of seats the coalition has to command.
        If a number between 0 and 1, it will be interpreted as a fraction of
        total seats required (this is useful when the coalition wants to
        attain a higher quorum, e.g. to change the constitution or other
        entrenched law). If None, the minimum number of seats is calculated
        from min_margin; if that is also None, a simple majority (0.5) is used.
    :param min_margin: Minimum number of seats that the coalition has to have
        extra against the coalition. This is useful to find more stable
        coalitions (e.g. setting the margin to 2 disallows coalitions that
        would be directly dependent on any one of its representatives).
    :return: A mapping from coalitions that satisfy the given constraints
        to their seat counts. The coalition parties are ordered from the
        strongest party to the weakest; the coalitions are ordered by number
        of parties ascending, then seat count descending.
    """
    coalitions: Dict[Tuple[Candidate, ...], int] = {}
    total_seats = sum(seats.values())
    min_coalition_seats = _determine_min_coalition_seats(
        total_seats=total_seats,
        min_seats=min_seats,
        min_margin=min_margin,
    )
    for candidate in sorted(seats, key=seats.get, reverse=True):
        candidate_coalitions = _expand_coalition(
            coalition=(candidate, ),
            current_seats=seats[candidate],
            seats=seats,
            min_seats=min_coalition_seats,
            disallowed_links=disallowed_links,
        )
        for coalition in candidate_coalitions:
            coalitions[coalition] = sum(seats[cand] for cand in coalition)
    return dict(sorted(
        coalitions.items(),
        key=lambda item: len(item[0]) - item[1] / (2 * total_seats),
    ))


def _determine_min_coalition_seats(
    total_seats: int,
    min_seats: Union[int, float, None] = None,
    min_margin: Union[int, float, None] = None,
) -> int:
    if min_seats is None:
        if min_margin is not None:
            if 0 < min_margin < 1:
                min_abs_margin = min_margin
            else:
                min_abs_margin = min_margin
            min_coal_seats = (total_seats + min_abs_margin) / 2
        else:
            min_coal_seats = total_seats / 2  # simple majority
    elif 0 < min_seats < 1:
        min_coal_seats = total_seats * min_seats
    else:
        min_coal_seats = min_seats
    return int(math.ceil(min_coal_seats))


def _expand_coalition(
    coalition: Tuple[Candidate, ...],
    current_seats: int,
    seats: Dict[Candidate, int],
    min_seats: int,
    disallowed_links: Optional[Dict[Candidate, List[Candidate]]] = None,
) -> Iterable[Tuple[Candidate, ...]]:
    if current_seats >= min_seats:
        yield coalition
    else:
        min_in_coalition = min(seats[cand] for cand in coalition)
        options = set(
            cand for cand in seats
            if cand not in coalition and seats[cand] <= min_in_coalition
        )
        if disallowed_links:
            current_disallowed = set()
            for coal_cand in coalition:
                current_disallowed |= set(disallowed_links.get(coal_cand, []))
            for cand in options:
                if set(coalition) & set(disallowed_links.get(cand, [])):
                    current_disallowed.add(cand)
            options -= current_disallowed
        sorted_options = sorted(options, key=seats.get, reverse=True)
        for expand_opt_cand in sorted_options:
            yield from _expand_coalition(
                coalition + (expand_opt_cand, ),
                current_seats + seats[expand_opt_cand],
                seats=seats,
                min_seats=min_seats,
                disallowed_links=disallowed_links,
            )
