"""Read and write STV format files.

The STV (or STV.pm) files contain cast votes in a ranked election and,
optionally, an exact definition of an election system. [#stvlob]_

.. [#wpav] "STV File Format".
    https://lobitos.net/voting/format.html
"""
import re
import math
import operator
import fractions
import decimal
import collections
import warnings
from typing import List, Tuple, Dict, Union, Iterable, Optional, Collection
from numbers import Number

import votelib
import votelib.convert
import votelib.evaluate
import votelib.evaluate.auxiliary
import votelib.evaluate.sequential
import votelib.io.blt
import votelib.io.core
import votelib.util
import votelib.component.transfer as transfer
from votelib.candidate import Candidate
from votelib.evaluate.sequential import \
    TransferableVoteSelector, TransferableVoteDistributor


SUPPORTED_QUOTAS: List[str] = ['droop', 'hare']


class NotSupportedInSTV(votelib.io.core.NotSupportedInFormat):
    FORMAT = 'STV file'


class STVParseError(votelib.io.core.ParseError):
    pass


def dump_lines(votes: Dict[Tuple[Candidate, ...], Number],
               system: Union[
                   votelib.VotingSystem,
                   votelib.evaluate.Evaluator,
                   None
               ] = None,
               candidates: Optional[List[Candidate]] = None,
               n_seats: Optional[int] = None,
               output_method: bool = True,
               ) -> Iterable[str]:
    """Dump the election data into an STV.pm file.

    :param votes: Ranked votes for the election.
    :param system: The election system (or just an evaluator) used in the
        election.
    :param candidates: List of candidates participating in the election.
        If None, will be inferred from votes.
    :param n_seats: Number of seats contested. Supplying this along with a
        fixed seat count evaluator will result in a duplicate marking in the
        output.
    :param output_method: If True, output the detailed parameters of the
        election system used. Only applies when system is given.
        Setting this to False will omit the vote transfer setup, but it allows
        to output partial STV setups from election systems that are not
        supported by STV files and would thus normally error out (such as
        non-uniform elimination). This parameter does not affect quota setup
        output, which is always attempted.
    """
    if system is not None:
        yield from _dump_system(system, output_method=output_method)
        if n_seats is not None:
            yield f'seats={n_seats}'
        yield from _dump_ballots(votes, candidates)
    else:
        yield 'method=blt'
        yield 'ballots=blt'
        yield from votelib.io.blt.dump_lines(
            votes, n_seats, candidates=candidates
        )


dump, dumps = votelib.io.core.dumpers(dump_lines)


def _dump_system(system: Union[
                     votelib.VotingSystem,
                     votelib.evaluate.Evaluator
                 ],
                 **kwargs) -> Iterable[str]:
    if isinstance(system, votelib.VotingSystem):
        yield f'title={system.name}'
        yield from _dump_system(system.evaluator, **kwargs)
    elif isinstance(system, votelib.evaluate.FixedSeatCount):
        yield f'seats={system.n_seats}'
        yield from _dump_system(system.evaluator, **kwargs)
    elif isinstance(system, votelib.evaluate.TieBreaking):
        yield from _dump_system(system.main, **kwargs)
        yield from _dump_tiebreaker(system.tiebreaker)
    elif isinstance(system, TransferableVoteDistributor):
        warnings.warn('TransferableVoteDistributor class will not be preserved'
                      ' in STV file, will store TransferableVoteSelector'
                      ' instead')
        yield from _dump_tveval(system, **kwargs)
    elif isinstance(system, TransferableVoteSelector):
        yield from _dump_tveval(system._inner, **kwargs)


def _dump_tveval(evaluator: TransferableVoteDistributor,
                 output_method: bool = True,
                 ) -> Iterable[str]:
    if output_method:
        if evaluator.retainer is not None:
            raise NotSupportedInSTV(f'transferable vote retainer'
                                    f'{evaluator.retainer}')
        if evaluator.eliminate_step != -1:
            raise NotSupportedInSTV(f'elimination {evaluator.eliminate_step}')
        if isinstance(evaluator.transferer, transfer.Gregory):
            yield 'method=BC'
        else:
            raise NotSupportedInSTV(f'transfer method {evaluator.transferer}')
    if hasattr(evaluator.quota_function, '__name__'):
        quota_name = evaluator.quota_function.__name__
        if quota_name in SUPPORTED_QUOTAS:
            yield f'quota={evaluator.quota_function.__name__}'
        else:
            raise NotSupportedInSTV(f'quota {quota_name}')
    if getattr(evaluator, 'mandatory_quota', False):
        yield 'quota=mandatory'


