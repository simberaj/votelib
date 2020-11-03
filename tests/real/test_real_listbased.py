
import sys
import os
import csv
import decimal

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.candidate
import votelib.convert
import votelib.evaluate.threshold
import votelib.evaluate.proportional
import votelib.evaluate.openlist

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


@pytest.fixture(scope='module')
def nmnmet_cc_2018_data():
    fpath = os.path.join(DATA_DIR, 'nmnmet_cc_2018.csv')
    votes = {}
    party_objs = {}
    people_objs = {}
    party_lists = {}
    with open(fpath, encoding='utf8') as infile:
        for party, name, n_pers_votes in csv.reader(infile, delimiter=';'):
            party_obj = party_objs.setdefault(party, votelib.candidate.PoliticalParty(party))
            person = votelib.candidate.Person(
                name,
                candidacy_for=party_obj
            )
            people_objs[name] = person
            votes[person] = int(n_pers_votes)
            party_lists.setdefault(party_obj, []).append(person)
    results_noobj = {
        'ČSSD': ['Čopík Jan Ing. Ph.D.'],
        'KSČM': ['Kulhavá Zdeňka PhDr.'],
        'VPM': [
            'Hable Petr', 'Maur Vilém Ing. MBA', 'Hladík Jiří',
            'Prouza Radek', 'Petruželková Marie', 'Němeček Jan Ing.',
        ],
        'NM': ['Sláma Jiří Bc.', 'Žahourková Markéta', 'Paarová Soňa Mgr.'],
        'KDU-ČSL': ['Hylský Josef Mgr.', 'Neumann Petr Ing.', 'Dostál Pavel Ing. et Ing.'],
        'ODS': ['Hovorka Libor Ing.', 'Kupková Irena Mgr.', 'Slavík Milan Ing.', 'Jarolímek Miroslav'],
        'VČ': ['Tymel Jiří Ing.', 'Prouza Martin Ing.', 'Balcarová Jana Mgr.'],
    }
    results_obj = {
        party_objs[party_name]: [people_objs[person_name] for person_name in name_list]
        for party_name, name_list in results_noobj.items()
    }
    return votes, party_lists, results_obj


def get_evaluators():
    mapper = votelib.candidate.IndividualToPartyMapper(independents='error')
    vote_grouper = votelib.convert.GroupVotesByParty(mapper)
    return [votelib.evaluate.core.FixedSeatCount(
        votelib.evaluate.core.PreConverted(
            vote_grouper,
            votelib.evaluate.core.PartyListEvaluator(
                votelib.evaluate.core.PreConverted(
                    votelib.convert.PartyTotals(),
                    votelib.evaluate.core.Conditioned(
                        votelib.evaluate.threshold.RelativeThreshold(
                            decimal.Decimal('.05'), accept_equal=True
                        ),
                        votelib.evaluate.proportional.HighestAverages('d_hondt'),
                    )
                ),
                votelib.evaluate.openlist.ThresholdOpenList(
                    jump_fraction=decimal.Decimal('.05')
                ),
                list_votes_converter=vote_grouper,
            )
        ),
        21
    )]


@pytest.fixture(scope='module')
def nmnmet_cc_2018_evaluator():
    return get_evaluators()[0]


def test_nmnmet_cc_2018(nmnmet_cc_2018_data, nmnmet_cc_2018_evaluator):
    votes, party_lists, results = nmnmet_cc_2018_data
    assert nmnmet_cc_2018_evaluator.evaluate(
        votes,
        list_votes=votes,
        party_lists=party_lists
    ) == results
