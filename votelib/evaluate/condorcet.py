'''Condorcet selection evaluators.

These evaluators work by examining pairwise orderings between candidates
(how many voters prefer one candidate to another), which is also the form of
votes they take in; if you have ranked vote input, use
:class:`votelib.convert.RankedToCondorcetVotes` to convert it first and
account for possible shared rankings and unranked candidates.

All of the methods in this module reliably select a Condorcet winner when there
is one in the input.

These evaluators are considered more advanced in terms of satisfied criteria
than transferable vote systems but still cannot defy some impossibility
theorems such as Arrow's or Gibbard's.

These evaluators only take few parameters; therefore, a dictionary of their
instances with different setups is provided in the ``EVALUATORS`` module
variable.
'''

import itertools
import collections
from typing import List, Tuple, Dict, Union, Callable, Collection
from numbers import Number

import votelib.evaluate.core
import votelib.component.pairwin_scorer
from votelib.candidate import Candidate
from votelib.persist import simple_serialization


def pairwise_wins(votes: Dict[Tuple[Candidate, Candidate], int],
                  include_ties: bool = False,
                  ) -> List[Tuple[Candidate, Candidate]]:
    """Select pairs of candidates where the first is preferred to the second.

    :param votes: Condorcet votes (counts of candidate pairs as they appear
        in the voter rankings); use
        :class:`votelib.convert.RankedToCondorcetVotes`
        to produce them from ranked votes.
    :param include_ties: Whether to include pairs of candidates that are tied.
        Such a pair will be included in both directions.
    :returns: Ordered pairs from the input that are generally preferred to the
        opposite ranking (i.e. listed in this order by more voters).
    """
    wins = []
    for pair, count in votes.items():
        upper_cand, lower_cand = pair
        anti_count = votes.get((lower_cand, upper_cand), 0)
        if anti_count < count or include_ties and anti_count == count:
            wins.append(pair)
    return wins


def beat_counts(votes: Dict[Tuple[Candidate, Candidate], int]
                ) -> Dict[Candidate, int]:
    """Count the number of candidates a given candidate beats pairwise.

    :param votes: Condorcet votes (counts of candidate pairs as they appear
        in the voter rankings); use
        :class:`votelib.convert.RankedToCondorcetVotes`
        to produce them from ranked votes.
    """
    n_beats = collections.defaultdict(int)
    for winner, loser in pairwise_wins(votes):
        n_beats[winner] += 1
    return dict(n_beats)


def _smith_schwartz_set(votes: Dict[Tuple[Candidate, Candidate], int],
                        ties: bool = True,
                        ) -> List[Candidate]:
    wins = pairwise_wins(votes, include_ties=ties)
    copeland_scores = Copeland.scores(wins)
    copeland_ordering = list(sorted(
        copeland_scores,
        key=copeland_scores.get,
        reverse=True,
    ))
    cand_copes = dict(zip(copeland_ordering, range(len(copeland_ordering))))
    end_i = 1  # index of first candidate out of smith set
    # Sort wins so that wins over the most promising candidates go first.
    wins.sort(key=lambda tup: copeland_ordering.index(tup[1]))
    for winner, loser in wins:
        if cand_copes[winner] >= end_i and cand_copes[loser] < end_i:
            end_i = cand_copes[winner] + 1
            if end_i == len(copeland_ordering):
                break
    return copeland_ordering[:end_i]


