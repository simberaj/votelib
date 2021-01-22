
from decimal import Decimal
from numbers import Number
from typing import List, Dict, Tuple, Set, Iterable, Optional, TextIO

import votelib.candidate
from votelib.candidate import Candidate
from votelib.vote import RankedVoteType


BLTSpecContents = Tuple[
    Dict[Tuple[Candidate, ...], Number],    # ranked votes w/o shared ranks
    int,
    List[Candidate],
    Optional[str],
]


def load(blt_file: TextIO, **kwargs) -> BLTSpecContents:
    return _load(blt_file, **kwargs)


def loads(blt_text: str, **kwargs) -> BLTSpecContents:
    return _load(iter(blt_text.split('\n')), **kwargs)


def dump(votes: Dict[Tuple[Candidate, ...], Number],
         n_seats: int,
         candidates: Optional[List[Candidate]] = None,
         election_name: Optional[str] = None,
         blt_file: TextIO,
         **kwargs) -> None:
    for line in _dump(votes, n_seats, candidates, election_name):
        blt_file.write(line + '\n')


def dumps(votes: Dict[Tuple[Candidate, ...], Number],
          n_seats: int,
          candidates: Optional[List[Candidate]] = None,
          election_name: Optional[str] = None,
          **kwargs) -> None:
    return '\n'.join(_dump(votes, n_seats, candidates, election_name))


def _dump(votes: Dict[Tuple[Candidate, ...], Number],
          n_seats: int,
          candidates: Optional[List[Candidate]] = None,
          election_name: Optional[str] = None,
          ) -> None:
    raise NotImplementedError


def _load(blt_lines: Iterable[str],
          oneplus_weights: bool = False,
          ) -> BLTSpecContents:
    try:
        n_cands, n_seats = _parse_header(next(blt_lines))
    except StopIteration as e:
        raise ValueError('empty BLT file') from e
    ballots, withdrawn = _parse_body(
        blt_lines,
        oneplus_weights=oneplus_weights
    )
    candidates, election_name = _parse_strings(blt_lines)
    if candidates is None:
        candidates = _numeric_candidates(n_cands)
    candidates = _form_candidate_objects(candidates, withdrawn)
    true_ballots = _deindex_ballots(ballots, candidates)
    return (
        election_name,
        candidates,
        true_ballots,
        n_seats
    )


def _numeric_candidates(n_cands: int) -> List[str]:
    return [str(i+1) for i in range(n_cands)]


def _form_candidate_objects(cands: List[str],
                            withdrawn: Set[int],
                            ) -> List[votelib.candidate.Person]:
    return [
        votelib.candidate.Person(
            cand,
            number=i+1,
            withdrawn=(i+1 in withdrawn)
        )
        for i, cand in enumerate(cands)
    ]


def _deindex_ballots(ballots: Dict[Tuple[int, ...], Number],
                     cands: List[Candidate]
                     ) -> Dict[Tuple[Candidate, ...], Number]:
    return {
        tuple(cands[i-1] for i in ballot): n_votes
        for ballot, n_votes in ballots.items()
    }


def _parse_header(blt_line: str) -> Tuple[int, int]:
    blt_result = _parse_numline(blt_line, allow_first_decimal=False)
    is_ok = (
        isinstance(blt_result, list)
        and len(blt_result) == 2
        and all(isinstance(num, int) for num in blt_result)
    )
    if is_ok:
        return tuple(blt_result)
    else:
        raise ValueError(f'need two integers (candidate and seat count) in BLT'
                         f'file header line, got {blt_result!r}')


def _parse_body(blt_lines: Iterable[str],
                oneplus_weights: bool = False,
                ) -> Tuple[Dict[Tuple[int, ...], Number], Set[int]]:
    ballots = {}
    withdrawn = set()
    ballots_encountered = False
    for line in blt_lines:
        result = _parse_numline(line, allow_first_decimal=True)
        if isinstance(result, str):
            raise ValueError(f'string line in BLT ballot part: {result!r}')
        elif not result:
            continue    # ignore empty lines
        elif result == [0]:
            # End-of-ballots line, return.
            return ballots, withdrawn
        elif result[0] < 0:
            if ballots_encountered:
                raise ValueError('withdrawn candidate line after ballot line: '
                                 f'{line!r}')
            # Withdrawn candidates. Allow more than one per line.
            withdrawn.update(-n for n in result)
        else:
            weight, ballot = _parse_ballot(result)
            if oneplus_weights and weight < 1:
                raise ValueError(f'ballot weight <1: {line!r}')
            if ballot not in ballots:
                ballots[ballot] = 0
            ballots[ballot] += weight
            ballots_encountered = True
    raise ValueError('incomplete BLT file: EOF before ballot list terminator')


def _parse_strings(blt_lines: Iterable[str]
                   ) -> Tuple[Optional[List[str]], Optional[str]]:
    parsed_lines = []
    for blt_line in blt_lines:
        blt_line = _clean_line(blt_line)
        if blt_line.startswith('"') and blt_line.endswith('"'):
            parsed_lines.append(blt_line[1:-1])
        else:
            raise ValueError(f'invalid BLT string line: {blt_line!r}')
    if not parsed_lines:
        return None, None
    elif len(parsed_lines) == 1:
        return None, parsed_lines[0]
    else:
        return parsed_lines[:-1], parsed_lines[-1]


def _clean_line(blt_line: str) -> str:
    blt_line = blt_line.strip()
    # Ignore everything after the first hash sign after the last double quote.
    hash_search_start = blt_line.rfind('"') if '"' in blt_line else 0
    leftmost_hash = blt_line[hash_search_start:].find('#')
    if leftmost_hash == -1:
        return blt_line
    else:
        return blt_line[:(hash_search_start + leftmost_hash)].rstrip()


def _parse_ballot(nums: List[Number]) -> Tuple[Number, Tuple[int, ...]]:
    # Assumes a line with at least one leading non-zero element, all elements
    # apart from the first one are assumed to be integers.
    # Check the trailing zero and strip it.
    if nums[-1] != 0:
        raise ValueError(f'ballot line must be zero-terminated, got {nums!r}')
    nums = nums[:-1]
    # The first element is weight, the rest are candidate indices.
    return nums[0], tuple(nums[1:])


def _parse_numline(blt_line: str,
                   allow_first_decimal: bool = False,
                   ) -> List[Number]:
    blt_line = _clean_line(blt_line)
    # Return empty lines as None.
    if not blt_line:
        return []
    # Split the line by spaces to obtain numbers.
    nums = []
    for i, numstr in enumerate(blt_line.split()):
        if numstr.isdigit():
            nums.append(int(numstr))
        elif i == 0 and allow_first_decimal:
            nums.append(Decimal(numstr))
        else:
            raise ValueError(f'invalid BLT numberline item: {numstr!r}'
                             f'(first decimal item'
                             f'allowed: {allow_first_decimal})')
    return nums
