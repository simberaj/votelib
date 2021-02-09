'''Candidate specifications and nomination validators.

Contains definitions of candidate types and interfaces (:class:`Candidate`,
:class:`ElectionParty`, :class:`Coalition`), constituencies
(:class:`Constituency`), special vote variants (:class:`NoneOfTheAbove`,
:class:`ReopenNominations`) and candidate/nomination validators
(:class:`BasicNominator`, :class:`PersonNominator`, :class:`PartyNominator`).

In the current version of Votelib, special candidate objects are not
needed (any hashable objects such as strings can be used for most
functionality implemented so far and will continue to be supported by it
in the future). However, some classes specify interface that are required by
a handful of system objects so if you want to use those system objects,
using the subclasses is necessary.

For a particular example of this, the
:class:`votelib.evaluate.threshold.PropertyBracketer` chooses different rules
based on a value of an arbitrary property of the candidate. You can use any
object that has the specified property defined; the classes defined here can be
assigned arbitrary additional properties, so they, too, can be used.
'''

from __future__ import annotations

import abc
import collections
from typing import Any, List, Optional, Union

from votelib.persist import simple_serialization


class CandidateError(Exception):
    '''A candidate is invalid in the given context.

    E.g. parties in place of individual candidates, or candidates ineligible
    to stand for given seats.

    :param candidate: Candidate that was found to be invalid.
    :param expected: Definition of a candidate that was expected.
    '''
    def __init__(self, candidate: Any, expected: Any = None):
        self.candidate = candidate
        self.expected = expected
        message = f'invalid candidate: {candidate}'
        if expected:
            message += f', must be {expected}'
        super().__init__(message)


class Candidate(metaclass=abc.ABCMeta):
    '''An abstract class for election candidates.

    The subclass check is overridden so that any hashable object that is not
    a set or tuple is accepted. Subclasses will not inherit this override.

    In the current version of Votelib, special candidate objects are not
    needed (any hashable objects such as strings can be used for most
    functionality implemented so far and will continue to be supported by it
    in the future) so this is essentially just a type marker. However,
    some subclasses specify methods that are required by some system objects
    so if you want to use those system objects, using the subclasses is
    necessary.
    '''

    withdrawn: bool = False
    '''Whether the candidate withdrew from the election (and is thus ineligible
    to get elected).'''

    @classmethod
    def __subclasshook__(cls, subcl):
        if cls is Candidate:
            return (
                hasattr(subcl, '__hash__')
                and subcl.__hash__ is not None
                and not issubclass(subcl, collections.abc.Set)
                and not issubclass(subcl, tuple)
            )
        else:
            return super().__subclasshook__(subcl)


class IndividualElectionOption(Candidate):
    '''An abstract class for individuals standing for an election.'''

    candidacy_for: Optional[ElectionParty] = NotImplemented
    '''The party for which this choice is candidating for the election.

    This is important for counting party-based election results where the votes
    are cast and counted for candidates.

    If the candidate is endorsed by multiple parties, use a :class:`Coalition`
    object.
    '''

    membership: Optional[PoliticalParty] = NotImplemented
    '''The party the candidate is member of.

    This is important for counting party-based election results where the votes
    are cast and counted for candidates.
    '''


@simple_serialization
class Person(IndividualElectionOption):
    '''A physical person standing for the election.

    :param name: Name of the person, in any customary text format.
    :param number: Candidacy number assigned to the person for the purpose
        of the election; usually drawn by lot.
    :param membership: A political party the person is member of, if any.
    :param candidacy_for: A political party for which the person is standing
        in the election. If there is no such party, the person is considered
        an independent candidate.
    :param withdrawn: Whether the candidate withdrew from the election
        (and is thus ineligible to get elected).
    '''
    def __init__(self,
                 name: str,
                 number: Optional[int] = None,
                 membership: Optional[PoliticalParty] = None,
                 candidacy_for: Optional[ElectionParty] = None,
                 properties: List[str] = [],
                 withdrawn: bool = False,
                 ):
        self.name = name
        self.number = number
        self.membership = membership
        self.candidacy_for = candidacy_for
        self.properties = properties
        self.withdrawn = withdrawn

    def __repr__(self) -> str:
        return (
            f'<Person({self.name}'
            + (f',{self.number}' if self.number is not None else '')
            + ')>'
        )


class ElectionParty(Candidate):
    '''A subject that is regarded as a political party for the election.'''

    is_coalition = NotImplemented
    '''Whether the party is a coalition.

    This makes a difference for some systems; the most common case is a
    heightened vote threshold in proportional elections.
    '''


