
from decimal import Decimal
from numbers import Number
from typing import List, Dict, Tuple, Set, Iterable, Optional, TextIO

import votelib.candidate
import votelib.vote
from votelib.candidate import Candidate


ABIFSpecContents = Dict[votelib.vote.AnyVoteType, Number]


def load(abif_file: TextIO, **kwargs) -> ABIFSpecContents:
    return _load(abif_file, **kwargs)


def loads(abif_text: str, **kwargs) -> ABIFSpecContents:
    return _load(iter(abif_text.split('\n')), **kwargs)


def dump(abif_file: TextIO,
         votes: Dict[votelib.vote.AnyVoteType, Number],
         **kwargs) -> None:
    for line in _dump(votes):
        abif_file.write(line + '\n')


def dumps(votes: Dict[votelib.vote.AnyVoteType, Number],
          **kwargs) -> None:
    return '\n'.join(_dump(votes))


def _dump(votes: Dict[votelib.vote.AnyVoteType, Number]) -> Iterable[str]:
    raise NotImplementedError


def _load(abif_lines: Iterable[str]) -> ABIFSpecContents:
    raise NotImplementedError
