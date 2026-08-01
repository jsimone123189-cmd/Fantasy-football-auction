"""Per-manager draft tendency profiles, built purely from your league's own
historical auction results (no external projections needed).

Metrics are all relative — computed against your league's own year-to-year
totals — so they hold up even as your budget or league size has changed.
"""
from __future__ import annotations

import pandas as pd


def _manager_key(df: pd.DataFrame) -> pd.Series:
    guid = df["manager_guid"].astype("string")
    name = df["manager_name"].astype("string")
    return guid.fillna(name)


def build_tendency_profiles(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0)
    df["pick"] = pd.to_numeric(df["pick"], errors="coerce")
    df["is_keeper"] = df["is_keeper"].fillna(False).astype(bool)
    df["manager_key"] = _manager_key(df)

    season_pos_total = df.groupby(["season", "position"])["cost"].sum()
    season_total = df.groupby("season")["cost"].sum()
    league_pos_share = (season_pos_total / season_total).rename("league_pos_share")

    season_median_pick = df.groupby("season")["pick"].transform("median")
    df["is_early_pick"] = df["pick"] <= season_median_pick

    # League-wide baselines per season, so pace/shape are judged relative to
    # how this specific league's auctions actually run (half the picks are
    # always $1 dregs at the end, so >50% of $ going early is the norm, not
    # a personality trait — what matters is who's *more* front-loaded than
    # everyone else that year).
    def _season_hhi(sg: pd.DataFrame) -> float:
        t = sg["cost"].sum()
        if not t:
            return 0.0
        shares = (sg.groupby("position")["cost"].sum() / t).to_numpy()
        return float((shares**2).sum())

    league_early_share = {}
    league_hhi = {}
    for season, sg in df.groupby("season"):
        season_total_cost = sg["cost"].sum()
        league_early_share[season] = (
            sg.loc[sg["is_early_pick"], "cost"].sum() / season_total_cost if season_total_cost else 0.0
        )
        # average per-team HHI that season (each team's own position mix)
        team_hhis = [
            _season_hhi(tg) for _, tg in sg.groupby("team_name") if tg["cost"].sum()
        ]
        league_hhi[season] = sum(team_hhis) / len(team_hhis) if team_hhis else 0.0

    profiles = []
    for manager_key, g in df.groupby("manager_key"):
        name_mode = g["manager_name"].mode()
        display_name = name_mode.iat[0] if not name_mode.empty else manager_key
        seasons = sorted(g["season"].astype(str).unique().tolist())
        team_total = g["cost"].sum()

        pos_share = (
            g.groupby("position")["cost"].sum() / team_total
            if team_total
            else pd.Series(dtype=float)
        )

        agg_rows = []
        for season, sg in g.groupby("season"):
            sg_total = sg["cost"].sum()
            if not sg_total:
                continue
            for pos, pos_cost in sg.groupby("position")["cost"].sum().items():
                lg_share = league_pos_share.get((season, pos))
                if lg_share:
                    agg_rows.append((pos, (pos_cost / sg_total) / lg_share))
        aggression = pd.DataFrame(agg_rows, columns=["position", "ratio"])
        aggression_by_pos = (
            aggression.groupby("position")["ratio"].mean().sort_values(ascending=False)
            if not aggression.empty
            else pd.Series(dtype=float)
        )

        early_spend = g.loc[g["is_early_pick"], "cost"].sum()
        pct_spent_early = early_spend / team_total if team_total else 0.0

        # Per-season ratios vs this league's own norm that year, then averaged —
        # same pattern as position bias above, so a manager who paces/concentrates
        # exactly like everyone else in this league scores ~1.0x, not "extreme".
        pace_ratios, shape_ratios = [], []
        for season, sg in g.groupby("season"):
            sg_total = sg["cost"].sum()
            if not sg_total:
                continue
            sg_early_share = sg.loc[sg["is_early_pick"], "cost"].sum() / sg_total
            lg_early_share = league_early_share.get(season)
            if lg_early_share:
                pace_ratios.append(sg_early_share / lg_early_share)
            sg_hhi = _season_hhi(sg)
            lg_hhi = league_hhi.get(season)
            if lg_hhi:
                shape_ratios.append(sg_hhi / lg_hhi)
        pace_index = sum(pace_ratios) / len(pace_ratios) if pace_ratios else 1.0
        shape_index = sum(shape_ratios) / len(shape_ratios) if shape_ratios else 1.0

        keeper_g = g[g["is_keeper"]]
        keeper_rate = len(keeper_g) / len(g) if len(g) else 0.0
        avg_keeper_cost = keeper_g["cost"].mean() if not keeper_g.empty else None

        shares = pos_share.to_numpy()
        hhi = float((shares**2).sum()) if len(shares) else 0.0
        top_pick_share = (g["cost"].max() / team_total) if team_total else 0.0

        profiles.append(
            {
                "manager_key": manager_key,
                "manager_name": display_name,
                "seasons": ", ".join(seasons),
                "num_seasons": len(seasons),
                "num_picks": int(len(g)),
                "total_spend": float(team_total),
                "avg_pick_cost": float(g["cost"].mean()) if len(g) else 0.0,
                "pct_budget_early": round(float(pct_spent_early), 3),
                "pace_index": round(float(pace_index), 3),
                "position_concentration_hhi": round(hhi, 3),
                "shape_index": round(float(shape_index), 3),
                "top_pick_share": round(float(top_pick_share), 3),
                "keeper_rate": round(float(keeper_rate), 3),
                "avg_keeper_cost": None if avg_keeper_cost is None else round(float(avg_keeper_cost), 1),
                "top_position_bias": ", ".join(
                    f"{pos} {ratio:.2f}x" for pos, ratio in aggression_by_pos.head(3).items()
                ),
                "position_shares": {k: round(float(v), 3) for k, v in pos_share.items()},
            }
        )

    return pd.DataFrame(profiles).sort_values("manager_name").reset_index(drop=True)


def format_profile_text(row: pd.Series) -> str:
    lines = [
        f"{row['manager_name']} "
        f"({row['num_seasons']} seasons, {row['num_picks']} picks, ${row['total_spend']:.0f} total spend)"
    ]

    if row["top_position_bias"]:
        lines.append(
            f"  Position bias: {row['top_position_bias']} "
            f"(spend share at that position vs league average that year)"
        )

    if row["pace_index"] >= 1.1:
        pace = "front-loads more than the league norm"
    elif row["pace_index"] <= 0.9:
        pace = "back-loads more than the league norm"
    else:
        pace = "paces spending about like everyone else"
    lines.append(
        f"  Spending pace: {pace} "
        f"({row['pct_budget_early']*100:.0f}% of budget gone by the draft's halfway point, "
        f"{row['pace_index']:.2f}x the league's own average pace that year)"
    )

    if row["shape_index"] >= 1.1:
        shape = "more stars-and-scrubs than the league norm"
    elif row["shape_index"] <= 0.9:
        shape = "more balanced than the league norm"
    else:
        shape = "about as balanced as everyone else"
    lines.append(
        f"  Roster shape: {shape} (single biggest pick = {row['top_pick_share']*100:.0f}% of total spend, "
        f"{row['shape_index']:.2f}x the league's own concentration that year)"
    )

    if row["num_seasons"] >= 2:
        keeper_line = f"  Keepers: keeps {row['keeper_rate']*100:.0f}% of roster spots"
        if pd.notna(row["avg_keeper_cost"]):
            keeper_line += f", avg ${row['avg_keeper_cost']:.0f}"
        lines.append(keeper_line)

    return "\n".join(lines)
