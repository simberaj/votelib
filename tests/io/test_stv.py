
import sys
import os

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.io.stv
import votelib.convert
import votelib.evaluate.auxiliary
import votelib.evaluate.sequential
import votelib.system

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

CUSTOM_SYSTEM = votelib.system.VotingSystem(
    'Example Election',
    votelib.evaluate.TieBreaking(
        votelib.evaluate.sequential.TransferableVoteSelector(
            quota_function='droop'
        ),
        votelib.evaluate.PreConverted(
            votelib.convert.RankedToPresenceCounts(),
            votelib.evaluate.auxiliary.Sortitor(1711),
        )
    )
)
CUSTOM_VOTES = {
    tuple('AECDB'): 31,
    tuple('BAE'): 30,
    tuple('CDB'): 29,
    tuple('DAE'): 10,
}
CUSTOM_N_SEATS = 2
UNORDERED_SYSTEM = votelib.system.VotingSystem(
    'STV Voting Example 2007-05-01',
    votelib.evaluate.FixedSeatCount(
        votelib.evaluate.TieBreaking(
            votelib.evaluate.sequential.TransferableVoteSelector(
                quota_function='hare',
                mandatory_quota=True,
            ),
            votelib.evaluate.PreConverted(
                votelib.convert.RankedToPresenceCounts(),
                votelib.evaluate.auxiliary.Sortitor(37863),
            )
        ),
        3
    )
)
ORDERED_SYSTEM = votelib.system.VotingSystem(
    'Test of Choice Voting',
    votelib.evaluate.FixedSeatCount(
        votelib.evaluate.TieBreaking(
            votelib.evaluate.sequential.TransferableVoteSelector(
                quota_function='droop',
                mandatory_quota=True,
            ),
            votelib.evaluate.PreConverted(
                votelib.convert.RankedToPresenceCounts(),
                votelib.evaluate.auxiliary.CandidateNumberRanker(),
            )
        ),
        3
    )
)
UNORDERED_VOTES = {
    ('George Brown', ): 1,
    ('George Brown', 'Hermione Tan', 'Harvey Black'): 3,
    ('Able Body', 'Hermione Tan'): 1,
    ('Hermione Tan', ): 2,
    ('Able Body', ): 3,
    ('Harvey Black', 'Hermione Tan'): 1,
    ('Violet Smith', 'George Brown', 'Hermione Tan', 'Harvey Black'): 2,
    ('Violet Smith', ): 1,
    ('Violet Smith', 'Mary Green'): 1,
    ('Mary Green', 'Violet Smith'): 1,
    ('Mary Green', ): 2,
    ('Mary Green', 'Violet Smith', 'George Brown'): 1,
    ('Hermione Tan', 'Violet Smith'): 1,
    ('Hermione Tan', 'Able Body', 'George Brown', 'Harvey Black'): 1,
}
EXAMPLE_CANDIDATES = [
    'George Brown', 'Mary Green', 'Hermione Tan', 'Harvey Black',
    'Violet Smith', 'Able Body'
]
ORDERED_VOTES = {
    ('George Brown', 'Hermione Tan', 'Harvey Black'): 2,
    ('Hermione Tan', 'Harvey Black'): 1,
}
BLT_RESULT = 'method=blt\nballots=blt\n3 2\n2 1 2 3 0\n1 2 3 1 0\n0\n"A"\n"B"\n"C"\n'
BLT_VOTES = {tuple('ABC'): 2, tuple('BCA'): 1}
BLT_N_SEATS = 2


def file_fixture(name: str, filename: str):
    @pytest.fixture(scope='module')
    def fixture():
        with open(os.path.join(DATA_DIR, filename)) as infile:
            return infile.read()
    fixture.__name__ = name
    return fixture


custom_standard_result = file_fixture('custom_standard_result', 'custom.stv')
custom_blt_result = file_fixture('custom_blt_result', 'custom_blt.stv')
unordered_out_result = file_fixture('unordered_out_result', 'unordered_out.stv')
unordered_result = file_fixture('unordered_result', 'unordered.stv')
ordered_result = file_fixture('ordered_result', 'ordered.stv')


def test_out_custom_system(custom_standard_result):
    assert votelib.io.stv.dumps(CUSTOM_VOTES, CUSTOM_SYSTEM, n_seats=CUSTOM_N_SEATS) == custom_standard_result


def test_out_custom_blt(custom_blt_result):
    assert votelib.io.stv.dumps(CUSTOM_VOTES, n_seats=CUSTOM_N_SEATS) == custom_blt_result


def test_in_custom_eval(custom_standard_result):
    voting_setup = votelib.io.stv.loads(custom_standard_result)
    check_candidates_equal(voting_setup.system.evaluate(voting_setup.votes), ['A', 'C'])
    check_candidates_equal(voting_setup.system.evaluator.evaluator.evaluate(voting_setup.votes, 1), ['B'])


def test_out_unordered(unordered_out_result):
    assert votelib.io.stv.dumps(
        UNORDERED_VOTES,
        UNORDERED_SYSTEM,
        candidates=EXAMPLE_CANDIDATES,
    ) == unordered_out_result


def test_ordinal_nicks():
    votes = {
        ('Au', 'An'): 3,
        ('An', 'Au'): 2,
    }
    assert votelib.io.stv.dumps(
        votes,
        votelib.evaluate.sequential.TransferableVoteSelector(),
        output_method=False
    ) == (
        'quota=droop\ncandidate=a Au\ncandidate=b An\nballots=2\n'
        '3X a b\n2X b a\nend\n'
    )


def test_warn_distributor():
    with pytest.warns(UserWarning):
        votelib.io.stv.dumps(
            CUSTOM_VOTES,
            votelib.evaluate.sequential.TransferableVoteDistributor(),
        )


def test_out_error_nonunit_step():
    with pytest.raises(votelib.io.stv.NotSupportedInSTV):
        votelib.io.stv.dumps(
            CUSTOM_VOTES,
            votelib.evaluate.sequential.TransferableVoteSelector(
                eliminate_step=2,
            ),
        )


def test_out_error_bad_quota():
    with pytest.raises(votelib.io.stv.NotSupportedInSTV):
        votelib.io.stv.dumps(
            CUSTOM_VOTES,
            votelib.evaluate.sequential.TransferableVoteSelector(
                quota_function='hagenbach_bischoff',
            ),
        )


def test_out_error_equal_ranking():
    with pytest.raises(votelib.io.stv.NotSupportedInSTV):
        votelib.io.stv.dumps(
            {(frozenset('AB'), 'C'): 1},
            votelib.evaluate.sequential.TransferableVoteSelector(),
        )


def test_out_blt():
    assert votelib.io.stv.dumps(BLT_VOTES, n_seats=BLT_N_SEATS) == BLT_RESULT


def test_in_blt():
    voting_setup = votelib.io.stv.loads(BLT_RESULT)
    check_votes_equal(voting_setup.votes, BLT_VOTES)
    check_candidates_equal(voting_setup.candidates, list('ABC'))
    assert voting_setup.system.evaluator.n_seats == BLT_N_SEATS


def test_in_unordered(unordered_result):
    voting_setup = votelib.io.stv.loads(unordered_result)
    check_votes_equal(voting_setup.votes, UNORDERED_VOTES)
    check_candidates_equal(voting_setup.candidates, EXAMPLE_CANDIDATES)
    system = voting_setup.system
    # compare systems (via internal components)
    assert isinstance(system, type(UNORDERED_SYSTEM))
    assert system.name == UNORDERED_SYSTEM.name
    assert isinstance(system.evaluator, type(UNORDERED_SYSTEM.evaluator))
    assert system.evaluator.n_seats == UNORDERED_SYSTEM.evaluator.n_seats
    assert isinstance(system.evaluator.evaluator, type(UNORDERED_SYSTEM.evaluator.evaluator))
    assert isinstance(system.evaluator.evaluator.main, type(UNORDERED_SYSTEM.evaluator.evaluator.main))
    assert system.evaluator.evaluator.main._inner.quota_function == UNORDERED_SYSTEM.evaluator.evaluator.main._inner.quota_function
    assert system.evaluator.evaluator.main._inner.mandatory_quota == UNORDERED_SYSTEM.evaluator.evaluator.main._inner.mandatory_quota
    assert isinstance(system.evaluator.evaluator.tiebreaker, type(UNORDERED_SYSTEM.evaluator.evaluator.tiebreaker))
    assert isinstance(system.evaluator.evaluator.tiebreaker.evaluator, type(UNORDERED_SYSTEM.evaluator.evaluator.tiebreaker.evaluator))
    assert system.evaluator.evaluator.tiebreaker.evaluator.seed == UNORDERED_SYSTEM.evaluator.evaluator.tiebreaker.evaluator.seed


