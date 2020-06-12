Candidate objects and candidacy (nomination) validation API
------------------------------------------------------------

.. automodule:: votelib.candidate


Candidate objects and interfaces
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: votelib.candidate.Candidate
   :members:

.. autoclass:: votelib.candidate.IndividualElectionOption
   :members:

.. autoclass:: votelib.candidate.Person
   :members:

.. autoclass:: votelib.candidate.ElectionParty
   :members:

.. autoclass:: votelib.candidate.PoliticalParty
   :members:

.. autoclass:: votelib.candidate.Coalition
   :members:

Blank votes and other special vote options
++++++++++++++++++++++++++++++++++++++++++++

.. autoclass:: votelib.candidate.BlankVoteOption
   :members:

.. autoclass:: votelib.candidate.NoneOfTheAbove
   :members:

.. autoclass:: votelib.candidate.ReopenNominations
   :members:


Mapping candidates to parties
++++++++++++++++++++++++++++++++++++

.. autoclass:: votelib.candidate.IndividualToPartyMapper
   :members:


Constituency objects
~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: votelib.candidate.Constituency
   :members:


Nomination (candidate) validators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: votelib.candidate.BasicNominator
   :members:

.. autoclass:: votelib.candidate.PersonNominator
   :members:

.. autoclass:: votelib.candidate.PartyNominator
   :members:

An abstract class defining the nominator interface is also present.

.. autoclass:: votelib.candidate.Nominator
   :members:


Nomination (candidate) validation errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: votelib.candidate.CandidateError
   :members:
