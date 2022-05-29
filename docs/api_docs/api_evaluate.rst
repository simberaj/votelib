Evaluators API
-------------------------------------

.. automodule:: votelib.evaluate
   :members:
   

Plurality evaluator
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: votelib.evaluate.core.Plurality
    :members:


Proportional distribution evaluators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: votelib.evaluate.proportional
   :members:


Condorcet selection evaluators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: votelib.evaluate.condorcet
   :members:


Sequential (vote addition) selection evaluators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: votelib.evaluate.sequential
   :members:


Approval voting selection evaluators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: votelib.evaluate.approval
   :members:


Auxiliary evaluators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Open list evaluators
+++++++++++++++++++++++++++

.. automodule:: votelib.evaluate.openlist
   :members:


Electoral threshold evaluators
++++++++++++++++++++++++++++++++

.. automodule:: votelib.evaluate.threshold
   :members:


Other auxiliary evaluators
++++++++++++++++++++++++++++++++

.. automodule:: votelib.evaluate.auxiliary
   :members:


Base classes and composition objects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: votelib.evaluate.core


Common evaluation objects
+++++++++++++++++++++++++++

.. autoclass:: votelib.evaluate.core.Tie
   :members:

.. autoclass:: votelib.evaluate.core.VotingSystemError
   :members:


Abstract base classes for evaluators
++++++++++++++++++++++++++++++++++++++

.. autoclass:: votelib.evaluate.core.Evaluator
   :members:

.. autoclass:: votelib.evaluate.core.Selector
   :members:

.. autoclass:: votelib.evaluate.core.SeatlessSelector
   :members:

.. autoclass:: votelib.evaluate.core.Distributor
   :members:

.. autoclass:: votelib.evaluate.core.SeatCountCalculator
   :members:


Composite evaluators
+++++++++++++++++++++++++++++++

.. autoclass:: votelib.evaluate.core.FixedSeatCount
   :members:

.. autoclass:: votelib.evaluate.core.TieBreaking
   :members:

.. autoclass:: votelib.evaluate.core.Conditioned
   :members:

.. autoclass:: votelib.evaluate.core.PreConverted
   :members:

.. autoclass:: votelib.evaluate.core.PostConverted
   :members:

.. autoclass:: votelib.evaluate.core.ByConstituency
   :members:

.. autoclass:: votelib.evaluate.core.PreApportioned
   :members:

.. autoclass:: votelib.evaluate.core.RemovedApportionment
   :members:

.. autoclass:: votelib.evaluate.core.ByParty
   :members:

.. autoclass:: votelib.evaluate.core.MultistageDistributor
   :members:

.. autoclass:: votelib.evaluate.core.UnusedVotesDistributor
   :members:

.. autoclass:: votelib.evaluate.core.AdjustedSeatCount
   :members:

.. autoclass:: votelib.evaluate.core.PartyListEvaluator
   :members:


Seat count adjustment calculators
++++++++++++++++++++++++++++++++++

.. autoclass:: votelib.evaluate.core.AllowOverhang
   :members:

.. autoclass:: votelib.evaluate.core.LevelOverhang
   :members:

.. autoclass:: votelib.evaluate.core.LevelOverhangByConstituency
   :members:



Auxiliary evaluation functions
+++++++++++++++++++++++++++++++

.. autofunction:: votelib.evaluate.core.get_n_best

.. autofunction:: votelib.evaluate.core.accepts_seats

.. autofunction:: votelib.evaluate.core.accepts_prev_gains
