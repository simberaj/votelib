
import re
from decimal import Decimal
from numbers import Number
from typing import List, Dict, Tuple, Set, Iterable, Optional, TextIO, Union

import votelib.candidate
import votelib.vote
import votelib.io.core
from votelib.candidate import Candidate


ABIFSpecContents = Dict[votelib.vote.AnyVoteType, Number]

SHORTHAND_PATTERN = r'[A-Za-z]+'
RE_SHORTHAND_TOKEN = re.compile(SHORTHAND_PATTERN)
RE_CANDIDATE_TOKEN = re.compile(r'((?:\[.+?\])|(?:' + SHORTHAND_PATTERN + '))')
# RE_SCORE = re.compile('[0-9]+(?:\.[0-9]+)?')

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
    raise NotImplementedError


# TODO spec uncertainties, simple vote conversion, streamline vote type detection, headers?
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
        elif line[0] == '[':
            shorthand, cand_string = _parse_candidate_mapping(line)
            shorthands[shorthand] = cand_string
        elif line[0] not in ('{', '#'):
            # Skip metadata, comments and empty lines, otherwise give an error.
            raise ABIFParseError(f'invalid line: {line!r}')
    return votes


def _parse_vote_line(line: str,
                     shorthands: Dict[str, str],
                     ) -> Tuple[votelib.vote.AnyVoteType, Number]:
    number, vote_part = line.split(':', 1)
    return (
        _parse_vote(vote_part.strip(), shorthands)[0],
        _parse_number(number.strip(), 'vote count')
    )


def _parse_number(numstr: str, oftype: str = 'ABIF') -> Union[int, Decimal]:
    if numstr.isdigit():
        return int(numstr)
    elif '.' in numstr and numstr.replace('.', '').isdigit():
        return Decimal(numstr)
    else:
        raise ABIFParseError(f'invalid {oftype} number: {numstr!r}')


def _parse_vote(vote_str: str,
                shorthands: Dict[str, str],
                ) -> Tuple[votelib.vote.AnyVoteType, str]:
    tokens = _tokenize_vote(vote_str)
    vote_type = _get_vote_type(tokens)
    print(tokens, vote_type)
    return VOTE_PARSERS[vote_type](tokens, shorthands), vote_type


def _tokenize_vote(vote_str: str) -> List[str]:
    tokens = [token.strip() for token in RE_CANDIDATE_TOKEN.split(vote_str)]
    if tokens[0] != '':
        raise ABIFParseError(f'vote line does not start with candidate token: {vote_str!r}')
    tokens = tokens[1:]
    cut_at = None
    # Find comments and delete them.
    for i, token in enumerate(tokens):
        if token and token[0] == '#':
            cut_at = i
            break
    if cut_at is not None:
        tokens = tokens[:cut_at]
    else:
        if tokens[-1] != '':
            raise ABIFParseError(f'vote line does not end with candidate token: {vote_str!r}')
        tokens = tokens[:-1]
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
            raise ABIFParseError(f'invalid token in approval vote: {token}')
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
            raise ABIFParseError(f'invalid token in ranked vote: {token}')
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
                raise ABIFParseError(f'expecting slash in score vote, got {token}')
        elif expect == 'score':
            current_score = _parse_number(token, 'score')
            expect = 'sep'
        elif expect == 'sep':
            if token in ('>', '=', ','):
                expect = 'cand'
                scores.append((current_cand, current_score))
            else:
                raise ABIFParseError(f'expecting separator in score vote, got {token}')
        else:
            raise ABIFParseError
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
        raise ABIFParseError(f'invalid candidate token: {token}')
