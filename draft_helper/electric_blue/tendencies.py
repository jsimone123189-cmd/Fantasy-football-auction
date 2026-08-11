"""Real, empirical draft tendencies from Electric Blue's own 7-season
history (2019-2025) -- no external projections needed, same philosophy as
Top Teamz's tendencies.py: judge behavior against the league's own real
patterns, not a generic benchmark.

Position-mix tendencies (who reaches for RBs, etc.) aren't computed here --
there's no reliable historical position database for ~600 unique player
names spanning 7 draft classes without either fabricating positions or a
large new research pass, so this deliberately stays to what's honestly
answerable from pick/round/player-repeat data alone.
"""
from __future__ import annotations

import pandas as pd

NFL_TEAMS = {
    "49ers", "Bears", "Bengals", "Bills", "Broncos", "Browns", "Buccaneers", "Cardinals",
    "Chargers", "Chiefs", "Colts", "Cowboys", "Dolphins", "Eagles", "Falcons", "Giants",
    "Jaguars", "Jets", "Lions", "Packers", "Panthers", "Patriots", "Raiders", "Rams",
    "Ravens", "Saints", "Seahawks", "Steelers", "Texans", "Titans", "Vikings", "Commanders",
}

# The four managers whose team name was identical (and therefore confidently
# resolved) in every single one of the 7 captured seasons -- see dename.py.
STABLE_MANAGERS = {
    "Ron Mexico's Perro": "Dan Thompson",
    "By The Beard of Zeus": "Jamison",
    "Surrender Your Booty": "Scott",
    "Password Is Taco": "Dave",
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


def stable_manager_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """For the 4 confidently-identified long-tenured managers: seasons
    active, average draft slot used, and repeat players (drafted the same
    real player in 2+ different seasons -- a real keeper/preference signal,
    not inferred).
    """
    rows = []
    for team_name, manager in STABLE_MANAGERS.items():
        g = df[df["team_name"] == team_name]
        if g.empty:
            continue
        seasons = sorted(g["season"].unique().tolist())
        repeats = (
            g.groupby("player_name")["season"].nunique()
            .loc[lambda s: s > 1]
            .sort_values(ascending=False)
        )
        rows.append({
            "team_name": team_name,
            "manager": manager,
            "seasons_active": len(seasons),
            "season_range": f"{min(seasons)}-{max(seasons)}",
            "avg_overall_pick": round(g["overall_pick"].mean(), 1),
            "repeat_players": ", ".join(f"{name} ({n}x)" for name, n in repeats.head(5).items()),
        })
    return pd.DataFrame(rows)
