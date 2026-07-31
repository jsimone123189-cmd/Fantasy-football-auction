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
                "position_concentration_hhi": round(hhi, 3),
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

    if row["pct_budget_early"] >= 0.55:
        pace = "front-loads"
    elif row["pct_budget_early"] <= 0.45:
        pace = "back-loads"
    else:
        pace = "spends evenly across"
    lines.append(
        f"  Spending pace: {pace} the draft "
        f"({row['pct_budget_early']*100:.0f}% of budget gone by the draft's halfway point)"
    )

    shape = "stars-and-scrubs" if row["position_concentration_hhi"] >= 0.22 else "balanced roster builder"
    lines.append(
        f"  Roster shape: {shape} (single biggest pick = {row['top_pick_share']*100:.0f}% of total spend)"
    )

    if row["num_seasons"] >= 2:
        keeper_line = f"  Keepers: keeps {row['keeper_rate']*100:.0f}% of roster spots"
        if pd.notna(row["avg_keeper_cost"]):
            keeper_line += f", avg ${row['avg_keeper_cost']:.0f}"
        lines.append(keeper_line)

    return "\n".join(lines)
