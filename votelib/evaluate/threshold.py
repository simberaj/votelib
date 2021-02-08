'''Electoral threshold evaluators and other seatless selectors.

These evaluators mainly serve as auxiliary components (usually preconditions)
in proportional or similar voting systems. They are seatless selectors, which
means they return a list of elected candidates without being given the number
of them to select; that number is determined by other means.
'''

from fractions import Fraction
from typing import Any, List, Dict, Optional
from numbers import Number


import votelib.util
import votelib.evaluate.core
from votelib.candidate import Candidate, ElectionParty
from votelib.persist import simple_serialization


@simple_serialization
class AbsoluteThreshold:
    '''Absolute threshold seatless selector.

    Selects all candidates with more (or equally many) votes than the specified
    absolute number. Does not accept a number of seats as an argument to the
    ``evaluate()`` method.

    :param threshold: The absolute threshold as a number of votes.
    :param accept_equal: Whether to elect candidates that only just reach the
        threshold.
    '''
    def __init__(self,
                 threshold: Number,
                 accept_equal: bool = True,
                 ):
        self.threshold = threshold
        self.accept_equal = accept_equal

    def evaluate(self,
                 votes: Dict[Candidate, Number],
                 ) -> List[Candidate]:
        '''Select candidates by a given absolute threshold of votes.

        :param votes: Simple votes.
        '''
        return [
            cand for cand, n_votes in votelib.util.sorted_votes(votes)
            if (
                n_votes > self.threshold
                or self.accept_equal and n_votes == self.threshold
            )
        ]


@simple_serialization
class RelativeThreshold:
    '''Relative threshold seatless selector.

    Selects all candidates with more (or equally many) votes than the specified
    fraction of total votes. Does not accept a number of seats as an argument
    to the ``evaluate()`` method.

    This is a common component in proportional systems that excludes very small
    parties to increase stability of the resulting elected body.

    :param threshold: The relative threshold as a fraction of total votes.
    :param accept_equal: Whether to elect candidates that only just reach the
        threshold.
    '''
    def __init__(self,
                 threshold: Number,
                 accept_equal: bool = True,
                 ):
        self.threshold = threshold
        self.accept_equal = accept_equal

    def evaluate(self,
                 votes: Dict[Candidate, Number],
                 ) -> List[Candidate]:
        '''Select candidates by a given threshold of fraction of total votes.

        :param votes: Simple votes.
        '''
        total = sum(votes.values())
        return [
            cand for cand, n_votes in votelib.util.sorted_votes(votes)
            if (
                Fraction(n_votes, total) > self.threshold
                or self.accept_equal and n_votes == self.threshold
            )
        ]


@simple_serialization
class CoalitionMemberBracketer:
    '''Dispatch to different seatless selectors for coalitions.

    In many proportional systems the threshold to exclude smaller parties is
    raised for coalitions depending on the number of their members, to prevent
    the fragmentation of the resulting elected body.

    :param evaluators: A dictionary mapping the number of coalition members
        to the corresponding seatless selector such as
        :class:`RelativeThreshold`. Atomic parties (non-coalitions) will be
        dispatched to 1.
    :param default: A default seatless selector for coalitions that do not have
        the corresponding count in evaluators. This is useful for clauses like
        "four and more party coalitions".
    '''
    def __init__(self,
                 evaluators: Dict[int, votelib.evaluate.core.SeatlessSelector],
                 default: votelib.evaluate.core.SeatlessSelector,
                 ):
        self.evaluators = evaluators
        self.default = default

    def evaluate(self,
                 votes: Dict[ElectionParty, Number],
                 ) -> List[ElectionParty]:
        '''Select parties by dispatching to partial selectors.

        :param votes: Simple votes for parties. The keys in the dictionary must
            provide an ``is_coalition`` property and if its value is truthy, a
            ``get_n_coalition_members()`` method that returns the number of
            coalition members as an integer.
        '''
        n_member_dict = {
            cand: cand.get_n_coalition_members() if cand.is_coalition else 1
            for cand, _ in votelib.util.sorted_votes(votes)
        }
        n_member_variants = frozenset(n_member_dict.values())
        passed = {
            n_members: self.evaluators.get(
                n_members, self.default
            ).evaluate(votes)
            for n_members in n_member_variants
        }
        return [
            cand for cand, n_members in n_member_dict.items()
            if cand in passed[n_members]
        ]


