"""Team DEF/ST projections, scored against the league's real, fully-specified
Yahoo DEF rules (confirmed via a screenshot of the actual settings page, Aug
2026) -- sacks, interceptions, fumble recoveries, defensive/return TDs,
safeties, blocked kicks, and points-/yards-allowed tiers. This replaces a
cruder win-total-only heuristic with the real scoring table; the *inputs*
(how many sacks/INTs/points-allowed a defense produces) are still team-
quality estimates, not individually researched per team the way skill-
position players are -- DEF is 0.9% of this league's historical spend (see
the strategy report), so this is intentionally less deep than the player
model, but the scoring math itself is exact.

Run as: python -m draft_helper.projections.def_model
"""
from __future__ import annotations

import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEAM_CONTEXT_PATH = os.path.join(BASE_DIR, "data", "research", "team_context_2026.csv")
OUT_PATH = os.path.join(BASE_DIR, "data", "projections", "def_2026.csv")

POINTS_ALLOWED_TIERS = [
    (0, 10), (6, 8), (13, 5), (20, 2), (27, 0), (34, -3), (float("inf"), -6),
]
YARDS_ALLOWED_TIERS = [
    (99, 8), (199, 6), (299, 4), (399, 2), (499, 0), (float("inf"), -2),
]

# Team-quality tiers (win_total-driven, with a few explicit real-signal
# overrides) -> estimated per-game defensive counting stats. These are the
# "opportunity+efficiency" inputs for DEF, analogous to the per-player rows
# for skill positions, just coarser given how little of the auction budget
# DEF ever commands.
TIERS = {
    "elite": dict(sacks_pg=3.1, int_pg=1.05, fum_rec_pg=0.65, def_td_per_season=6.0, pts_allowed_pg=18.5, yds_allowed_pg=305),
    "good": dict(sacks_pg=2.7, int_pg=0.9, fum_rec_pg=0.6, def_td_per_season=4.0, pts_allowed_pg=20.5, yds_allowed_pg=330),
    "average": dict(sacks_pg=2.3, int_pg=0.75, fum_rec_pg=0.55, def_td_per_season=3.0, pts_allowed_pg=22.5, yds_allowed_pg=350),
    "below-average": dict(sacks_pg=2.0, int_pg=0.65, fum_rec_pg=0.5, def_td_per_season=2.2, pts_allowed_pg=24.5, yds_allowed_pg=370),
    "poor": dict(sacks_pg=1.7, int_pg=0.55, fum_rec_pg=0.45, def_td_per_season=1.5, pts_allowed_pg=27.0, yds_allowed_pg=390),
}

# A few teams with real, specific 2026 defensive personnel/context signal
# (surfaced incidentally in this session's offense-focused research) get
# nudged up a tier or given a small explicit bonus, noted in the explanation.
REAL_SIGNAL_BONUS = {
    "Rams": (1.3, "traded for reigning Defensive Player of the Year Myles Garrett"),
    "Seahawks": (1.0, "defending Super Bowl champions under DC-turned-HC Mike Macdonald"),
    "Ravens": (0.5, "new HC Jesse Minter is a defensive-minded former DC"),
}


def _win_total_tier(win_total: float) -> str:
    if win_total >= 10.5:
        return "elite"
    if win_total >= 9.0:
        return "good"
    if win_total >= 7.5:
        return "average"
    if win_total >= 6.0:
        return "below-average"
    return "poor"


def _tiered_points(value: float, tiers: list[tuple[float, float]]) -> float:
    for threshold, points in tiers:
        if value <= threshold:
            return points
    return tiers[-1][1]


def project_defense(team: str, win_total: float) -> dict:
    tier_name = _win_total_tier(win_total)
    tier = TIERS[tier_name]
    bonus_pg, bonus_note = REAL_SIGNAL_BONUS.get(team, (0.0, ""))

    games = 17
    sack_pts = tier["sacks_pg"] * 1 * games
    int_pts = tier["int_pg"] * 2 * games
    fum_pts = tier["fum_rec_pg"] * 2 * games
    td_pts = tier["def_td_per_season"] * 6
    pts_allowed_pts = _tiered_points(tier["pts_allowed_pg"], POINTS_ALLOWED_TIERS) * games
    yds_allowed_pts = _tiered_points(tier["yds_allowed_pg"], YARDS_ALLOWED_TIERS) * games

    median = sack_pts + int_pts + fum_pts + td_pts + pts_allowed_pts + yds_allowed_pts + (bonus_pg * games)
    floor = median * 0.78
    ceiling = median * 1.25

    explanation = (
        f"{tier_name.capitalize()}-tier defensive projection from a {win_total:.1f}-win Vegas total (team "
        f"quality is a real, if imperfect, proxy for scoring defense -- DEF is 0.9% of this league's historical "
        f"spend, so this gets a lighter-touch treatment than skill positions). Scored against the league's exact "
        f"real DEF rules: ~{tier['sacks_pg']:.1f} sacks/g (1pt), ~{tier['int_pg']:.2f} INT/g (2pt), "
        f"~{tier['fum_rec_pg']:.2f} fumble rec/g (2pt), ~{tier['def_td_per_season']:.1f} defensive/return TDs/"
        f"season (6pt), ~{tier['pts_allowed_pg']:.1f} points allowed/g, and ~{tier['yds_allowed_pg']:.0f} yards "
        f"allowed/g (both scored on the league's tiered scale)."
    )
    if bonus_note:
        explanation += f" Bonus applied: {bonus_note}."
    explanation += f" Median {median:.0f} pts, floor {floor:.0f}, ceiling {ceiling:.0f}."

    return dict(team=team, projected_points=round(median, 1), floor=round(floor, 1),
                ceiling=round(ceiling, 1), risk_tier="medium", explanation=explanation)


def build(team_context_path: str = TEAM_CONTEXT_PATH) -> pd.DataFrame:
    tc = pd.read_csv(team_context_path)
    rows = [project_defense(row["team"], float(row["win_total"])) for _, row in tc.iterrows()]
    return pd.DataFrame(rows).sort_values("projected_points", ascending=False).reset_index(drop=True)


def main():
    out = build()
    out.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out)} defenses to {OUT_PATH}")


if __name__ == "__main__":
    main()
