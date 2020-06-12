
import sys
import os
import itertools
import random
import collections
from decimal import Decimal

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import votelib.vote
import votelib.candidate

VOTE_ERRORS = (
    votelib.vote.VoteError,
    votelib.candidate.CandidateError,
)

VALID = {
    'simple': [
        votelib.candidate.NoneOfTheAbove('Nikdo'),
        votelib.candidate.Person('Barack Obama'),
        votelib.candidate.PoliticalParty('Greens'),
        votelib.candidate.Coalition([
            votelib.candidate.PoliticalParty('PS'),
            votelib.candidate.PoliticalParty('Spolu'),
        ]),
        'Angela Merkel',
    ],
    'approval': [
        frozenset('A'),
        frozenset('AB'),
        frozenset('ABCDEFGH'),
    ],
    'ranked': [
        tuple(),
        ('A',),
        tuple('AB'),
        tuple('ABCDEFGH'),
        (frozenset('AB'), 'C', 'D'),
        ('A', frozenset('BC'), 'D'),
        ('A', frozenset('BC'), 'D', frozenset('EFG')),
    ],
    'score': [
        frozenset([('M', 5), ('N', 2), ('C', 1), ('K', 0)]),
        frozenset([('M', 0), ('N', 5), ('C', 2), ('K', 2)]),
        frozenset([('M', 0), ('N', 3), ('C', 5), ('K', 4)]),
        frozenset([('M', 0), ('N', 2), ('C', 4), ('K', 5)]),
        frozenset([('EL', 6), ('L', 5), ('CL', 4), ('C', 3), ('CR', 2), ('R', 1), ('ER', 0)]),
        frozenset([('EL', 5), ('L', 6), ('CL', 5), ('C', 4), ('CR', 3), ('R', 2), ('ER', 1)]),
        frozenset([('EL', 4), ('L', 5), ('CL', 6), ('C', 5), ('CR', 4), ('R', 3), ('ER', 2)]),
        frozenset([('EL', 3), ('L', 4), ('CL', 5), ('C', 6), ('CR', 5), ('R', 4), ('ER', 3)]),
        frozenset([('EL', 2), ('L', 3), ('CL', 4), ('C', 5), ('CR', 6), ('R', 5), ('ER', 4)]),
        frozenset([('EL', 1), ('L', 2), ('CL', 3), ('C', 4), ('CR', 5), ('R', 6), ('ER', 5)]),
        frozenset([('EL', 0), ('L', 1), ('CL', 2), ('C', 3), ('CR', 4), ('R', 5), ('ER', 6)]),
    ]
}

INVALID_OVERALL = [{}]

INVALID = {}
for key in VALID.keys():
    INVALID[key] = INVALID_OVERALL.copy()
    for other_key, other_var in VALID.items():
        if other_key != key:
            INVALID[key].extend(other_var)

VALIDATORS = {
    'simple': votelib.vote.SimpleVoteValidator(),
    'approval': votelib.vote.ApprovalVoteValidator(),
    'ranked': votelib.vote.RankedVoteValidator(rank_vote_count_bounds=(None, None)),
    'score': votelib.vote.EnumScoreVoteValidator(list(range(7))),
}

@pytest.mark.parametrize(('vote_type', 'variant'), [
    (key, var) for key, var_list in VALID.items() for var in var_list
])
def test_valid_generic(vote_type, variant):
    VALIDATORS[vote_type].validate(variant)


@pytest.mark.parametrize(('vote_type', 'variant'), [
    (key, var) for key, var_list in INVALID.items() for var in var_list
])
def test_invalid_generic(vote_type, variant):
    with pytest.raises(VOTE_ERRORS):
        VALIDATORS[vote_type].validate(variant)


def check_validation(validator, vote, is_ok, error=VOTE_ERRORS):
    if is_ok:
        validator.validate(vote)
    else:
        with pytest.raises(error):
            validator.validate(vote)


APPROVAL_SIZE_RANGE = (2, 5)
SEQ = list('ABCDEFGHIJ')

@pytest.mark.parametrize('vote', [
    frozenset(random.choices(SEQ, k=i))
    for i in range(len(SEQ)) for try_i in range(5)
])
def test_approval_size(vote):
    check_validation(
        votelib.vote.ApprovalVoteValidator(APPROVAL_SIZE_RANGE),
        vote,
        APPROVAL_SIZE_RANGE[0] <= len(vote) <= APPROVAL_SIZE_RANGE[1],
        votelib.vote.VoteMagnitudeError
    )

@pytest.mark.parametrize('vote', VALID['ranked'])
def test_ranked_noshare(vote):
    validator = votelib.vote.RankedVoteValidator()
    check_validation(
        validator, vote, all(not isinstance(item, frozenset) for item in vote),
        votelib.vote.VoteMagnitudeError
    )

@pytest.mark.parametrize('vote', VALID['ranked'])
def test_ranked_nosharefirst(vote):
    validator = votelib.vote.RankedVoteValidator(rank_vote_count_bounds={1: (1, 1)})
    check_validation(
        validator, vote,
        (not vote or not isinstance(vote[0], frozenset) or len(vote[0]) == 1),
        votelib.vote.VoteMagnitudeError
    )

@pytest.mark.parametrize('vote', VALID['ranked'] + [
    tuple('ABA'),
    tuple('AA'),
    ('A', frozenset(['B', 'C']), 'C', 'D'),
    (frozenset(['A', 'C']), frozenset(['B', 'C']), 'E', 'D'),
])
def test_ranked_duplicated(vote):
    counter = collections.Counter()
    for rank in vote:
        if isinstance(rank, frozenset):
            counter.update(rank)
        else:
            counter.update([rank])
    check_validation(
        VALIDATORS['ranked'], vote,
        (not counter or max(counter.values()) == 1),
        votelib.vote.VoteError
    )


