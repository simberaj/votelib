
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

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

@pytest.fixture(scope='module')
def sk_nr_2020_data():
    fpath = os.path.join(DATA_DIR, 'sk_nr_2020.csv')
    with open(fpath, encoding='utf8') as infile:
        rows = list(csv.reader(infile, delimiter=';'))
    party_names, coalflags, votes, seats = [list(x) for x in zip(*rows)]
    parties = [
        votelib.candidate.Coalition(name=name, parties=[
            votelib.candidate.PoliticalParty(pname)
            for pname in name.split('-')
        ])
        if int(coalflag) else votelib.candidate.PoliticalParty(name)
        for name, coalflag in zip(party_names, coalflags)
    ]
    return dict(zip(parties, [int(v) for v in votes])), {
        party: int(n_seats)
        for party, n_seats in zip(parties, seats) if int(n_seats) > 0
    }


def get_sk_nr_evaluator():
    standard_elim = votelib.evaluate.threshold.RelativeThreshold(
        decimal.Decimal('.05'), accept_equal=True
    )
    mem_2_3_elim = votelib.evaluate.threshold.RelativeThreshold(
        decimal.Decimal('.07'), accept_equal=True
    )
    mem_4plus_elim = votelib.evaluate.threshold.RelativeThreshold(
        decimal.Decimal('.1'), accept_equal=True
    )
    eliminator = votelib.evaluate.threshold.CoalitionMemberBracketer(
        {1: standard_elim, 2: mem_2_3_elim, 3: mem_2_3_elim},
        mem_4plus_elim
    )
    # main evaluator
    evaluator = votelib.evaluate.proportional.LargestRemainder(
        'hagenbach_bischoff_rounded'
    )
    # TODO: missing provisions for tie handling and low amount of candidates
    return votelib.evaluate.core.Conditioned(eliminator, evaluator)
    

def test_sk_nr_2020(sk_nr_2020_data):
    votes, results = sk_nr_2020_data
    nominator = votelib.candidate.PartyNominator()
    for cand in votes.keys():
        nominator.validate(cand)
    assert get_sk_nr_evaluator().evaluate(votes, 150) == results


CZ_EP_EVALUATOR = votelib.evaluate.core.FixedSeatCount(
    votelib.evaluate.core.Conditioned(
        votelib.evaluate.threshold.RelativeThreshold(
            decimal.Decimal('.05'), accept_equal=True
        ),
        votelib.evaluate.proportional.HighestAverages('d_hondt')
    ),
    21
)


def test_cz_ep_2019():
    votes = {
        'Klub angažovaných nestraníků': 2580,
        'Strana nezávislosti ČR': 9676,
        'Cesta odpovědné společnosti': 7890,
        'Národní socialisté': 1312,
        'Občanská demokratická strana': 344885,
        'ANO, vytrollíme europarlament': 37046,
        'Česká strana sociálně demokratická': 93664,
        'Romská demokratická strana': 1651,
        'KSČM': 164624,
        'Koalice DSSS a NF': 4363,
        'SPR-RSČ': 4284,
        'Koalice Rozumní, ND': 18715,
        'Pravý Blok': 4752,
        'NE-VOLIM.CZ': 2221,
        'Pro Česko': 2760,
        'Vědci pro Českou republiku': 19492,
        'Koalice ČSNS, Patrioti ČR': 1289,
        'JSI PRO?Jist.Solid.In.pro bud.': 836,
        'PRO Zdraví a Sport': 7868,
        'Moravské zemské hnutí': 3195,
        'Česká Suverenita': 2609,
        'TVŮJ KANDIDÁT': 1653,
        'HLAS': 56449,
        'Koalice Svobodní, RČ': 15492,
        'Koalice STAN, TOP 09': 276220,
        'Česká pirátská strana': 330844,
        'Svoboda a přímá demokracie': 216718,
        'Aliance národních sil': 1971,
        'ANO 2011': 502343,
        'Agrární demokratická strana': 4004,
        'Moravané': 6599,
        'První Republika': 844,
        'Demokratická strana zelených': 14339,
        'Bezpečnost,Odpovědnost,Solid.': 2583,
        'Koalice Soukromníci, NEZ': 8720,
        'Evropa společně': 12587,
        'Konzervativní Alternativa': 235,
        'KDU-ČSL': 171723,
        'Alternativa pro Česk. rep.2017': 11729,
    }
    results = {
        'ANO 2011': 6,
        'Občanská demokratická strana': 4,
        'Česká pirátská strana': 3,
        'Koalice STAN, TOP 09': 3,
        'Svoboda a přímá demokracie': 2,
        'KDU-ČSL': 2,
        'KSČM': 1,
    }
    assert CZ_EP_EVALUATOR.evaluate(votes) == results


CZ_PSP_EVALUATOR = votelib.evaluate.core.ByConstituency(
    votelib.evaluate.proportional.HighestAverages('d_hondt'),
    votelib.evaluate.proportional.LargestRemainder('hare'),
    preselector=votelib.evaluate.threshold.RelativeThreshold(
        decimal.Decimal('.05'), accept_equal=True
    )
)


@pytest.fixture(scope='module')
def cz_psp_2017_votes():
    fpath = os.path.join(DATA_DIR, 'cz_psp_2017.csv')
    with open(fpath, encoding='utf8') as infile:
        rows = list(csv.reader(infile, delimiter=';'))
    region_names = rows[0][1:]
    votes = {region: {} for region in region_names}
    for row in rows[1:]:
        party = row[0]
        for regname, n_votes in zip(region_names, row[1:]):
            votes[regname][party] = int(n_votes)
    return votes

def test_cz_psp_2017(cz_psp_2017_votes):
    reg_results = CZ_PSP_EVALUATOR.evaluate(cz_psp_2017_votes, 200)
    nat_agg = votelib.convert.VoteTotals()
    assert nat_agg.convert(reg_results) == {
        'ANO': 78,
        'ODS': 25,
        'Piráti': 22,
        'SPD': 22,
        'ČSSD': 15,
        'KSČM': 15,
        'KDU-ČSL': 10,
        'TOP 09': 7,
        'STAN': 6,
    }
    assert reg_results['Hlavní město Praha'] == {
        'ANO': 6,
        'ODS': 5,
        'Piráti': 5,
        'SPD': 1,
        'ČSSD': 1,
        'KSČM': 1,
        'KDU-ČSL': 1,
        'TOP 09': 3,
        'STAN': 1,
    }
    assert reg_results['Karlovarský kraj'] == {
        'ANO': 3,
        'Piráti': 1,
        'SPD': 1,
    }


def get_evaluators():
    return [
        CZ_EP_EVALUATOR,
        CZ_PSP_EVALUATOR,
        get_sk_nr_evaluator(),
    ]
