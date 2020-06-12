Converters API
---------------

.. automodule:: votelib.convert


Vote aggregators
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: votelib.convert.ApprovalToSimpleVotes
    :members:

.. autoclass:: votelib.convert.ScoreToSimpleVotes
    :members:

.. autoclass:: votelib.convert.RankedToPositionalVotes
    :members:

.. autoclass:: votelib.convert.RankedToCondorcetVotes
    :members:

.. autoclass:: votelib.convert.ScoreToRankedVotes
    :members:


Vote inverters to negative votes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: votelib.convert.InvertedSimpleVotes
    :members:


Individual candidate/party conversion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: votelib.convert.IndividualToPartyVotes
    :members:

.. autoclass:: votelib.convert.IndividualToPartyResult
    :members:


Result conversion and merging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: votelib.convert.SelectionToDistribution
    :members:

.. autoclass:: votelib.convert.MergedSelections
    :members:

.. autoclass:: votelib.convert.MergedDistributions
    :members:


Constituency-based vote handling and aggregation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: votelib.convert.VoteTotals
    :members:

.. autoclass:: votelib.convert.ConstituencyTotals
    :members:

.. autoclass:: votelib.convert.PartyTotals
    :members:

.. autoclass:: votelib.convert.ByConstituency
    :members:


Vote corrections and subsetting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: votelib.convert.RoundedVotes
    :members:

.. autoclass:: votelib.convert.SubsettedVotes
    :members:

.. autoclass:: votelib.convert.InvalidVoteEliminator
    :members:
