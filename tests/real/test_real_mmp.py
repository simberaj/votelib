
import sys
import os
import csv
from decimal import Decimal

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import votelib.convert
import votelib.evaluate.core
import votelib.evaluate.proportional
import votelib.evaluate.threshold

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


NZ_LEG_2014_PARTY_VOTE = {
    'ACT New Zealand':                  16689,
    'Aotearoa Legalise Cannabis Party': 10961,
    'Ban1080':                          5113,
    'Conservative':                     95598,
    'Democrats for Social Credit':      1730,
    'Focus New Zealand':                639,
    'Green Party':                      257359,
    'Internet MANA':                    34094,
    'Labour Party':                     604535,
    'Māori Party':                      31849,
    'National Party':                   1131501,
    'New Zealand First Party':          208300,
    'NZ Independent Coalition':         872,
    'The Civilian Party':               1096,
    'United Future':                    5286,
}

NZ_LEG_2008_PARTY_VOTE = {
    'ACT New Zealand': 85496,
    'Alliance': 1909,
    'Aotearoa Legalise Cannabis Party': 9515,
    'Democrats for Social Credit': 1208,
    'Family Party': 8176,
    'Green Party': 157613,
    'Progressive': 21241,
    'Kiwi Party': 12755,
    'Labour Party': 796880,
    'Libertarianz': 1176,
    'Māori Party': 55980,
    'National Party': 1053398,
    'New Zealand First Party': 95356,
    'New Zealand Pacific Party': 8640,
    'RAM - Residents Action Movement': 465,
    'The Bill and Ben Party': 13016,
    'The Republic of New Zealand Party': 313,
    'United Future': 20497,
    'Workers Party': 932,
}

NZ_ELECTORATE_EVAL = votelib.evaluate.core.PostConverted(
    votelib.evaluate.core.ByConstituency(
        votelib.evaluate.core.PostConverted(
            votelib.evaluate.core.Plurality(),
            votelib.convert.SelectionToDistribution()
        ),
        apportioner=1
    ),
    votelib.convert.MergedDistributions()
)

NZ_PARTYLIST_EVAL = votelib.evaluate.core.Conditioned(
    votelib.evaluate.threshold.AlternativeThresholds([
        votelib.evaluate.threshold.RelativeThreshold(Decimal('.05')),
        votelib.evaluate.threshold.PreviousGainThreshold(
            votelib.evaluate.threshold.AbsoluteThreshold(1)
        )
    ]),
    votelib.evaluate.proportional.HighestAverages('sainte_lague')
)

@pytest.fixture(scope='module')
def nz_leg_2014_electorate_data():
    fpath = os.path.join(DATA_DIR, 'nz_leg_2014_electorate.csv')
    with open(fpath, encoding='utf8') as infile:
        rows = list(csv.reader(infile, delimiter=';'))
    party_names = rows[0][1:]
    return {
        row[0]: dict(zip(party_names, [int(n_votes) for n_votes in row[1:]]))
        for row in rows[1:]
    }


def test_nz_leg_2014_raw(nz_leg_2014_electorate_data):
    elect_res = NZ_ELECTORATE_EVAL.evaluate(nz_leg_2014_electorate_data)
    assert elect_res == {
        'ACT New Zealand': 1,
        'Labour Party': 27,
        'Māori Party': 1,
        'National Party': 41,
        'United Future': 1,
    }


def test_nz_leg_2014(nz_leg_2014_electorate_data):
    total_evaluator = votelib.evaluate.core.MultistageDistributor([
        NZ_ELECTORATE_EVAL,
        votelib.evaluate.core.AdjustedSeatCount(
            votelib.evaluate.core.AllowOverhang(NZ_PARTYLIST_EVAL.evaluator),
            NZ_PARTYLIST_EVAL,
        )
    ])
    total_res = total_evaluator.evaluate(
        [nz_leg_2014_electorate_data, NZ_LEG_2014_PARTY_VOTE], 120
    )
    assert total_res == {
        'ACT New Zealand': 1,
        'Labour Party': 32,
        'Māori Party': 2,
        'National Party': 60,
        'United Future': 1,
        'Green Party': 14,
        'New Zealand First Party': 11,
    }


def test_nz_leg_2008():
    elect_res = {
        'ACT New Zealand': 1,
        'Labour Party': 21,
        'Māori Party': 5,
        'National Party': 41,
        'United Future': 1,
        'Progressive': 1,
    }
    
    class MockEvaluator:
        def evaluate(self, *args, **kwargs):
            return elect_res

    total_evaluator = votelib.evaluate.core.MultistageDistributor([
        MockEvaluator(),
        votelib.evaluate.core.AdjustedSeatCount(
            votelib.evaluate.core.AllowOverhang(NZ_PARTYLIST_EVAL.evaluator),
            NZ_PARTYLIST_EVAL,
        )
    ])
    total_res = total_evaluator.evaluate(
        NZ_LEG_2008_PARTY_VOTE, 120
    )
    assert total_res == {
        'ACT New Zealand': 5,
        'Labour Party': 43,
        'Māori Party': 5,
        'National Party': 58,
        'United Future': 1,
        'Progressive': 1,
        'Green Party': 9,
    }


