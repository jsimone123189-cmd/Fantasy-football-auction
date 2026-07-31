import pandas as pd
import pytest

from draft_helper.analysis.cheat_sheet import generate_cheat_sheet, load_projections
from draft_helper.analysis.inflation import build_position_rank_curve


def make_curve():
    rows = [
        dict(season="2022", position="RB", cost=100),
        dict(season="2022", position="RB", cost=50),
        dict(season="2022", position="WR", cost=50),
        dict(season="2023", position="RB", cost=80),
        dict(season="2023", position="RB", cost=40),
        dict(season="2023", position="WR", cost=80),
    ]
    return build_position_rank_curve(pd.DataFrame(rows))


def test_generate_cheat_sheet_sorted_by_target_price():
    curve = make_curve()
    proj = pd.DataFrame(
        [
            {"player_name": "Star RB", "position": "RB", "projected_rank": 1},
            {"player_name": "Backup RB", "position": "RB", "projected_rank": 2},
            {"player_name": "Star WR", "position": "WR", "projected_rank": 1},
        ]
    )
    sheet = generate_cheat_sheet(proj, curve, num_teams=1, budget_per_team=200)
    assert list(sheet["player_name"]) == sorted(
        sheet["player_name"], key=lambda n: -sheet.set_index("player_name").loc[n, "target_price"]
    )
    assert sheet.iloc[0]["player_name"] == "Star RB"


def test_generate_cheat_sheet_excludes_and_deducts_keepers():
    curve = make_curve()
    proj = pd.DataFrame(
        [
            {"player_name": "Star RB", "position": "RB", "projected_rank": 1},
            {"player_name": "Backup RB", "position": "RB", "projected_rank": 2},
        ]
    )
    keepers = pd.DataFrame([{"player_name": "Star RB", "cost": 40, "team_name": "A"}])
    sheet = generate_cheat_sheet(proj, curve, num_teams=1, budget_per_team=200, keeper_costs=keepers)
    assert "Star RB" not in sheet["player_name"].values
    # effective budget is now 160, so Backup RB's target price should scale down accordingly.
    unadjusted = generate_cheat_sheet(proj, curve, num_teams=1, budget_per_team=200)
    backup_unadjusted = unadjusted.set_index("player_name").loc["Backup RB", "target_price"]
    backup_adjusted = sheet.set_index("player_name").loc["Backup RB", "target_price"]
    assert backup_adjusted < backup_unadjusted


def test_load_projections_derives_rank_from_points(tmp_path):
    path = tmp_path / "proj.csv"
    pd.DataFrame(
        [
            {"player_name": "A", "position": "RB", "projected_points": 100},
            {"player_name": "B", "position": "RB", "projected_points": 200},
        ]
    ).to_csv(path, index=False)
    proj = load_projections(str(path))
    assert proj.set_index("player_name").loc["B", "projected_rank"] == 1
    assert proj.set_index("player_name").loc["A", "projected_rank"] == 2


def test_load_projections_requires_rank_or_points(tmp_path):
    path = tmp_path / "proj.csv"
    pd.DataFrame([{"player_name": "A", "position": "RB"}]).to_csv(path, index=False)
    with pytest.raises(ValueError):
        load_projections(str(path))