def test_in_ordered(ordered_result):
    voting_setup = votelib.io.stv.loads(ordered_result)
    check_votes_equal(voting_setup.votes, ORDERED_VOTES)
    check_candidates_equal(voting_setup.candidates, EXAMPLE_CANDIDATES)
    system = voting_setup.system
    # compare systems (via internal components)
    assert isinstance(system, type(ORDERED_SYSTEM))
    assert system.name == ORDERED_SYSTEM.name
    assert isinstance(system.evaluator, type(ORDERED_SYSTEM.evaluator))
    assert system.evaluator.n_seats == ORDERED_SYSTEM.evaluator.n_seats
    assert isinstance(system.evaluator.evaluator, type(ORDERED_SYSTEM.evaluator.evaluator))
    assert isinstance(system.evaluator.evaluator.main, type(ORDERED_SYSTEM.evaluator.evaluator.main))
    assert system.evaluator.evaluator.main._inner.quota_function == ORDERED_SYSTEM.evaluator.evaluator.main._inner.quota_function
    assert system.evaluator.evaluator.main._inner.mandatory_quota == ORDERED_SYSTEM.evaluator.evaluator.main._inner.mandatory_quota
    assert isinstance(system.evaluator.evaluator.tiebreaker, type(ORDERED_SYSTEM.evaluator.evaluator.tiebreaker))
    assert isinstance(system.evaluator.evaluator.tiebreaker.evaluator, type(ORDERED_SYSTEM.evaluator.evaluator.tiebreaker.evaluator))


def test_in_error_bad_quota():
    with pytest.raises(votelib.io.stv.STVParseError) as excinfo:
        votelib.io.stv.loads('method=BC\nquota=whatever\nballots=34')
    assert 'unknown quota' in str(excinfo.value)


def test_in_error_invalid_seats():
    with pytest.raises(votelib.io.stv.STVParseError) as excinfo:
        votelib.io.stv.loads('method=BC\nseats=whatever\nquota=hare\nballots=34')
    assert 'invalid seat count' in str(excinfo.value)


def test_in_error_duplicate_title():
    with pytest.raises(votelib.io.stv.STVParseError) as excinfo:
        votelib.io.stv.loads('title=My Election\ntitle=Her Election\nmethod=GPCA2000\nballots=42')
    assert 'duplicate' in str(excinfo.value)


def test_in_unordered_roundtrip(unordered_out_result):
    assert votelib.io.stv.dumps(votelib.io.stv.loads(unordered_out_result)) == unordered_out_result


def check_votes_equal(tested, expected):
    # strip numbers to compare to candidate names
    assert {
        tuple(c.name for c in vote): n_votes
        for vote, n_votes in tested.items()
    } == expected


def check_candidates_equal(tested, expected):
    # strip numbers to compare to candidate names
    assert [c.name for c in tested] == expected


def test_in_incomplete():
    with pytest.raises(votelib.io.stv.STVParseError):
        votelib.io.stv.loads('method=BC\nquota=hare')


def test_in_bad_header():
    with pytest.raises(votelib.io.stv.STVParseError):
        votelib.io.stv.loads('method=BC\nsomething very stupid\nseats=2')