@pytest.fixture(scope='module')
def de_bdt_2017_votes():
    fpath = os.path.join(DATA_DIR, 'de_bdt_2017.csv')
    with open(fpath, encoding='utf8') as infile:
        rows = list(csv.reader(infile, delimiter=';'))
    party_names = [item for item in rows[0][2:] if item]
    wahlkreis_votes, party_votes = {}, {}
    for row in rows[2:]:
        wahlkreis, land = row[:2]
        row[2:] = [int(x) if x else 0 for x in row[2:]]
        wahlkreis_votes.setdefault(land, {})[wahlkreis] = dict(zip(party_names, row[2::2]))
        party_votes.setdefault(land, {})[wahlkreis] = dict(zip(party_names, row[3::2]))
    return wahlkreis_votes, party_votes


def get_de_bdt_evaluator():
    sainte_lague = votelib.evaluate.proportional.HighestAverages('sainte_lague')
    land_inhab = {
        'Schleswig-Holstein': 2673803,
        'Hamburg': 1525090,
        'Niedersachsen': 7278789,
        'Bremen': 568510,
        'Nordrhein-Westfalen': 15707569,
        'Hessen': 5281198,
        'Rheinland-Pfalz': 3661245,
        'Baden-Württemberg': 9365001,
        'Bayern': 11362245,
        'Saarland': 899748,
        'Berlin': 2975745,
        'Brandenburg': 2391746,
        'Mecklenburg-Vorpommern': 1548400,
        'Sachsen': 3914671,
        'Sachsen-Anhalt': 2145671,
        'Thüringen': 2077901,
    }
    land_seats = sainte_lague.evaluate(land_inhab, 598)
    land_wk_eval = votelib.evaluate.core.ByConstituency(
        votelib.evaluate.core.PostConverted(
            votelib.evaluate.core.ByConstituency(
                votelib.evaluate.core.PostConverted(
                    votelib.evaluate.core.Plurality(),
                    votelib.convert.SelectionToDistribution()
                ),
                apportioner=1,
            ),
            votelib.convert.MergedDistributions()
        )
    )
    land_prop_eval = votelib.evaluate.core.ByConstituency(
        sainte_lague,
        apportioner=land_seats,
        preselector=votelib.evaluate.threshold.RelativeThreshold(Decimal('.05'))
    )
    nat_eval = votelib.evaluate.core.Conditioned(
        votelib.evaluate.threshold.AlternativeThresholds([
            votelib.evaluate.threshold.RelativeThreshold(Decimal('.05')),
            votelib.evaluate.threshold.PreviousGainThreshold(
                votelib.evaluate.threshold.AbsoluteThreshold(3)
            )
        ]),
        sainte_lague
    )
    return votelib.evaluate.FixedSeatCount(
        votelib.evaluate.core.MultistageDistributor([
            land_wk_eval,
            votelib.evaluate.core.PreConverted(
                votelib.convert.ByConstituency(votelib.convert.VoteTotals()),
                votelib.evaluate.core.AdjustedSeatCount(
                    calculator=votelib.evaluate.core.LevelOverhangByConstituency(
                        constituency_evaluator=land_prop_eval,
                        overall_evaluator=nat_eval,
                    ),
                    evaluator=votelib.evaluate.core.ByParty(
                        overall_evaluator=nat_eval,
                        allocator=sainte_lague,
                    )
                )
            )
        ], depth=2),
        598
    )
    

def test_de_bdt_2017(de_bdt_2017_votes):
    # https://www.bundeswahlleiter.de/dam/jcr/3f3d42ab-faef-4553-bdf8-ac089b7de86a/btw17_heft3.pdf
    wahlkreis_votes, party_votes = de_bdt_2017_votes
    total_eval = get_de_bdt_evaluator()
    land_result = total_eval.evaluate([wahlkreis_votes, party_votes])
    bund_result = votelib.convert.MergedDistributions().convert(land_result)
    assert bund_result == {
        'CDU': 200, 'SPD': 153, 'AfD': 94, 'FDP': 80, 'DIE LINKE': 69,
        'GRÜNE': 67, 'CSU': 46
    }
    assert land_result['Mecklenburg-Vorpommern'] == {
        'CDU': 6, 'SPD': 2, 'AfD': 3, 'FDP': 1, 'DIE LINKE': 3, 'GRÜNE': 1
    }


def get_evaluators():
    return [
        get_de_bdt_evaluator(),
        NZ_ELECTORATE_EVAL,
        NZ_PARTYLIST_EVAL,
    ]