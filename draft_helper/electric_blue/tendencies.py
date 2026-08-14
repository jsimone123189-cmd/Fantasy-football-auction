"""Real, empirical draft tendencies from Electric Blue's own 7-season
history (2019-2025) plus the current 2026 roster, now covering every
manager (not just the 4 who happened to keep the same team name every
year) -- see dename.py, which resolves each season's real team-name/
manager roster (captured from the user's own Yahoo "Managers" page
screenshots) instead of guessing from name repetition.

Position-mix tendencies (who reaches for RBs, etc.) still aren't computed
here -- there's no reliable historical position database for ~600 unique
player names spanning 7 draft classes without either fabricating positions
or a large new research pass, so this deliberately stays to what's
honestly answerable from pick/round/player-repeat data alone.

Reach detection doesn't need external ADP to be honest, though: for any
player drafted more than once across this league's own history, comparing
one manager's specific pick round against the *other* instances of that
same player (leave-one-out, so a pick never inflates its own baseline)
gives a real, self-consistent "did this manager draft him earlier than
this league typically has" signal -- no fabricated external ranking
required.
"""
from __future__ import annotations

import pandas as pd

NFL_TEAMS = {
    "49ers", "Bears", "Bengals", "Bills", "Broncos", "Browns", "Buccaneers", "Cardinals",
    "Chargers", "Chiefs", "Colts", "Cowboys", "Dolphins", "Eagles", "Falcons", "Giants",
    "Jaguars", "Jets", "Lions", "Packers", "Panthers", "Patriots", "Raiders", "Rams",
    "Ravens", "Saints", "Seahawks", "Steelers", "Texans", "Titans", "Vikings", "Commanders",
}


def def_and_kicker_draft_rounds(df: pd.DataFrame) -> dict:
    """Real historical avg draft round for DEF (whole-team picks) and K --
    used to sanity-check the 2026 VOR ranking, which doesn't know that real
    managers in this exact league have never drafted either early."""
    def_rows = df[df["player_name"].isin(NFL_TEAMS)]
    kicker_pattern = (
        r"Tucker|Butker|Lutz|Prater|Gould|Zuerlein|Badgley|Gostkowski|Fairbairn|Elliott$"
    )
    k_rows = df[df["player_name"].str.contains(kicker_pattern, regex=True, na=False)
                & ~df["player_name"].isin(NFL_TEAMS)
                & ~df["player_name"].str.contains("Ezekiel|Sean Tucker", regex=True, na=False)]
    return {
        "def_avg_round": round(def_rows["round"].mean(), 1) if not def_rows.empty else None,
        "def_n_picks": len(def_rows),
        "def_earliest_round": int(def_rows["round"].min()) if not def_rows.empty else None,
        "kicker_avg_round": round(k_rows["round"].mean(), 1) if not k_rows.empty else None,
        "kicker_n_picks": len(k_rows),
        "kicker_earliest_round": int(k_rows["round"].min()) if not k_rows.empty else None,
    }


def manager_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """One row per real manager (df must already have a `manager` column,
    e.g. from dename.apply()): seasons active, average draft slot, and a
    repeat-player rate (how often they draft someone they'd already
    rostered in an earlier EB season) -- a real signal, but a minor one;
    the reach index below is the more actionable one.
    """
    rows = []
    for manager, g in df.groupby("manager"):
        if pd.isna(manager):
            continue
        seasons = sorted(g["season"].unique().tolist())
        own_repeats = (
            g.groupby("player_name")["season"].nunique()
            .loc[lambda s: s > 1]
            .sort_values(ascending=False)
        )
        rows.append({
            "manager": manager,
            "seasons_active": len(seasons),
            "season_range": f"{min(seasons)}-{max(seasons)}" if seasons else "",
            "num_picks": len(g),
            "avg_overall_pick": round(g["overall_pick"].mean(), 1),
            "own_repeat_players": ", ".join(f"{name} ({n}x)" for name, n in own_repeats.head(5).items()),
            "own_repeat_rate": round(len(g[g["player_name"].isin(own_repeats.index)]) / len(g), 3) if len(g) else 0.0,
        })
    return pd.DataFrame(rows).sort_values("manager").reset_index(drop=True)


def reach_index(df: pd.DataFrame, min_appearances: int = 2) -> pd.DataFrame:
    """For every player drafted `min_appearances`+ times across this
    league's real history, compares each specific pick's round against the
    *other* instances of that same player (leave-one-out mean, so a pick
    never inflates its own baseline). Positive reach_rounds = this manager
    took that player earlier (a real reach relative to how this league has
    valued him in other years); negative = got him at a discount.

    Returns one row per (manager, player, season) instance with its reach,
    plus per-manager aggregates via `reach_summary()`.
    """
    counts = df.groupby("player_name")["round"].transform("count")
    repeat_df = df[counts >= min_appearances].copy()
    if repeat_df.empty:
        return pd.DataFrame(columns=["manager", "player_name", "season", "round", "field_avg_round", "reach_rounds"])

    total_round = repeat_df.groupby("player_name")["round"].transform("sum")
    n = repeat_df.groupby("player_name")["round"].transform("count")
    # leave-one-out mean of every *other* instance's round
    repeat_df["field_avg_round"] = (total_round - repeat_df["round"]) / (n - 1)
    repeat_df["reach_rounds"] = (repeat_df["field_avg_round"] - repeat_df["round"]).round(2)

    return repeat_df[["manager", "player_name", "season", "round", "field_avg_round", "reach_rounds"]].sort_values(
        "reach_rounds", ascending=False
    ).reset_index(drop=True)


def reach_summary(reach_df: pd.DataFrame, min_instances: int = 3) -> pd.DataFrame:
    """Per-manager reach index: average reach_rounds across all their
    repeat-drafted-player instances, plus their single biggest reach and
    biggest discount for a concrete, checkable example.
    """
    rows = []
    for manager, g in reach_df.groupby("manager"):
        if pd.isna(manager) or len(g) < min_instances:
            continue
        biggest_reach = g.loc[g["reach_rounds"].idxmax()]
        biggest_discount = g.loc[g["reach_rounds"].idxmin()]
        rows.append({
            "manager": manager,
            "n_instances": len(g),
            "avg_reach_rounds": round(g["reach_rounds"].mean(), 2),
            "biggest_reach": f"{biggest_reach['player_name']} ({int(biggest_reach['season'])}, "
                              f"rd {int(biggest_reach['round'])} vs. field avg rd "
                              f"{biggest_reach['field_avg_round']:.1f})",
            "biggest_discount": f"{biggest_discount['player_name']} ({int(biggest_discount['season'])}, "
                                 f"rd {int(biggest_discount['round'])} vs. field avg rd "
                                 f"{biggest_discount['field_avg_round']:.1f})",
        })
    return pd.DataFrame(rows).sort_values("avg_reach_rounds", ascending=False).reset_index(drop=True)