@simple_serialization
class PoliticalParty(ElectionParty):
    '''A political party or movement that is eligible to stand in elections.

    :param name: Name of the party, in any customary text format.
    :param number: Candidacy number assigned to the party for the purpose
        of the election; usually drawn by lot.
    :param affiliation: Other (e.g. national or supranational) parties this
        party is affiliated with, if any.
    :param lead: A person that leads the party into the elections.
    '''
    is_coalition = False

    def __init__(self,
                 name: str,
                 number: Optional[int] = None,
                 affiliations: Optional[List[PoliticalParty]] = None,
                 lead: Optional[Person] = None,
                 properties: List[str] = [],
                 withdrawn: bool = False,
                 ):
        self.name = name
        self.number = number
        self.affiliations = affiliations
        self.lead = lead
        self.properties = properties
        self.withdrawn = withdrawn

    def __repr__(self) -> str:
        return (
            f'<PoliticalParty({self.name}'
            + (f',{self.number}' if self.number is not None else '')
            + ')>'
        )


@simple_serialization
class Coalition(ElectionParty):
    '''A coalition of two or more election-eligible parties.

    :param parties: Parties involved in the coalition.
    :param name: Name of the coalition, in any customary text format. If not
        given, it is derived from the names of the member parties.
    :param number: Candidacy number assigned to the coalition for the purpose
        of the election; usually drawn by lot.
    :param affiliations: Other (e.g. national or supranational) parties this
        coalition is affiliated with, if any.
    :param lead: A person that leads the coalition into the elections.
    '''
    is_coalition = True

    def __init__(self,
                 parties: List[PoliticalParty],
                 name: Optional[str] = None,
                 number: Optional[int] = None,
                 affiliations: Optional[List[PoliticalParty]] = None,
                 lead: Optional[Person] = None,
                 withdrawn: bool = False,
                 ):
        self.parties = parties
        if name is None:
            name = '-'.join(p.name for p in parties)
        self.name = name
        self.number = number
        self.affiliations = affiliations
        self.lead = lead
        self.withdrawn = withdrawn

    def get_n_coalition_members(self) -> int:
        '''Return the number of member parties in the coalition.

        This is important in some elections which specify different thresholds
        for coalitions with a given number of members.
        '''
        return len(self.parties)

    def __repr__(self) -> str:
        return (
            'Coalition('
            + repr(self.parties)
            + (f',{self.number}' if self.number is not None else '')
            + ')'
        )


@simple_serialization
class IndividualToPartyMapper:
    '''Define mapping from individuals to parties.

    A candidate object such as a :class:`Person` might define multiple party
    relationships or define that the candidate is standing for the election as
    an independent. This object can be added as a component to some converters
    or evaluators to map individuals to parties correctly according to the
    rules of the particular election system.

    :param affiliation: How to allocate the candidate to the party:

        -   `'candidacy_for'` (default) uses the party the candidate stood
            for (was endorsed by) in the election,
        -   `'membership'` uses the party the candidate is a member of.

    :param independents: How to handle individual candidates not candidating
        for a party:

        -   `'aggregate'` (default) aggregates them under the None key
            to a total count,
        -   `'keep'` keeps them separately,
        -   `'ignore'` omits them from the result,
        -   `'error'` raises an error.
    '''

    AFFILIATION_METHODS: List[str] = [
        'candidacy_for', 'membership'
    ]
    INDEPENDENTS_METHODS: List[str] = [
        'error', 'keep', 'aggregate', 'ignore'
    ]

    IGNORE = object()

    def __init__(self,
                 affiliation: str = 'candidacy_for',
                 independents: str = 'aggregate',
                 ):
        if affiliation not in self.AFFILIATION_METHODS:
            raise ValueError(
                'invalid assignment of individuals to parties:'
                f' {affiliation}, allowed {self.AFFILIATION_METHODS}'
            )
        if independents not in self.INDEPENDENTS_METHODS:
            raise ValueError(
                'invalid handling of independents in aggregation:'
                f' {independents}, allowed {self.INDEPENDENTS_METHODS}'
            )
        self.affiliation = affiliation
        self.independents = independents

    def __call__(self,
                 cand: IndividualElectionOption
                 ) -> Union[ElectionParty, IndividualElectionOption, None]:
        party = getattr(cand, self.affiliation)
        if party is None:
            if self.independents == 'error':
                raise CandidateError(
                    f'independent {cand} not allowed in aggregation'
                )
            elif self.independents == 'keep':
                return cand
            elif self.independents == 'aggregate':
                return None
            else:
                return self.IGNORE
        else:
            return party


@simple_serialization
class BlankVoteOption(ElectionParty, IndividualElectionOption):
    '''A base class for blank (non-partisan) vote choices.

    This includes votes that are not counted to any candidate. In some rare
    cases, these votes have a special effect (such as triggering a new election
    if there is a sufficient number of them), but most of the time they can be
    safely disregarded.
    '''
    is_coalition = False
    candidacy_for = None
    membership = None

    def __init__(self,
                 name: str,
                 ):
        self.name = name