ORDER_SELECTORS = (
    votelib.evaluate.auxiliary.InputOrderSelector,
    votelib.evaluate.auxiliary.CandidateNumberRanker,
)


def _dump_tiebreaker(evaluator: votelib.evaluate.Evaluator) -> Iterable[str]:
    if isinstance(evaluator, votelib.evaluate.PreConverted):
        if type(evaluator.converter) not in votelib.convert.RANKED_TO_SIMPLE:
            raise NotSupportedInSTV(f'conversion {evaluator.converter}')
        yield from _dump_tiebreaker(evaluator.evaluator)
    elif isinstance(evaluator, ORDER_SELECTORS):
        yield 'random=non'
    elif isinstance(evaluator, votelib.evaluate.auxiliary.Sortitor):
        if evaluator.seed is not None:
            yield f'random={evaluator.seed}'
    else:
        raise NotSupportedInSTV(f'tiebreaker {evaluator}')


def _dump_ballots(votes: Dict[Tuple[Candidate, ...], Number],
                  candidates: Optional[List[Candidate]] = None,
                  ) -> Iterable[str]:
    # unordered format supported only
    if candidates is None:
        candidates = votelib.util.all_ranked_candidates(votes)
    cand_names = {cand: _candidate_name(cand) for cand in candidates}
    cand_nicks = _candidate_nicks(cand_names)
    for cand in candidates:
        prefix = 'candidate'
        if getattr(cand, 'withdrawn', False):
            prefix = 'withdrawn'
        yield f'{prefix}={cand_nicks[cand]} {cand_names[cand]}'
    yield f'ballots={len(votes)}'
    for ranking, n_votes in votes.items():
        multiplier = f'{n_votes}X ' if n_votes != 1 else ''
        yield multiplier + _ranking_to_str(ranking, cand_nicks)
    yield 'end'


def _ranking_to_str(ranking: Tuple[Candidate, ...],
                    nicks: Dict[Candidate, str],
                    ) -> str:
    try:
        return ' '.join(nicks[cand] for cand in ranking)
    except KeyError as err:
        if err.args and isinstance(err.args[0], collections.abc.Set):
            raise NotSupportedInSTV(f'equal rankings: {ranking}')
        else:
            raise err


def _candidate_name(candidate: Candidate) -> str:
    if isinstance(candidate, str):
        return candidate
    elif getattr(candidate, 'name', None) is not None:
        return candidate.name
    else:
        return str(candidate)


def _candidate_nicks(cand_names: Dict[Candidate, str]) -> Dict[Candidate, str]:
    all_initials = []
    for cand_name in cand_names.values():
        cand_initials = _name_to_initials(cand_name)
        if cand_initials in all_initials:    # duplicate, fall back to trivial
            return _ordinal_candidate_nicks(cand_names.keys())
        else:
            all_initials.append(cand_initials)
    return dict(zip(cand_names.keys(), all_initials))


def _name_to_initials(name: str) -> str:
    return ''.join(part[0].lower() for part in re.split(r'\W', name))


def _ordinal_candidate_nicks(cand_names: Collection[Candidate]
                             ) -> Dict[Candidate, str]:
    n_letters = int(math.ceil(math.log(len(cand_names)) / math.log(26)))
    nicks = {}
    for cand_i, cand in enumerate(cand_names):
        nick_letters = []
        for letter_i in range(n_letters):
            nick_letters.append(chr(97 + cand_i % 26))
            cand_i //= 26
        nicks[cand] = ''.join(nick_letters)
    return nicks


