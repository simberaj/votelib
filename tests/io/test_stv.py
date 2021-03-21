
import sys
import os

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.io.stv
import votelib.convert
import votelib.evaluate.auxiliary
import votelib.evaluate.sequential

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

CUSTOM_SYSTEM = votelib.VotingSystem(
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
UNORDERED_SYSTEM = votelib.VotingSystem(
    'STV Voting Example 2007-05-01',
    votelib.evaluate.FixedSeatCount(
        votelib.evaluate.TieBreaking(
            votelib.evaluate.sequential.TransferableVoteSelector(
                quota_function='droop',
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
UNORDERED_CANDIDATES = [
    'George Brown', 'Mary Green', 'Hermione Tan', 'Harvey Black',
    'Violet Smith', 'Able Body'
]


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


def test_out_custom_system(custom_standard_result):
    assert votelib.io.stv.dumps(CUSTOM_VOTES, CUSTOM_SYSTEM, n_seats=2) == custom_standard_result


def test_out_custom_blt(custom_blt_result):
    assert votelib.io.stv.dumps(CUSTOM_VOTES, n_seats=2) == custom_blt_result


def test_out_unordered(unordered_out_result):
    assert votelib.io.stv.dumps(
        UNORDERED_VOTES,
        UNORDERED_SYSTEM,
        candidates=UNORDERED_CANDIDATES,
        output_method=False,
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


def test_error_nonunit_step():
    with pytest.raises(votelib.io.stv.NotSupportedInSTV):
        votelib.io.stv.dumps(
            CUSTOM_VOTES,
            votelib.evaluate.sequential.TransferableVoteSelector(
                eliminate_step=2,
            ),
        )


def test_error_bad_quota():
    with pytest.raises(votelib.io.stv.NotSupportedInSTV):
        votelib.io.stv.dumps(
            CUSTOM_VOTES,
            votelib.evaluate.sequential.TransferableVoteSelector(
                quota_function='hagenbach_bischoff',
            ),
        )
