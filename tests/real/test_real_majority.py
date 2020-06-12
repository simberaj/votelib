
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.candidate
import votelib.evaluate


def test_mex_prez_2018():
    votes = {
        'Andrés Manuel López Obrador': 30113483,
        'Ricardo Anaya': 12610120,
        'José Antonio Meade': 9289853,
        'Jaime Rodríguez Calderón': 2961732,
        'Margarita Zavala': 32743,
    }
    pers_votes = {
        votelib.candidate.Person(cand): n
        for cand, n in votes.items()
    }
    evaluator = votelib.evaluate.Plurality()
    assert evaluator.evaluate(votes) == evaluator.evaluate(votes, 1)
    assert evaluator.evaluate(votes, 1) == ['Andrés Manuel López Obrador']
    nominator = votelib.candidate.PersonNominator()
    for cand in pers_votes.keys():
        nominator.validate(cand)
    assert evaluator.evaluate(pers_votes, 1) == [max(
        pers_votes.keys(), key=pers_votes.get
    )]
