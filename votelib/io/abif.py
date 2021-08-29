
import re
from decimal import Decimal
from numbers import Number
from typing import List, Dict, Tuple, Set, Iterable, Optional, TextIO, Union, Callable

import votelib.candidate
import votelib.vote
import votelib.io.core
from votelib.candidate import Candidate


ABIFSpecContents = Dict[votelib.vote.AnyVoteType, Number]

SHORTHAND_PATTERN = r'[A-Za-z]+'
FULLNAME_PATTERN = r'\[.+?\]'
RE_SHORTHAND_TOKEN = re.compile(SHORTHAND_PATTERN)
RE_FULLNAME_TOKEN = re.compile(FULLNAME_PATTERN)
RE_CANDIDATE_TOKEN = re.compile(r'((?:' + FULLNAME_PATTERN + ')|(?:' + SHORTHAND_PATTERN + '))')
RE_VOTE_COUNT_DELIMITER = re.compile(':|[*]')
# RE_SCORE = re.compile('[0-9]+(?:\.[0-9]+)?')


class NotSupportedInABIF(votelib.io.core.NotSupportedInFormat):
    FORMAT = 'ABIF file'


class ABIFParseError(votelib.io.core.ParseError):
    pass


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
    if votes:
        vote_serializer = _get_vote_serializer(next(iter(votes.keys())))
        for vote, num in votes.items():
            num_str = _dump_number(num)
            vote_str = vote_serializer(vote)
            yield f'{num_str}: {vote_str}'
    else:
        yield ''


def _get_vote_serializer(vote: votelib.vote.AnyVoteType) -> Callable[[votelib.vote.AnyVoteType], str]:
    if isinstance(vote, frozenset):
        if all(isinstance(item, tuple) and len(item) == 2 for item in vote):
            return _dump_score_vote
        else:
            return _dump_approval_vote
    elif isinstance(vote, tuple):
        return _dump_ranked_vote
    else:
        return _dump_candidate


def _dump_candidate(candidate: Candidate) -> str:
    if hasattr(candidate, 'name') and candidate.name is not None:
        cand_str = candidate.name
    else:
        cand_str = str(candidate)
    if ']' in cand_str:
        raise NotSupportedInABIF(f'right square bracket in candidate name: {cand_str}')
    elif RE_SHORTHAND_TOKEN.fullmatch(cand_str):
        return cand_str
    else:
        return '[' + cand_str + ']'


def _dump_approval_vote(vote: votelib.vote.ApprovalVoteType) -> str:
    return ', '.join(_dump_candidate(item) for item in vote)


def _dump_ranked_vote(vote: votelib.vote.RankedVoteType) -> str:
    return '>'.join(
        (
            '='.join(
                _dump_candidate(eqranked) for eqranked in item
            )
            if isinstance(item, frozenset)
            else _dump_candidate(item)
        )
        for item in vote
    )


def _dump_score_vote(vote: votelib.vote.ScoreVoteType) -> str:
    return ', '.join(
        '/'.join((_dump_candidate(cand), _dump_number(score)))
        for cand, score in vote
    )


def _dump_number(number: Number) -> str:
    if isinstance(number, int):
        return str(number)
    else:
        raise NotSupportedInABIF(f'invalid number type: {type(number)} ({number})')


# TODO spec uncertainties, testcase for simple vote conversion, streamline vote type detection, headers?
def _load(abif_lines: Iterable[str]) -> ABIFSpecContents:
    votes = {}
    shorthands = {}
    vote_validator = None
    for line in abif_lines:
        line = line.strip()
        if not line:
            continue
        elif line[0].isdigit():
            # Vote line.
            vote, n = _parse_vote_line(line, shorthands)
            # if votes:
                # vote_validator.validate(vote)
            # else:
                # vote_validator = _create_vote_validator(vote)
            if vote not in votes:
                votes[vote] = 0
            votes[vote] += n
        elif line[0] == '=':
            shorthand, cand_string = _parse_candidate_mapping(line[1:].lstrip())
            shorthands[shorthand] = cand_string
        elif line[0] not in ('{', '#'):
            # Skip metadata, comments and empty lines, otherwise give an error.
            raise ABIFParseError(f'invalid line: {line!r}')
    if _holds_simple_votes(votes):
        votes = {vote.pop(): n_votes for vote, n_votes in votes.items()}
    return votes


def _holds_simple_votes(votes: Dict[votelib.vote.AnyVoteType, Number]) -> bool:
    for vote in votes.keys():
        if not isinstance(vote, frozenset):
            return False
        elif vote and len(vote) > 1:
            return False
        elif vote and isinstance(vote[0], tuple):
            return False
    return True


def _parse_vote_line(line: str,
                     shorthands: Dict[str, str],
                     ) -> Tuple[votelib.vote.AnyVoteType, Number]:
    number, vote_part = RE_VOTE_COUNT_DELIMITER.split(line, maxsplit=1)
    return (
        _parse_vote(vote_part.strip(), shorthands)[0],
        _parse_number(number.strip(), 'vote count')
    )


def _parse_number(numstr: str, oftype: str = 'ABIF') -> Union[int, Decimal]:
    if numstr.isdigit():
        return int(numstr)
    else:
        raise ABIFParseError(f'invalid {oftype} number: {numstr!r}')


def _parse_vote(vote_str: str,
                shorthands: Dict[str, str],
                ) -> Tuple[votelib.vote.AnyVoteType, str]:
    tokens = _tokenize_vote(vote_str)
    vote_type = _get_vote_type(tokens)
    return VOTE_PARSERS[vote_type](tokens, shorthands), vote_type