@simple_serialization
class PropertyBracketer:
    '''Dispatch to different seatless selectors for some types of parties.

    In many proportional systems the threshold to exclude smaller parties is
    lowered or nonexistent for parties with a special designation, such as
    parties of regional minorities. This wrapper class allows to provide
    special seatless selectors for such special cases.

    :param property: The property (attribute) of the candidate to get as the
        key to distinguish which evaluator to use. ``getattr()`` is used on the
        candidate objects.
    :param evaluators: A dictionary mapping the values of the property
        to the corresponding seatless selector such as
        :class:`RelativeThreshold`.
    :param default: A default seatless selector for candidates that do not
        define the specified property or whose property value is outside the
        set of keys of the evaluators dictionary.
    '''
    def __init__(self,
                 property: str,
                 evaluators: Dict[
                     Any, Optional[votelib.evaluate.core.SeatlessSelector]
                 ],
                 default: Optional[
                     votelib.evaluate.core.SeatlessSelector
                 ] = None,
                 ):
        self.property = property
        self.evaluators = evaluators
        self.default = default

    def evaluate(self,
                 votes: Dict[Candidate, Number],
                 ) -> List[Candidate]:
        '''Select candidates by dispatching to partial selectors.

        :param votes: Simple votes. The keys in the dictionary should provide
            the property name specified at the setup of this elector; if they
            do not, the default evaluator is used for them.
        '''
        variants = {}
        results = []
        for cand, _ in votelib.util.sorted_votes(votes):
            cand_var = getattr(cand, self.property, NotImplemented)
            if cand_var not in variants:
                var_eval = self.evaluators.get(
                    cand_var, self.default
                )
                if var_eval:
                    variants[cand_var] = var_eval.evaluate(votes)
                else:
                    variants[cand_var] = list(votes.keys())
            if cand in variants[cand_var]:
                results.append(cand)
        return results


@simple_serialization
class AlternativeThresholds:
    '''An OR function for threshold evaluators.

    Wraps multiple seatless selectors and selects a candidate that is selected
    by any single one of them.

    :param partials: The selectors to wrap.
    '''
    # an OR function for eliminators, primarily
    def __init__(self,
                 partials: List[votelib.evaluate.core.SeatlessSelector],
                 ):
        for partial in partials:
            if votelib.evaluate.core.accepts_seats(partial):
                raise ValueError(f'seat-based evaluator {partial} in {self}')
        self.partials = partials

    def evaluate(self,
                 votes: Dict[Candidate, Number],
                 prev_gains: Dict[Candidate, int] = {},
                 ) -> List[Candidate]:
        '''Select candidates by dispatching to partial selectors and ORing.

        :param votes: Simple votes.
        :returns: A list of candidates that were selected by any single one
            of the internal partial selectors. They are ordered by mean rank
            in those partial selections.
        '''
        partial_results = []
        for partial in self.partials:
            if votelib.evaluate.core.accepts_prev_gains(partial):
                partial_result = partial.evaluate(votes, prev_gains=prev_gains)
            else:
                partial_result = partial.evaluate(votes)
            partial_results.append(partial_result)
        all_results = frozenset(
            cand for res in partial_results for cand in res
        )

        def mean_rank(cand):
            return Fraction(
                sum(
                    res.index(cand) if cand in res else len(res)
                    for res in partial_results
                ),
                len(partial_results)
            )

        return list(sorted(all_results, key=mean_rank))


@simple_serialization
class PreviousGainThreshold:
    '''A threshold on gained seats in previous election rounds.

    In some multi-round systems (especially mixed-member proportional ones),
    an alternative to clearing a national-level vote fraction threshold is to
    gain a specific minimum number of seats in the first round (e.g. in Germany
    a party may qualify for list seats if they gain three or more district
    seats).

    This evaluator passes the ``prev_gains`` argument of ordinary distribution
    evaluators to the ``votes`` argument of a given seatless selector, allowing
    one to specify a threshold based on previously gained seats.

    :param selector: The selector to evaluate the threshold on previous gains;
        :class:`AbsoluteThreshold` would be the most typical choice.
    '''
    def __init__(self, selector: votelib.evaluate.core.SeatlessSelector):
        self.selector = selector

    def evaluate(self,
                 votes: Dict[Any, int],
                 prev_gains: Dict[Candidate, int],
                 ) -> List[Candidate]:
        '''Select candidates by previous gain according to the inner selector.

        :param votes: Will be disregarded.
        :param prev_gains: Seats gained by the candidate/party in previous
            election rounds. Will be passed as votes to the inner selector.
        '''
        return self.selector.evaluate(prev_gains)
