"""Shared functionality for ballot/election file I/O. Internal."""

from __future__ import annotations

import dataclasses
import typing
from numbers import Real
from typing import Any, List, Dict, Tuple, Callable, Iterable, TextIO, TypeVar, Optional

import votelib.system
from votelib.candidate import Candidate
from votelib.vote import AnyVoteType

FilePayload = TypeVar('FilePayload')


class NotSupportedInFormat(Exception):
    """Signals that the given element is not supported by the I/O format."""

    FORMAT: str = NotImplemented

    def __init__(self, what: str):
        super().__init__(f'{what} not supported by {self.FORMAT}')


class ParseError(Exception):
    """An input that is invalid according to the given format was detected."""
    pass


@dataclasses.dataclass
class VotingSetup:
    """A container for data returnable from a ballot file."""
    votes: Dict[AnyVoteType, Real]
    system: Optional[votelib.system.VotingSystem] = None
    n_seats: Optional[int] = None
    candidates: Optional[List[Candidate]] = None
    election_name: Optional[str] = None


def loaders(line_loader: Callable[..., VotingSetup]
            ) -> Tuple[Callable[..., VotingSetup], Callable[..., VotingSetup]]:
    """Create load() and loads() functions from an iterating function."""
    return_annot = typing.get_type_hints(line_loader).get('return')
    if return_annot is None:
        return_annot = Any

    def load(file: TextIO, **kwargs) -> return_annot:
        return line_loader(file, **kwargs)

    def loads(text: str, **kwargs) -> return_annot:
        return line_loader(iter(text.split('\n')), **kwargs)

    return load, loads


def dumpers(line_dumper: Callable[..., Iterable[str]]
            ) -> Tuple[Callable[..., None], Callable[..., str]]:
    """Create dump() and dumps() functions from a line generator function."""

    def dump(blt_file: TextIO, *args, **kwargs) -> None:
        for line in line_dumper(*args, **kwargs):
            if not line.endswith('\n'):
                line += '\n'
            blt_file.write(line)

    def dumps(*args, **kwargs) -> str:
        return ''.join(
            line + ('' if line.endswith('\n') else '\n')
            for line in line_dumper(*args, **kwargs)
        )

    return dump, dumps