def load_lines(lines: Iterable[str]) -> Tuple[
                   Dict[Tuple[Candidate, ...], Number],
                   Optional[votelib.VotingSystem],
                   List[Candidate],
               ]:
    system, candidates, nicks, n_ballots, is_ordered = _load_system(lines)
    if n_ballots is None:
        # BLT mode invoked, the rest of the file is in BLT format.
        try:
            votes, blt_n_seats, blt_candidates, election_name = \
                votelib.io.blt.load_lines(lines)
        except votelib.io.blt.BLTParseError as err:
            raise STVParseError('BLT content parsing failed') from err
        # Replace the STV config results with the BLT data where applicable.
        if system.name is None and election_name:
            system.name = election_name
        system.evaluator = votelib.evaluate.FixedSeatCount(
            system.evaluator, blt_n_seats
        )
        if not candidates and blt_candidates:
            candidates = blt_candidates
    else:
        loader = _load_ordered_votes if is_ordered else _load_unordered_votes
        votes = loader(_iter_vote_lines(lines, n_ballots), nicks)
    return votes, system, candidates


def _load_system(lines: Iterable[str]) -> Tuple[
                     Optional[votelib.VotingSystem],
                     List[Candidate],
                     Dict[str, Candidate],
                     Optional[int],
                     bool,
                 ]:
    syscomps = {}
    candidates = []
    nicks = {}
    nick_orders = []
    for line in lines:
        key, value = _parse_header_line(line)
        if key is None:
            continue    # comment or empty line
        elif key == 'ballots':
            if nick_orders:
                # reorder nicks into order= spec
                nicks = {nick: nicks[nick] for nick in nick_orders}
            return (
                _create_system(**syscomps), candidates, nicks,
                _parse_n_ballots(value), bool(nick_orders)
            )
        elif key == 'order':
            nick_orders = value.split()
        elif key in ('candidate', 'withdrawn'):
            nick, name = value.split(None, 1)
            cand = votelib.candidate.Person(
                name,
                number=len(candidates)+1,
                withdrawn=(key == 'withdrawn'),
            )
            candidates.append(cand)
            nicks[nick] = cand
        elif key in syscomps:
            syscomps[key] = (syscomps[key], value)
        else:
            syscomps[key] = value
    raise STVParseError('end of file before ballot data')


def _parse_header_line(line: str) -> Tuple[str, str]:
    if '#' in line:
        line = line[:line.find('#')]
    line = line.strip()
    if not line:
        return None, None
    if '=' in line:
        return line.split('=', 1)
    else:
        raise STVParseError(f'invalid STV header line: {line!r}')


def _parse_n_ballots(value: str) -> Optional[int]:
    if value == 'blt':
        return None
    elif value.isdigit():
        return int(value)
    else:
        raise STVParseError(f'invalid ballot count: {value!r}')


def _iter_vote_lines(lines: Iterable[str],
                     n_ballots: int,
                     ) -> Iterable[Tuple[Number, List[str]]]:
    has_ended = False
    for i, line in enumerate(lines):
        line = line.strip()
        if line == 'end':
            if i != n_ballots:
                raise STVParseError(f'expected {n_ballots} ballots, got {i}')
            has_ended = True
            break
        if not line:
            continue
        items = line.split()
        if items[0].endswith('X'):
            yield _parse_multiplier(items[0][:-1], i), items[1:]
        else:
            yield 1, items
    if not has_ended:
        raise STVParseError('no "end" terminator line')


def _parse_multiplier(mult: str, line_i: int) -> Number:
    inner_err = None
    try:
        if '/' in mult:
            return fractions.Fraction(mult)
        elif '.' in mult:
            return decimal.Decimal(mult)
        elif mult.isdigit():
            return int(mult)
    except ValueError as err:
        inner_err = err
    parse_err = STVParseError(f'invalid vote weight multiplier: {mult!r}'
                              f'on ballot line {line_i}')
    if inner_err is not None:
        raise parse_err from inner_err
    else:
        raise parse_err


def _load_ordered_votes(lines: Iterable[Tuple[Number, List[str]]],
                        nicks: Dict[str, Candidate],
                        ) -> Dict[Tuple[Candidate, ...], Number]:
    votes = collections.defaultdict(int)
    candidates = list(nicks.values())
    for line_i, line_cont in enumerate(lines):
        mult, items = line_cont
        cand_order = []
        for item_i, item in enumerate(items):
            if item.isdigit():
                cand_order.append((candidates[item_i], int(item)))
            elif item != '-':
                raise STVParseError(f'invalid ordered vote item: {item!r}'
                                    f'on ballot line {line_i}')
        cand_order.sort(key=operator.itemgetter(1))
        vote, indices = zip(*cand_order)
        if indices != tuple(range(1, len(indices)+1)):
            raise STVParseError(f'invalid ranking indices: {indices!r}'
                                f' on ballot line {line_i}')
        votes[vote] += mult
    return votes


