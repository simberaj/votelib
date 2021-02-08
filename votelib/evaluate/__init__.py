'''Evaluate the results of the elections.

There are two basic election types - selections and distributions.
In selections, each candidate (usually a physical person) is either
elected or not elected.
In distributions, some candidates (usually parties) are allocated
a positive number of seats (seats are distributied among the parties),
while other parties get none and do not appear in the result.

*Selection evaluators* return a list of candidates. If some of them are tied,
a :class:`core.Tie` object will appear in the list. The tie object will contain
all candidates tied for the seats and will be repeated the
number of times equal to the number of tied seats.

*Distribution evaluators* return a dictionary mapping candidates to the number
of seats (or other tokens they should be allocated). In case of a tie, the
:class:`core.Tie` object will appear as one of the keys, with the number of
tied seats as its associated value.

There are some other election concepts, for example *asset voting*, where the
candidates bargain with each other with the votes they have received;
these understandably cannot be implemented within the current scope of
Votelib. [#rvasset]_

None of the evaluators validate vote correctness; use the tools in the
:mod:`vote` module for that, potentially wrapped in
:class:`convert.InvalidVoteEliminator`.

.. [#rvasset] "Asset voting", Range voting.org.
    https://rangevoting.org/Asset.html
'''

from votelib.evaluate.core import *    # noqa
