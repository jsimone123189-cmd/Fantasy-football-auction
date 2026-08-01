import json
import re

import pandas as pd

from draft_helper.analysis.inflation import build_position_rank_curve
from draft_helper.web import generate_html


def make_curve():
    rows = [
        dict(season="2022", position="RB", cost=100),
        dict(season="2022", position="RB", cost=50),
        dict(season="2023", position="RB", cost=80),
        dict(season="2023", position="RB", cost=40),
    ]
    return build_position_rank_curve(pd.DataFrame(rows))


def test_generate_html_embeds_valid_json_with_expected_players():
    curve = make_curve()
    proj = pd.DataFrame(
        [
            {"player_name": "Star RB", "position": "RB", "projected_rank": 1},
            {"player_name": "Backup RB", "position": "RB", "projected_rank": 2},
        ]
    )
    html = generate_html(curve, proj, num_teams=1, budget_per_team=200, roster_size=5, team_names=["A", "B"])

    match = re.search(r'<script id="draftData" type="application/json">(.*?)</script>', html, re.S)
    assert match is not None
    data = json.loads(match.group(1))
    names = {p["name"] for p in data["players"]}
    assert names == {"Star RB", "Backup RB"}
    assert data["players"][0]["name"] == "Star RB"  # sorted by baseline desc
    assert data["budget"] == 200
    assert data["rosterSize"] == 5
    assert '"A"' in html and '"B"' in html


def test_generate_html_has_no_leftover_placeholders():
    curve = make_curve()
    proj = pd.DataFrame([{"player_name": "Star RB", "position": "RB", "projected_rank": 1}])
    html = generate_html(curve, proj, num_teams=1, budget_per_team=200, roster_size=5, team_names=["A"])
    assert "{data_json}" not in html
    assert "{title}" not in html
    assert html.count("<title>") == 1
