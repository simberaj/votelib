
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.evaluate.approval


def test_cz_sen_2018_68():
    votes = {
        'Vícha Josef': 3241,
        'Pavlíček Petr': 5014,
        'Běrský Kamil MUDr.': 2885,
        'Kupka Vlastimil Bc.': 2030,
        'Tancík Vladimír Mgr.': 5324,
        'Pavera Herbert Mgr.': 15900,
        'Horáková Simona Mgr.': 9443,
    }
    evaluator = votelib.evaluate.approval.QuotaSelector()
    assert evaluator.evaluate(votes, 1) == []

def test_cz_sen_2018_20():
    votes = {
        'Dvořák Martin Ing.': 4868,
        'Drahoš Jiří prof. Ing. DrSc.': 20595,
        'Kuras Benjamin Miloslav': 2801,
        'Syková Eva prof. MUDr. DrSc.': 5110,
        'Skovajsová Miroslava MUDr. Ph.D.': 3058,
        'Skoupil Karel': 1169,
        'Mazáč Rudolf Karel Mgr.': 258,
        'Kocman Jiří Ing.': 1251,
    }
    evaluator = votelib.evaluate.approval.QuotaSelector()
    assert evaluator.evaluate(votes, 1) == ['Drahoš Jiří prof. Ing. DrSc.']