def _tokenize_vote(vote_str: str) -> List[str]:
    tokens = []
    # print('TOKENIZING', vote_str)
    for i, token in enumerate(RE_CANDIDATE_TOKEN.split(vote_str)):
        leftover_token = None
        seen_slash = False
        token = token.strip()
        # print(i, repr(token))
        if i == 0:
            if token:
                raise ABIFParseError(f'vote line does not start with candidate token: {vote_str!r}')
        elif i % 2 == 0:
            # non-candidate token, split it if necessary
            if '#' in token:
                token = token[:token.find('#')].rstrip()
            if token and token[0] == '/':
                tokens.append('/')
                token = token[1:].lstrip()
                seen_slash = True
            if token and token[-1] in ('>', '=', ','):
                leftover_token = token[-1]
                token = token[:-1].rstrip()
            if token and seen_slash:
                # anything left over must be a score
                tokens.append(token)
                token = ''
            if token:
                raise ABIFParseError(f'unrecognized vote line chunk: {token!r} in {vote_str!r}')
            if leftover_token:
                tokens.append(leftover_token)
        elif not token:
            raise ABIFParseError(f'empty candidate token at {vote_str!r}')
        else:
            tokens.append(token)
    return tokens


def _get_vote_type(tokens: List[str]) -> Union[str, None]:
    if '/' in tokens:
        return 'score'
    elif '>' in tokens or '=' in tokens:
        return 'ranked'
    elif ',' in tokens:
        return 'list'
    else:
        return None


def _parse_list_tokens(tokens: List[str],
                       shorthands: Dict[str, str],
                       ) -> votelib.vote.ApprovalVoteType:
    # Expecting alternating candidate tokens and commas.
    expect_cand = True
    cands = []
    for token in tokens:
        if expect_cand:
            cands.append(_parse_candidate_token(token, shorthands))
            expect_cand = False
        elif token == ',':
            expect_cand = True
        else:
            raise ABIFParseError(f'invalid token in approval vote: {token!r}')
    return frozenset(cands)


def _parse_ranked_tokens(tokens: List[str],
                         shorthands: Dict[str, str],
                         ) -> votelib.vote.RankedVoteType:
    # Expecting alternating candidate tokens and >/= signs.
    expect_cand = True
    all_ranks = []
    last_rank = []
    for token in tokens:
        if expect_cand:
            last_rank.append(_parse_candidate_token(token, shorthands))
            expect_cand = False
        elif token == '>':
            all_ranks.append(last_rank)
            last_rank = []
            expect_cand = True
        elif token == '=':
            expect_cand = True
        else:
            raise ABIFParseError(f'invalid token in ranked vote: {token!r}')
    return tuple(
        frozenset(rank) if len(rank) > 1 else rank[0]
        for rank in all_ranks + [last_rank]
    )


def _parse_score_tokens(tokens: List[str],
                        shorthands: Dict[str, str],
                        ) -> votelib.vote.RankedVoteType:
    # Expecting alternating candidate tokens, scores, and >/=/, signs.
    expect = 'cand'
    scores = []
    current_cand = None
    current_score = None
    for token in tokens:
        if expect == 'cand':
            current_cand = _parse_candidate_token(token, shorthands)
            expect = 'slash'
        elif expect == 'slash':
            if token == '/':
                expect = 'score'
            else:
                raise ABIFParseError(f'expecting slash in score vote, got {token!r}')
        elif expect == 'score':
            current_score = _parse_number(token, 'score')
            expect = 'sep'
        elif expect == 'sep':
            if token in ('>', '=', ','):
                expect = 'cand'
                scores.append((current_cand, current_score))
                current_cand = None
                current_score = None
            else:
                raise ABIFParseError(f'expecting separator in score vote, got {token!r}')
        else:
            raise ABIFParseError
    if expect == 'sep':
        scores.append((current_cand, current_score))
        current_cand = None
        current_score = None
    if current_cand or current_score:
        raise ABIFParseError(f'score vote line not properly terminated, '
                             f'leftover candidate {current_cand} and score {current_score}')
    return frozenset(scores)


VOTE_PARSERS = {
    None: _parse_list_tokens,
    'list': _parse_list_tokens,
    'ranked': _parse_ranked_tokens,
    'score': _parse_score_tokens,
}


def _parse_candidate_token(token: str, shorthands: Dict[str, str]) -> str:
    if token[0] == '[' and token[-1] == ']':
        return token[1:-1]
    elif token in shorthands:
        return shorthands[token]
    elif RE_SHORTHAND_TOKEN.fullmatch(token):
        return token
    else:
        raise ABIFParseError(f'invalid candidate token: {token!r}')


def _parse_candidate_mapping(line: str) -> Tuple[str, str]:
    shorthand_match = RE_SHORTHAND_TOKEN.match(line)
    if shorthand_match is None:
        raise ABIFParseError(f'did not find shorthand in candidate full name'
                             f'mapping line: {line!r}')
    shorthand = shorthand_match.group(0)
    restof_line = line[len(shorthand):].lstrip()
    if restof_line[0] != ':':
        raise ABIFParseError(f'invalid candidate full name mapping: shorthand '
                             f'token must be followed by colon, got {restof_line!r}')
    restof_line = restof_line[1:].lstrip()
    fullname_match = RE_FULLNAME_TOKEN.fullmatch(restof_line)
    if fullname_match is None:
        raise ABIFParseError(f'did not find bracketed candidate full name'
                             f'in mapping line: {restof_line!r}')
    fullname_token = fullname_match.group(0)
    fullname = fullname_token[1:-1]    # strip square brackets
    return shorthand, fullname
