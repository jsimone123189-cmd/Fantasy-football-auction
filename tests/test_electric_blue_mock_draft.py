import pandas as pd

from draft_helper.electric_blue.mock_draft import optimal_lineup_points, simulate_draft


def _pool():
    rows = []
    # A deep, VOR-descending pool across positions so BPA has real choices
    # at every pick, including enough RB/WR to outlast K/DEF deferral.
    for i in range(60):
        rows.append({"player_name": f"RB{i}", "position": "RB", "nfl_team": "X", "projected_points": 200 - i, "vor": 100 - i})
    for i in range(60):
        rows.append({"player_name": f"WR{i}", "position": "WR", "nfl_team": "X", "projected_points": 190 - i, "vor": 95 - i})
    for i in range(24):
        rows.append({"player_name": f"QB{i}", "position": "QB", "nfl_team": "X", "projected_points": 250 - i, "vor": 90 - i})
    for i in range(24):
        rows.append({"player_name": f"TE{i}", "position": "TE", "nfl_team": "X", "projected_points": 120 - i, "vor": 40 - i})
    # DEF given artificially high VOR -- exactly the real-world distortion
    # this league's actual scoring produces -- to prove the deferral rule
    # actually overrides raw VOR rather than coincidentally not mattering.
    for i in range(5):
        rows.append({"player_name": f"DEF{i}", "position": "DEF", "nfl_team": "X", "projected_points": 175 - i, "vor": 145 - i})
    return pd.DataFrame(rows)


def test_def_is_never_drafted_before_the_deferral_round():
    pool = _pool()
    rosters = simulate_draft(pool, num_teams=12, rounds=14)
    picks_per_team = 14
    for slot, roster in rosters.items():
        for i, pick in enumerate(roster):
            rnd = i + 1  # each team's own Nth pick == round N
            if pick["position"] == "DEF":
                assert rnd >= 13, f"slot {slot} drafted {pick['player_name']} ({pick['position']}) in round {rnd}"


def test_keeper_is_inserted_at_its_real_round_not_live_drafted():
    pool = _pool()
    keepers = {0: [(3, "RB0")]}  # slot 0's round-3 pick is a keeper: the highest-VOR player in the pool
    rosters = simulate_draft(pool, num_teams=4, rounds=5, keepers=keepers)
    # RB0 (the single best player in the whole pool) should NOT go 1st overall --
    # it's reserved for slot 0's round 3, not live-picked by anyone else either.
    assert rosters[0][2]["player_name"] == "RB0"
    all_other_picks = [p["player_name"] for slot, roster in rosters.items() if slot != 0 for p in roster]
    assert "RB0" not in all_other_picks


def test_keeper_team_does_not_get_an_extra_live_pick_that_round():
    pool = _pool()
    keepers = {0: [(2, "RB0")]}
    rosters = simulate_draft(pool, num_teams=4, rounds=5, keepers=keepers)
    # slot 0 still ends up with exactly 5 total roster spots (1 keeper + 4 live picks),
    # not 6 -- the keeper occupies its round, it doesn't add to it.
    assert len(rosters[0]) == 5


def test_optimal_lineup_points_uses_flex_for_best_remaining_rwt():
    roster = [
        {"position": "QB", "projected_points": 300},
        {"position": "RB", "projected_points": 200},
        {"position": "RB", "projected_points": 150},
        {"position": "RB", "projected_points": 140},  # should fill FLEX
        {"position": "WR", "projected_points": 130},
        {"position": "WR", "projected_points": 100},
        {"position": "TE", "projected_points": 80},
        {"position": "DEF", "projected_points": 50},
    ]
    total = optimal_lineup_points(roster)
    assert total == 300 + 200 + 150 + 130 + 100 + 80 + 50 + 140