D21_VALIDATOR = votelib.vote.EnumScoreVoteValidator(
    score_levels=[-1, 1],
    allowed_scorings=(0, 6),
    sum_bounds={
        1: (1, 1),
        2: (2, 2),
        3: (1, 3),
        4: (2, 4),
        5: (3, 3),
        6: (2, 2),
    },
)

@pytest.mark.parametrize(('vote', 'is_valid'), [
    (frozenset(), True),
    (frozenset([('A', 0)]), False),
    (frozenset([('A', 1, 1)]), False),
    (frozenset([('A', 1)]), True),
    (frozenset([('A', 0), ('B', 2)]), False),
    (frozenset([('A', 2)]), False),
    (frozenset([('A', -1)]), False),
    (frozenset([('A', 1), ('B', 1)]), True),
    (frozenset([('A', 1), ('B', -1)]), False),
    (frozenset([('A', 1), ('B', 5)]), False),
    (frozenset([('A', 1), ('B', 0)]), False),
    (frozenset([('A', 1), ('B', 1), ('C', 1)]), True),
    (frozenset([('A', 1), ('B', 1), ('C', -1)]), True),
    (frozenset([('A', 1), ('B', -1), ('C', -1)]), False),
    (frozenset([('A', 1), ('B', 1), ('C', 1), ('D', 1)]), True),
    (frozenset([('A', 1), ('B', 1), ('C', 1), ('D', -1)]), True),
    (frozenset([('A', 1), ('B', 1), ('C', -1), ('D', -1)]), False),
    (frozenset([('A', 1), ('B', 1), ('C', 1), ('D', 1), ('E', -1)]), True),
    (frozenset([('A', 1), ('B', 1), ('C', -1), ('D', -1), ('E', -1)]), False),
    (frozenset([('A', 1), ('B', 1), ('C', 1), ('D', -1), ('E', -1)]), False),
    (frozenset([('A', 1), ('B', 1), ('C', 1), ('D', -1), ('E', -1), ('F', 1)]), True),
    (frozenset([('A', 1), ('B', 1), ('C', 1), ('D', 1), ('E', -1), ('F', 1)]), False),
    (frozenset([('A', 1), ('B', 1), ('C', 1), ('D', 1), ('E', 1), ('F', 1)]), False),
    (frozenset([('A', 1), ('B', 1), ('C', 1), ('D', 1), ('F', 1)]), False),
    (frozenset([('A', 1), ('B', 1), ('C', 1), ('D', 1), ('F', 1)]), False),
])
def test_score_d21_pseudo(vote, is_valid):
    check_validation(D21_VALIDATOR, vote, is_valid)


RANGE_VALIDATOR = votelib.vote.RangeVoteValidator((0, 1))

@pytest.mark.parametrize(('vote', 'is_valid'), [
    (frozenset([('A', 0)]), True),
    (frozenset([('A', Decimal('-.5'))]), False),
    (frozenset([('A', Decimal('.5'))]), True),
    (frozenset([('A', Decimal('.5979846'))]), True),
    (frozenset([('A', Decimal('.132467'))]), True),
    (frozenset([('A', Decimal('.98543'))]), True),
    (frozenset([('A', -1)]), False),
    (frozenset([('A', 0), ('B', 2)]), False),
    (frozenset([('A', 1), ('B', 1)]), True),
])
def test_range_vote(vote, is_valid):
    check_validation(RANGE_VALIDATOR, vote, is_valid, votelib.vote.VoteMagnitudeError)


RANKED_VOTES = [
    tuple(),
    ('A',),
    ('A', 'B'),
    ('A', 'A'),
    ('C', 'D'),
    ('g', 'Hah', 'y'),
    ('g', 'Hah', 'y', 'A', 'B', 'C'),
    (frozenset(['A', 'B']), 'Hah', 'y'),
    ('Hah', frozenset(['D', 'A']), 'y'),
    ('A', frozenset(['D', 'A']), 'y'),
    (frozenset(['D', 'A']), 'A', 'y'),
    (frozenset(['A', 'B', 'C']), 'Hah', 'y'),
    ('g', 'A', frozenset(['D', 'B', 'C'])),
    (frozenset(['D', 'A']), 'B', 'y', frozenset(['C', 'Hah'])),
    (frozenset(['D', 'A']), 'B', frozenset(['C', 'Hah'])),
]

@pytest.mark.parametrize('is_valid, vote', list(zip([
    False, True, True, False, True,
    True, False, True, True, False,
    False, False, False, False, True, 
], RANKED_VOTES)))
def test_ranked_validator(vote, is_valid):
    validator = votelib.vote.RankedVoteValidator(
        total_vote_count_bounds=(1, 5),
        rank_vote_count_bounds=(1, 2),
    )
    check_validation(validator, vote, is_valid, votelib.vote.VoteError)


RANKED_SUBSET = ['B', 'C', 'Hah']

@pytest.mark.parametrize('sub_vote, vote', list(zip([
    tuple(),
    tuple(),
    ('B',),
    tuple(),
    ('C',),
    ('Hah',),
    ('Hah', 'B', 'C'),
    ('B', 'Hah',),
    ('Hah',),
    tuple(),
    tuple(),
    (frozenset(['B', 'C']), 'Hah'),
    (frozenset(['B', 'C']), ),
    ('B', frozenset(['C', 'Hah']),),
    ('B', frozenset(['C', 'Hah']),),
], RANKED_VOTES)))
def test_ranked_subsetter(vote, sub_vote):
    subsetter = votelib.vote.RankedSubsetter()
    assert subsetter.subset(vote, RANKED_SUBSET) == sub_vote
