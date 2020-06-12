Vote objects and vote validation API
---------------------------------------------------------

.. automodule:: votelib.vote

Vote validators
~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: votelib.vote.SimpleVoteValidator
   :members:

.. autoclass:: votelib.vote.ApprovalVoteValidator
   :members:

.. autoclass:: votelib.vote.RankedVoteValidator
   :members:

.. autoclass:: votelib.vote.EnumScoreVoteValidator
   :members:

.. autoclass:: votelib.vote.RangeVoteValidator
   :members:
   
An abstract class defining the vote validator interface is also present.

.. autoclass:: votelib.vote.VoteValidator
   :members:

Vote validation errors
~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: votelib.vote.VoteError
   :members:

.. autoclass:: votelib.vote.VoteTypeError
   :members:

.. autoclass:: votelib.vote.VoteMagnitudeError
   :members:

.. autoclass:: votelib.vote.VoteValueError
   :members:
