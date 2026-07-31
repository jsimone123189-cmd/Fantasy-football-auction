"""Pre-draft cheat sheet: this year's players priced against your league's
own historical position/rank cost curve.

Needs a projections file you supply for the upcoming season — Yahoo's
historical draft data alone can't tell you this year's rookies or which
veterans changed teams. See data/projections/README or --help for the
expected CSV format.
"""
from __future__ import annotations

import pandas as pd

from .inflation import baseline_value


REQUIRED_COLUMNS = {"player_name", "position"}


def load_projections(path: str) -> pd.DataFrame:
    proj = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(proj.columns)
    if missing:
        raise ValueError(f"Projections file is missing required column(s): {sorted(missing)}")
    if "projected_rank" not in proj.columns:
        if "projected_points" not in proj.columns:
            raise ValueError(
                "Projections file needs either a 'projected_rank' column (1 = best "
                "at that position) or a 'projected_points' column to derive rank from."
            )
        proj["projected_rank"] = proj.groupby("position")["projected_points"].rank(
            ascending=False, method="first"
        )
    return proj


def generate_cheat_sheet(
    projections: pd.DataFrame,
    curve: pd.DataFrame,
    num_teams: int,
    budget_per_team: float,
    keeper_costs: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """keeper_costs: optional DataFrame with player_name, cost, team_name for
    players already locked in as keepers this year — removed from the pool
    and their $ removed from the effective auction budget before pricing
    everyone else.
    """
    total_budget = num_teams * budget_per_team
    kept_names = set()
    if keeper_costs is not None and not keeper_costs.empty:
        kept_names = set(keeper_costs["player_name"])
        total_budget -= pd.to_numeric(keeper_costs["cost"], errors="coerce").fillna(0).sum()

    proj = projections[~projections["player_name"].isin(kept_names)].copy()
    proj["target_price"] = proj.apply(
        lambda r: baseline_value(curve, r["position"], int(r["projected_rank"]), total_budget),
        axis=1,
    )
    return proj.sort_values("target_price", ascending=False).reset_index(drop=True)
