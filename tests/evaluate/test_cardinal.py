import votelib.evaluate.cardinal


def test_allocated_score_selection():
    votes = {
        frozenset([('A', 5), ('B', 3), ('C', 1)]): 8,
        frozenset([('C', 5), ('D', 3), ('B', 1)]): 4,
    }
    ev = votelib.evaluate.cardinal.AllocatedScoreSelector()
    result = ev.evaluate(votes, n_seats=2)
    assert result == ['A', 'C']


def test_allocated_score_distribution():
    votes = {
        frozenset([('A', 5), ('B', 3), ('C', 1)]): 8,
        frozenset([('C', 5), ('D', 3), ('B', 1)]): 4,
    }
    ev = votelib.evaluate.cardinal.AllocatedScoreDistributor()
    result = ev.evaluate(votes, n_seats=3)
    assert result == {'A': 2, 'C': 1}


def test_allocated_score_tie():
    votes = {
        frozenset([('A', 5), ('B', 3), ('D', 1)]): 4,
        frozenset([('C', 5), ('D', 3), ('B', 1)]): 4,
    }
    ev = votelib.evaluate.cardinal.AllocatedScoreDistributor()
    result = ev.evaluate(votes, n_seats=3)
    assert result == {'A': 1, 'C': 1, votelib.evaluate.core.Tie(['A', 'C']): 1}