class Selector:
    def evaluate(self,
                 votes: Dict[Tuple[Candidate, Candidate], int],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        raise NotImplementedError


class SeatlessSelector:
    def evaluate(self,
                 votes: Dict[Tuple[Candidate, Candidate], int],
                 ) -> List[Candidate]:
        raise NotImplementedError


@simple_serialization
class CondorcetWinner:
    """Condorcet winner selector.

    Selects a candidate that pairwise beats all other candidates, if there
    is one, or an empty list otherwise.
    """
    def evaluate(self,
                 votes: Dict[Tuple[Candidate, Candidate], int],
                 ) -> List[Candidate]:
        """Select the Condorcet winner.

        :param votes: Condorcet votes (counts of candidate pairs as they appear
            in the voter rankings); use
            :class:`votelib.convert.RankedToCondorcetVotes`
            to produce them from ranked votes.
        """
        n_required_wins = len(
            frozenset(cand for pair in votes for cand in pair)
        ) - 1
        for cand, n_beats in beat_counts(votes).items():
            if n_beats == n_required_wins:
                return [cand]
        return []


@simple_serialization
class SmithSet:
    """Smith set selector.

    The Smith set is the smallest possible non-empty set whose candidates beat
    all other candidates in pairwise preference comparisons.
    """
    def evaluate(self,
                 votes: Dict[Tuple[Candidate, Candidate], int],
                 ) -> List[Candidate]:
        """Select the Smith set.

        :param votes: Condorcet votes (counts of candidate pairs as they appear
            in the voter rankings); use
            :class:`votelib.convert.RankedToCondorcetVotes`
            to produce them from ranked votes.
        """
        return _smith_schwartz_set(votes, ties=True)


@simple_serialization
class SchwartzSet:
    """Schwartz set selector.

    The Schwartz set is the smallest possible non-empty set whose candidates
    are pairwise unbeaten by all other candidates.
    """
    def evaluate(self,
                 votes: Dict[Tuple[Candidate, Candidate], int],
                 ) -> List[Candidate]:
        """Select the Schwartz set.

        :param votes: Condorcet votes (counts of candidate pairs as they appear
            in the voter rankings); use
            :class:`votelib.convert.RankedToCondorcetVotes`
            to produce them from ranked votes.
        """
        return _smith_schwartz_set(votes, ties=False)


@simple_serialization
class Copeland:
    '''Copeland (count of pairwise wins) Condorcet selection evaluator.

    Calculates the pairwise wins, constructs the Copeland score by taking
    ``number_of_pairwise_wins - number_of_pairwise_losses`` for each candidate,
    and uses this score to rank candidates. This often produces ties, which
    can be used by second order tiebreaking - by preferring the candidates
    who have pairwise beaten the candidates with the highest total Copeland
    score.

    :param second_order: Whether to use second-order Copeland tiebreaking.
    '''
    def __init__(self, second_order: bool = True):
        self.second_order = second_order

    def evaluate(self,
                 votes: Dict[Tuple[Candidate, Candidate], int],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        '''Select candidates using the Copeland method.

        :param votes: Condorcet votes (counts of candidate pairs as they appear
            in the voter rankings); use
            :class:`votelib.convert.RankedToCondorcetVotes`
            to produce them from ranked votes.
        :param n_seats: Number of candidates to select.
        '''
        wins = pairwise_wins(votes)
        scores = self.scores(wins)
        best = votelib.evaluate.core.get_n_best(scores, n_seats)
        if self.second_order and votelib.evaluate.core.Tie.any(best):
            return self.break_second_order(best, scores, wins)
        else:
            return best

    @staticmethod
    def scores(wins: List[Tuple[Candidate, Candidate]]
               ) -> Dict[Candidate, int]:
        scores = collections.defaultdict(int)
        for winner, loser in wins:
            scores[winner] += 1
            scores[loser] -= 1
        return dict(scores)

    def break_second_order(self,
                           best: List[Union[
                               Candidate,
                               votelib.evaluate.core.Tie
                           ]],
                           scores: Dict[Candidate, int],
                           wins: List[Tuple[Candidate, Candidate]],
                           ) -> List[Candidate]:
        untied = []
        tied = set()
        for selected in best:
            if isinstance(selected, votelib.evaluate.core.Tie):
                tied.update(selected)
            else:
                untied.append(selected)
        second_order_scores = collections.defaultdict(int)
        for winner, loser in wins:
            if winner in tied:
                second_order_scores[winner] += scores[loser]
        return untied + votelib.evaluate.core.get_n_best(
            second_order_scores, len(best) - len(untied)
        )


@simple_serialization
class Schulze:
    '''Schulze (beatpath) Condorcet selection evaluator.

    Also called Schwartz Sequential dropping or path voting. Finds paths
    between pairs of candidates in which each candidate pairwise beats the next
    and then selects the candidates with strongest such paths.
    '''
    def evaluate(self,
                 votes: Dict[Tuple[Candidate, Candidate], int],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        '''Select candidates using the Schulze method.

        :param votes: Condorcet votes (counts of candidate pairs as they appear
            in the voter rankings); use
            :class:`votelib.convert.RankedToCondorcetVotes`
            to produce them from ranked votes.
        :param n_seats: Number of candidates to select.
        '''
        paths = self.widest_paths(votes)
        scores = collections.defaultdict(int)
        for winner, loser in pairwise_wins(paths):
            scores[winner] += 1
            scores[loser]    # to make zero appear if not present
        return votelib.evaluate.core.get_n_best(scores, n_seats)

    @staticmethod
    def widest_paths(counts: Dict[Tuple[Candidate, Candidate], Number]
                     ) -> Dict[Tuple[Candidate, Candidate], Number]:
        paths = {}
        all_candidates = set()
        for pair, count in counts.items():
            all_candidates.update(pair)
            if counts.get(tuple(reversed(pair)), 0) < count:
                paths[pair] = count
        all_candidates = list(all_candidates)
        for cand1 in all_candidates:
            for cand2 in all_candidates:
                if cand1 != cand2:
                    for cand_aug in all_candidates:
                        if cand_aug not in (cand1, cand2):
                            paths[cand2, cand_aug] = max(
                                paths.get((cand2, cand_aug), 0),
                                min(
                                    paths.get((cand2, cand1), 0),
                                    paths.get((cand1, cand_aug), 0),
                                )
                            )
        return paths


@simple_serialization
class KemenyYoung:
    '''Kemeny-Young Condorcet selection evaluator.

    Kemeny-Young orders the candidates based on their pairwise comparison by
    constructing an objective function that measures the quality of any
    ordering, evaluating it for all permutations of the candidate set, and
    selecting the ordering with the maximum score.

    The objective function is given as the number of satisfied pairwise
    orderings of candidates as given by the voters.

    WARNING: Due to the enumeration of all candidate set permutations, this
    method is highly computationally expensive (``O(n!)`` in the number of
    candidates) and infeasible on common machines for more than a handful of
    candidates.
    '''
    def evaluate(self,
                 votes: Dict[Tuple[Candidate, Candidate], int],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        '''Select candidates by the Kemeny-Young Condorcet method.

        :param votes: Condorcet votes (counts of candidate pairs as they appear
            in the voter rankings); use
            :class:`votelib.convert.RankedToCondorcetVotes`
            to produce them from ranked votes.
        :param n_seats: Number of candidates to select.
        '''
        all_candidates = frozenset(cand for pair in votes for cand in pair)
        best_variants = []
        best_score = 0
        for variant in itertools.permutations(all_candidates):
            score = self.score(variant, votes)
            if score >= best_score:
                variant = list(variant)
                if score > best_score:
                    best_variants = [variant]
                    best_score = score
                else:
                    best_variants.append(variant)
        if len(best_variants) == 1:
            return best_variants[0][:n_seats]
        else:
            return votelib.evaluate.core.Tie.tie_rankings(
                best_variants
            )[:n_seats]

    @staticmethod
    def score(variant: Collection[Candidate],
              votes: Dict[Tuple[Candidate, Candidate], int],
              ) -> int:
        '''Compute the Kemeny-Young ordering score (objective function value).

        :param variant: The ordering of candidates to evaluate.
        :param votes: Condorcet votes (counts of candidate pairs as they appear
            in the voter rankings); use
            :class:`votelib.convert.RankedToCondorcetVotes`
            to produce them from ranked votes.
        '''
        return sum(
            votes.get((cand_upper, cand_lower), 0)
            for i, cand_upper in enumerate(variant)
                for cand_lower in variant[i+1:]    # noqa: E131
        )


@simple_serialization
class MinimaxCondorcet:
    '''Minimax Condorcet selection evaluator.

    Also known as successive reversal or Simpson-Kramer method.
    Selects as the winner the candidate whose greatest pairwise defeat is
    smaller than the greatest pairwise defeat of any other candidate.

    The magnitude of the pairwise defeat can be measured in different ways
    according to the pairwise win scorer provided.

    :param pairwin_scoring: A pairwise win scorer callable. Most common
        variants are found in the :mod:`votelib.component.pairwin_scorer`
        module and can be referred to by their names.
    '''
    def __init__(self,
                 pairwin_scoring: Union[str, Callable] = 'winning_votes',
                 ):
        self.pairwin_scoring = votelib.component.pairwin_scorer.construct(
            pairwin_scoring
        )

    def evaluate(self,
                 votes: Dict[Tuple[Candidate, Candidate], int],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        '''Select candidates by the Minimax Condorcet method.

        :param votes: Condorcet votes (counts of candidate pairs as they appear
            in the voter rankings); use
            :class:`votelib.convert.RankedToCondorcetVotes`
            to produce them from ranked votes.
        :param n_seats: Number of candidates to select.
        '''
        max_counterscore = {}
        for pair, score in self.pairwin_scoring(votes).items():
            max_counterscore[pair[1]] = max(
                max_counterscore.get(pair[1], -float('inf')),
                score
            )
        return votelib.evaluate.core.get_n_best(
            {cand: -score for cand, score in max_counterscore.items()},
            n_seats
        )


@simple_serialization
class RankedPairs:
    '''Tideman's ranked pairs Condorcet selection evaluator.

    Ranks pairwise wins by their magnitude and sequentially locks pairs of
    who beats whom in descending order into a ranking, discarding pairs that
    would contradict previously established rankings (i.e. create a cycle).

    The magnitude of the pairwise win can be measured in different ways
    according to the pairwise win scorer provided.

    :param pairwin_scoring: A pairwise win scorer callable. Most common
        variants are found in the :mod:`votelib.component.pairwin_scorer`
        module and can be referred to by their names.
    '''
    def __init__(self,
                 pairwin_scoring: Union[str, Callable] = 'winning_votes',
                 ):
        self.pairwin_scoring = votelib.component.pairwin_scorer.construct(
            pairwin_scoring
        )

    def evaluate(self,
                 votes: Dict[Tuple[Candidate, Candidate], int],
                 n_seats: int = 1,
                 ) -> List[Candidate]:
        '''Select candidates by the ranked pairs method.

        :param votes: Condorcet votes (counts of candidate pairs as they appear
            in the voter rankings); use
            :class:`votelib.convert.RankedToCondorcetVotes`
            to produce them from ranked votes.
        :param n_seats: Number of candidates to select.
        '''
        scored = self.pairwin_scoring(votes)
        pairwise_winners = list(votes.keys())
        pairwise_winners.sort(key=votes.get, reverse=True)
        pairwise_winners.sort(key=scored.get, reverse=True)
        locked_pairs = self._lock_pairs(pairwise_winners)
        ranking = self._build_ranking(locked_pairs)
        return ranking[:n_seats]

    @classmethod
    def _lock_pairs(cls,
                    pairs: List[Tuple[Candidate, Candidate]]
                    ) -> List[Candidate]:
        locked_pairs = []
        for pair in pairs:
            if not cls._is_path(locked_pairs, pair[1], pair[0]):
                locked_pairs.append(pair)
        return locked_pairs

    @staticmethod
    def _is_path(pairs: List[Tuple[Candidate, Candidate]],
                 source: Candidate,
                 sink: Candidate,
                 ) -> bool:
        visited = set([source])
        while True:
            last_len = len(visited)
            for from_cand, to_cand in pairs:
                if from_cand in visited and to_cand not in visited:
                    visited.add(to_cand)
                    if to_cand == sink:
                        return True
            if len(visited) == last_len:
                return False

    @staticmethod
    def _build_ranking(locked_pairs: List[Tuple[Candidate, Candidate]]
                       ) -> List[Candidate]:
        edges = locked_pairs[:]
        ranking = []
        while edges:
            winners = set()
            losers = set()
            for winner, loser in edges:
                winners.add(winner)
                losers.add(loser)
            winners.difference_update(losers)
            if len(winners) != 1:
                raise votelib.evaluate.core.VotingSystemError
            winner = winners.pop()
            ranking.append(winner)
            edges = [edge for edge in edges if edge[0] != winner]
        return ranking + [next(
            node for pair in locked_pairs for node in pair
            if node not in ranking
        )]


EVALUATORS = {
    'rankedpairs_winvotes': RankedPairs(),
    'rankedpairs_margins': RankedPairs('margins'),
    'rankedpairs_pwo': RankedPairs('pairwise_opposition'),
    'copeland_2o': Copeland(),
    'copeland_raw': Copeland(second_order=False),
    'schulze': Schulze(),
    'kemeny_young': KemenyYoung(),
    'minimax_winvotes': MinimaxCondorcet(),
    'minimax_margins': MinimaxCondorcet('margins'),
    'minimax_pwo': MinimaxCondorcet('pairwise_opposition'),
}