class NoneOfTheAbove(BlankVoteOption):
    '''None of the above (NOTA) vote option (often called white ballots).

    In some contexts, a sufficient number of these votes can trigger a special
    effect such as a new election.

    :param name: Actual name of the NOTA option in the given context.
    '''


class ReopenNominations(BlankVoteOption):
    '''Reopen Nominations vote option.

    In some elections, this option is present; if it prevails, it can trigger
    a new round of nominations and a new election.

    :param name: Actual name of the Reopen Nominations option in the given
        context.
    '''


class Constituency:
    '''A constituency for elections with multiple sets of candidates.

    Constituencies are used where the electorate is separated into more than
    one group. The most common variant is spatial - electoral or voting
    districts (also called wards or precincts). This object should be used
    only for cases where such spatial division is used to evaluate the result,
    not merely used to collect and count the ballots.

    Non-spatial variants include
    curias (used in 19th century Austria-Hungary for different social classes),
    ethnical divisions (Maori electorates in New Zealand)
    or qualificational divisions (University constituencies in Ireland).

    In the current version of Votelib, special constituency objects are not
    needed (any hashable objects such as strings can be used for all
    functionality implemented so far and will continue to be supported by the
    existing features in the future) so this is essentially just a type marker,
    but further development might necessitate creating some subclasses of this,
    and more specific interfaces.
    '''


class Nominator(metaclass=abc.ABCMeta):
    '''An abstract class for nominators (candidacy validators).'''
    @abc.abstractmethod
    def validate(self, candidate: Candidate) -> None:
        '''Check if the candidate satisfies criteria given by the system.

        :raises NotImplementedError:
        '''
        raise NotImplementedError


# Nominators (checkers)
@simple_serialization
class BasicNominator(Nominator):
    '''Validate that the election candidates are valid objects.

    Does not do any logical checks; only validates that the candidate instance
    passes the criteria of the :class:`Candidate` class (such as checking
    against most types of collections).

    :param allow_blank: Whether to allow blank votes (NOTA, ReopenNominations).
    '''
    def __init__(self, allow_blank: bool = True):
        self.allow_blank = allow_blank

    def validate(self, candidate: Candidate) -> None:
        '''Check whether a candidate is valid.

        :param candidate: Candidate to be checked.
        :raises CandidateError: If a candidate is invalid.
        '''
        if not isinstance(candidate, Candidate):
            raise CandidateError(f'invalid candidate {candidate}')
        if not self.allow_blank and isinstance(candidate, BlankVoteOption):
            raise CandidateError('blank vote')


@simple_serialization
class PersonNominator(Nominator):
    '''Validate that election candidates are physical persons and not parties.

    :param allow_independents: Whether persons candidating without a support
        of a political party can stand in the election.
    :param allow_blank: Whether to allow blank votes (NOTA, ReopenNominations).
    '''
    def __init__(self,
                 allow_independents: bool = True,
                 allow_blank: bool = True,
                 ):
        self.allow_independents = allow_independents
        self.allow_blank = allow_blank

    def validate(self, candidate: Candidate) -> None:
        '''Check whether a candidate is valid.

        :param candidate: Candidate to be checked.
        :raises CandidateError: If a candidate is invalid.
        '''
        if not isinstance(candidate, IndividualElectionOption):
            raise CandidateError(candidate, IndividualElectionOption)
        if isinstance(candidate, BlankVoteOption):
            if not self.allow_blank:
                raise CandidateError(candidate, 'non-blank vote')
        elif not self.allow_independents and not candidate.candidacy_for:
            raise CandidateError(
                candidate, 'a candidate with party candidacy support'
            )


@simple_serialization
class PartyNominator(Nominator):
    '''Check that election candidates are electoral parties, not persons.

    This includes political parties in the broadest sense of the term, as well
    as their coalitions formed for the purpose of the election.

    Only instances of :class:`ElectionParty` and its subclasses are accepted,
    as are classes that pass the interface check of the class, if there is one.
    Blank votes are accepted by default and can be disallowed, like coalitions.

    :param allow_coalitions: Whether to allow coalitions.
    :param allow_blank: Whether to allow blank votes (NOTA, ReopenNominations).
    '''
    def __init__(self,
                 allow_coalitions: bool = True,
                 allow_blank: bool = True
                 ):
        self.allow_coalitions = allow_coalitions
        self.allow_blank = allow_blank

    def validate(self, candidate: Candidate) -> None:
        '''Check whether a candidate is a valid election party.

        :param candidate: Candidate to be checked.
        :raises CandidateError: If a candidate is not a valid election party
            candidate.
        '''
        if isinstance(candidate, BlankVoteOption):
            if not self.allow_blank:
                raise CandidateError(candidate, 'non-blank vote')
        elif not isinstance(candidate, ElectionParty):
            raise CandidateError(candidate, ElectionParty)
        elif not self.allow_coalitions and isinstance(candidate, Coalition):
            raise CandidateError(candidate, 'non-coalition')