def _load_unordered_votes(lines: Iterable[Tuple[Number, List[str]]],
                          nicks: Dict[str, Candidate],
                          ) -> Dict[Tuple[Candidate, ...], Number]:
    votes = collections.defaultdict(int)
    for line_i, line_cont in enumerate(lines):
        mult, items = line_cont
        try:
            vote = tuple(nicks[item] for item in items)
        except KeyError as err:
            raise STVParseError(f'unknown candidate in ballot line {line_i}') \
                from err
        votes[vote] += mult
    return votes


def _create_system(title: Optional[str] = None,
                   method: Optional[str] = None,
                   quota: Optional[Union[str, Tuple[str, str]]] = None,
                   seats: Optional[str] = None,
                   random: Optional[str] = None,
                   ) -> votelib.VotingSystem:
    if title is not None and not isinstance(title, str):
        if isinstance(title, tuple):
            raise STVParseError('duplicate election title')
        else:
            raise STVParseError(f'invalid election title: {title!r}')
    return votelib.VotingSystem(title, _create_evaluator(
        method=method, quota=quota, seats=seats, random=random
    ))


def _create_evaluator(method: Optional[str] = None,
                      quota: Optional[Union[str, Tuple[str, str]]] = None,
                      seats: Optional[str] = None,
                      random: Optional[str] = None,
                      ) -> votelib.evaluate.Evaluator:
    mandatory_quota = False
    if method == 'GPCA2000':
        method = 'BC'
        quota = ('droop', 'mandatory')
    if method == 'BC':
        transferer = 'Gregory'
    elif not method:
        raise STVParseError('STV method not found')
    elif method != 'blt':
        raise NotImplementedError(f'STV method not implemented: {method!r}')
    if isinstance(quota, tuple):
        if len(quota) > 2:
            raise STVParseError(f'too many quota settings: {quota!r}')
        elif 'mandatory' in quota:
            mandatory_quota = True
            quota = tuple(item for item in quota if item != 'mandatory')[0]
        else:
            raise STVParseError(f'unknown quota settings: {quota!r}')
    if quota is None:
        if method != 'blt':
            raise STVParseError('quota setting not found')
        # otherwise, we will not need quota_function
    elif quota.isdigit():
        quota_function = votelib.component.quota.constant(int(quota))
    else:
        try:
            quota_function = votelib.component.quota.get(quota)
        except KeyError:
            raise STVParseError(f'unknown quota type: {quota!r}')
    if method == 'blt':
        evaluator = votelib.evaluate.UnknownEvaluator()
    else:
        evaluator = TransferableVoteSelector(
            quota_function=quota_function,
            transferer=transferer,
            mandatory_quota=mandatory_quota,
        )
    if random:
        evaluator = _add_tiebreaker(evaluator, random)
    if seats:
        evaluator = _add_fixed_seats(evaluator, seats)
    return evaluator


def _add_tiebreaker(evaluator: votelib.evaluate.Evaluator,
                    random: str,
                    ) -> votelib.evaluate.Evaluator:
    if random == 'non':
        tiebreaker = votelib.evaluate.auxiliary.CandidateNumberRanker()
    elif random.isdigit():
        tiebreaker = votelib.evaluate.auxiliary.Sortitor(seed=int(random))
    else:
        raise STVParseError('invalid random= parameter: {random!r}')
    return votelib.evaluate.TieBreaking(
        evaluator,
        votelib.evaluate.PreConverted(
            votelib.convert.RankedToPresenceCounts(),
            tiebreaker
        )
    )


def _add_fixed_seats(evaluator: votelib.evaluate.Evaluator,
                     seats: str,
                     ) -> votelib.evaluate.FixedSeatCount:
    try:
        n_seats = int(seats)
    except ValueError as err:
        raise STVParseError(f'invalid seat count: {seats!r}') from err
    return votelib.evaluate.FixedSeatCount(
        evaluator, n_seats=n_seats
    )


load, loads = votelib.io.core.loaders(load_lines)
