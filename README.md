# Votelib: Evaluation of voting systems in Python

[![Documentation Status](https://readthedocs.org/projects/votelib/badge/?version=latest)](https://votelib.readthedocs.io/en/latest/?badge=latest)
[![Test coverage](https://codecov.io/gh/simberaj/votelib/branch/master/graph/badge.svg?token=0YC5FSTL9Z)](https://codecov.io/gh/simberaj/votelib)

Votelib is a package to evaluate results of elections under various systems.
It aims to provide reliable implementations of many voting systems so that
they may be evaluated as they are used in real-world conditions and compared.
The primary focus is on political decision making, but the library is not
limited to evaluating political decisions only.

Votelib does not aim to be an end-to-end tool for managing elections; it
does not (and will not) provide user interfaces or concern itself with other
parts of the election process than determining the result from the votes cast.
It also does not directly address theoretical analysis of different voting
systems (in terms of automatic proofs of satisfied criteria) - it is rather
meant for practical use and experiments.

Votelib aims to enrich the public debate around voting systems by providing an
impartial and solid basis for their comparison; the project does not (and
will not) lend itself to the agenda of promoting any particular system (but the
license allows you to *use* it to do so, of course).

Votelib is implemented in pure Python without any third-party dependencies
and is licensed permissively under an MIT license.

## Installation
Votelib supports Python 3.7+. You can get Votelib from PyPI by using

    pip install votelib

For restricted settings, you can also download the contents of its
[repository](https://github.com/simberaj/votelib)
and copy the `votelib` folder into a desired location. No actual installation
is necessary because Votelib does not have any dependencies beyond Python.

## Contents
At the heart of Votelib lie *evaluators*, objects that determine election
results from the votes cast, defined in the submodules of the `evaluate`
subpackage. The supported evaluators cover most of the systems
used around the world, such as the following:

-   *Selection evaluators*: select one or more elected candidates from a set.
    Each candidate can be elected at most once. This encompasses both
    single-winner elections (with number of seats set to 1) and multi-winner
    elections.
    -   Plurality (first-past-the-post)
    -   Transferable vote methods: PR-STV, instant runoff voting and other
        variants with different transfer methods
    -   Condorcet methods: Schulze, Copeland, Minimax, Kemeny-Young,
        Ranked pairs, Smith and Schwartz sets
    -   Majority Judgment
    -   Borda count and its variants
    -   Score voting (ordinary and STAR)
    -   Approval methods (AV, PAV, SPAV, SAV)
    -   Preference addition (Bucklin, Oklahoma)
    -   Sortition (random selection)
    -   Open list (preferential votes) evaluation
-   *Distribution evaluators*: allocate seats to candidates (each candidate -
    usually a political party - might get more than one seat). These systems
    are often called *proportional*, but their result might be very far from
    that.
    -   Largest remainder (all quota variants - Hare, Droop, Hagenbach-Bischoff,
        Imperiali and their variants)
    -   Highest averages (all divisor variants - D'Hondt, Sainte-Laguë/Webster,
        Imperiali, Huntington-Hill, Macau)
    -   Biproportional apportionment, allowing to satisfy proportionality in
        both party and district seats

The following classes of votes are supported:
-   Simple (single candidate) voting
-   Approval voting
-   Ranked voting
-   Score voting (also called range or cardinal voting)
These vote classes can be converted to each other by objects in the `convert`
module, where you can also find utilities to facilitate district-wise
elections.

The `candidate` and `vote` allow for validity checking of candidate nominations
and cast ballots respectively.

The whole library is designed for numerical stability and tries to avoid
inexact arithmetics; if you detect any such behavior, please report it.

### Usage
Votelib is meant as a library to be imported from other Python code.
The objects in the various submodules of Votelib can be easily combined and
chained to model the election system of choice. Examples can be found in the
documentation. A simple example is evaluating the [Irish presidential election
of 1990](https://en.wikipedia.org/wiki/1990_Irish_presidential_election), which
uses a single transferable vote method:

    votes = {
        ('Mary Robinson',): 612265,
        ('Brian Lenihan',): 694484,
        ('Austin Currie', 'Brian Lenihan'): 36789,
        ('Austin Currie', 'Mary Robinson'): 205565,
        ('Austin Currie',): 25548,
    }
    evaluator = votelib.evaluate.sequential.TransferableVoteSelector(
        quota_function='droop',
        transferer='Hare'
    )
    assert evaluator.evaluate(votes) == ['Mary Robinson']

The library covers many more systems like this! Find more in the
[ReadTheDocs documentation](https://votelib.readthedocs.io/en/latest/).

## Contributors
Feedback, additions, suggestions, issues and pull requests are welcome and much
appreciated on [GitHub](https://github.com/simberaj/votelib). See the issues
list there for some suggestions.

How to add features:

1.  Fork it (https://github.com/simberaj/pysynth/fork)
2.  Create your feature branch (`git checkout -b feature/feature-name`)
3.  Commit your changes (`git commit -am "feature-name added"`)
4.  Push to the branch (`git push origin feature/feature-name`)
5.  Create a new pull request

Development requires `pytest` for testing and `sphinx` to generate
documentation. Tests can be run using simple

    pytest tests

### Intended development directions
(See [issues](https://github.com/simberaj/votelib/issues) for more.)

-   More extensive example and test coverage, documentation with literature
    references
-   Support more systems (such as more STV variants, Quota Borda, or more
    Condorcet methods)

## License and author info
Votelib is developed by Jan Šimbera <simbera.jan@gmail.com>.

Votelib is available under the MIT license. See `LICENSE.txt` for more details.
