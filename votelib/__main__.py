"""A commandline tool for quick evaluation of some types of elections.

Can evaluate single-constituency elections with any vote type, selections
and distributions alike, and compare many comparable systems.
"""

import argparse
import io
import logging
import sys
import warnings
from numbers import Real
from typing import Optional, List, Dict, Union

import votelib.util
import votelib.io.blt
import votelib.io.stv
from votelib.candidate import Candidate
from votelib.io.core import ElectionData
from votelib.system import VotingSystem
from votelib.vote import AnyVoteType, SimpleVoteType, ApprovalVoteType, \
    RankedVoteType, ScoreVoteType

argparser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
argparser.add_argument(
    '-i', '--input-file',
    type=argparse.FileType('r', encoding='utf8'),
    help='file to load input votes from',
)
argparser.add_argument(
    '-I', '--use-stdin',
    action='store_true',
    help='load input votes from standard input',
)
argparser.add_argument(
    '-s', '--system',
    nargs='*',
    help='voting systems to use',
)
argparser.add_argument(
    '-n', '--n-seats',
    type=int,
    help=(
        'award this many seats in the election (may override the number'
        ' given in the input votes file); default (None) gives preference'
        ' to the votes file and fills in 1 (single-winner election)'
        ' if there is no setup'
    ),
)
argparser.add_argument(
    '-d', '--is-distribution',
    action='store_true',
    help=(
        'sets a distribution election (one candidate might get'
        ' multiple seats)'
    ),
)
argparser.add_argument(
    '-f', '--input-format',
    help='format of input vote data',
    default='blt',
)
argparser.add_argument(
    '-v', '--verbose',
    action='store_true',
    help='show all evaluator log messages and other info',
)
argparser.add_argument(
    '-q', '--quiet',
    action='store_true',
    help='do not show any evaluator log messages or other info',
)

INPUT_FORMATS = {
    # 'abif': votelib.io.abif.load,
    'blt': votelib.io.blt.load,
    'stv': votelib.io.stv.load,
}
VOTE_TYPE_NAMES = {
    SimpleVoteType: 'simple',
    ApprovalVoteType: 'approval',
    RankedVoteType: 'ranked',
    ScoreVoteType: 'score'
}


def main(input_file: io.TextIOBase,
         use_stdin: bool = False,
         system: Optional[List[str]] = None,
         n_seats: Optional[int] = None,
         is_distribution: bool = False,
         input_format: str = 'blt',
         verbose: bool = False,
         quiet: bool = False,
         ) -> None:
    logging.basicConfig(
        level=(
            logging.DEBUG if verbose
            else (logging.WARNING if quiet else logging.INFO)
        ),
        format='%(levelname)-10s %(message)s'
    )
    if use_stdin:
        input_file = sys.stdin
    voting_setup = load_votes(input_file, input_format=input_format)
    votes = voting_setup.votes
    if not votes:
        warnings.warn('empty votes: cannot evaluate election, terminating')
        return
    if n_seats is None:
        if voting_setup.n_seats:
            n_seats = voting_setup.n_seats
        else:
            n_seats = 1
    if voting_setup.system and not system:
        use_systems = {voting_setup.system.name: voting_setup.system}
    else:
        use_systems = gather_systems(
            selected_keys=system,
            is_distribution=is_distribution,
            vote_type=votelib.vote.detect_vote_type(next(iter(votes))),
        )
    if not use_systems:
        warnings.warn('no voting systems selected, terminating')
        return
    elif len(use_systems) == 1:
        run_one_system(use_systems[next(iter(use_systems))], votes, n_seats)
    else:
        run_many_systems(use_systems, votes, n_seats)


def load_votes(input_file: io.TextIOBase,
               input_format: str,
               ) -> ElectionData:
    """Load votes from the given file, expecting the given format."""
    try:
        loader = getattr(votelib.io, input_format)
    except AttributeError as e:
        raise ValueError(
            f'invalid input vote file format: {input_format}, '
            'supported: ' + ', '.join(INPUT_FORMATS.keys())
        ) from e
    return loader.load(input_file)


def gather_systems(selected_keys: Optional[List[str]] = None,
                   is_distribution: bool = False,
                   vote_type: type = SimpleVoteType,
                   ) -> Dict[str, VotingSystem]:
    """Select desired voting systems from the available ones."""
    avail_systems = votelib.system.get_available_systems(
        vote_type=vote_type,
        is_distribution=is_distribution,
    )
    if selected_keys is None:
        return avail_systems
    else:
        try:
            return {key: avail_systems[key] for key in selected_keys}
        except KeyError as e:
            raise ValueError(f'unknown voting system {str(e)}, available: '
                             + ', '.join(avail_systems.keys())) from e


def show_vote_stats(votes: Dict[AnyVoteType, Real],
                    n_seats: int,
                    ) -> None:
    vote_type = votelib.vote.detect_vote_type(next(iter(votes)))
    print(f'Received {sum(votes.values())} {VOTE_TYPE_NAMES[vote_type]} votes')
    print(f'Awarding {n_seats} seats')
    all_cands = sorted(votelib.util.all_voted_for_candidates(votes))
    print(f'{len(all_cands)} candidates with any votes cast'
          f' (in alphabetical order):')
    for cand in all_cands:
        print(' ' * 10 + str(cand))


def show_elected_full(result: Union[
                          List[Candidate],
                          Dict[Candidate, int]
                      ]) -> None:
    """Show full results of a single election (without comparison)."""
    rjust = False
    if not result:
        print('Nobody elected')
        return
    elif hasattr(result, 'keys'):
        # distribution election, show seat allocation
        left_col = [str(cand) for cand in result.keys()]
        right_col = [str(result[cand]) for cand in result.keys()]
    elif len(result) == 1:
        # single-winner election, display winner
        left_col = ['Elected']
        right_col = result
    else:
        # selection, show ordering
        left_col = [str(i) for i in range(1, len(result) + 1)]
        right_col = result
        rjust = True
    n_just_chars = len(max(left_col, key=len))
    for left, right in zip(left_col, right_col):
        left_disp = (left.rjust if rjust else left.ljust)(n_just_chars)
        print(left_disp, ' ', right)


def run_one_system(system: VotingSystem,
                   votes: Dict[AnyVoteType, Real],
                   n_seats: int,
                   ) -> None:
    print()
    print(f'Running a {system.name} election')
    show_vote_stats(votes, n_seats)
    print()
    print('Evaluating the election...')
    result = system.evaluator.evaluate(votes, n_seats)
    print()
    print('Election result:')
    show_elected_full(result)


def run_many_systems(systems: Dict[str, VotingSystem],
                     votes: Dict[AnyVoteType, Real],
                     n_seats: int,
                     ) -> None:
    raise NotImplementedError


if __name__ == '__main__':
    args = argparser.parse_args()
    if not args.input_file and not args.use_stdin:
        argparser.print_usage()
    else:
        main(**vars(args))
