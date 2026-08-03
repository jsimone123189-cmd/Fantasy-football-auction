"""Team-level environment layer (spec Step 3: Team Environment, Step 4:
Betting Markets, Step 6: Game Script).

Loads `data/research/team_context_2026.csv` (Vegas win totals, O-line tier,
scheme tendency, pace, coaching changes -- gathered by web research, see
that file's header for provenance) and turns it into a small set of
explainable multipliers that get applied to every player on that team:

- `scoring_mult`: team's implied points/game vs. league average. Drives raw
  TD equity and overall offensive ceiling for everyone on the roster.
- `run_funnel_mult` / `pass_funnel_mult`: scheme tendency + O-line tier,
  applied to RB volume/efficiency and to WR/TE/QB pass volume respectively.
- `rb_gamescript_mult` / `pass_gamescript_mult`: derived from win total
  relative to league average. Good teams (positive game script) run more
  and protect leads -> more RB volume, run out the clock late. Bad teams
  (negative game script) throw more while trailing -> more pass volume,
  but with less efficient (garbage-time, lower-leverage) production.

Every multiplier is deliberately mild (roughly 0.85x-1.15x) -- team context
should tilt a projection, not dominate it. A team with no research row falls
back to league-average neutral values (all multipliers 1.0) rather than
guessing.
"""
from __future__ import annotations

import os

import pandas as pd

OL_TIER_MULT = {
    "elite": 1.06,
    "good": 1.02,
    "average": 1.00,
    "below-average": 0.96,
    "poor": 0.90,
}

SCHEME_RUN_MULT = {
    "run-funnel": 1.08,
    "run-heavy": 1.08,
    "balanced": 1.00,
    "pass-funnel": 0.93,
    "pass-heavy": 0.93,
}

SCHEME_PASS_MULT = {
    "run-funnel": 0.93,
    "run-heavy": 0.93,
    "balanced": 1.00,
    "pass-funnel": 1.08,
    "pass-heavy": 1.08,
}

PACE_MULT = {
    "fast": 1.05,
    "average": 1.00,
    "slow": 0.95,
}

DEFAULT_WIN_TOTAL = 8.5
DEFAULT_IMPLIED_PPG = 21.5


class TeamContext:
    def __init__(self, row: pd.Series | None, league_avg_implied_ppg: float):
        self.row = row
        self.league_avg_implied_ppg = league_avg_implied_ppg
        if row is None:
            self.win_total = DEFAULT_WIN_TOTAL
            self.implied_ppg = league_avg_implied_ppg
            self.ol_tier = "average"
            self.scheme = "balanced"
            self.pace = "average"
            self.new_hc_or_oc = ""
            self.qb_change = ""
            self.starting_qb = ""
            self.redzone_note = ""
            self.key_personnel_changes = ""
            self.division_odds = ""
            self.sb_odds = ""
        else:
            self.win_total = _to_float(row.get("win_total"), DEFAULT_WIN_TOTAL)
            self.implied_ppg = _to_float(row.get("implied_ppg"), league_avg_implied_ppg)
            self.ol_tier = str(row.get("ol_tier") or "average").strip().lower()
            self.scheme = str(row.get("scheme_tendency") or "balanced").strip().lower()
            self.pace = str(row.get("pace_tier") or "average").strip().lower()
            self.new_hc_or_oc = str(row.get("new_hc_or_oc") or "").strip()
            self.qb_change = str(row.get("qb_change") or "").strip()
            self.starting_qb = str(row.get("starting_qb_2026") or "").strip()
            self.redzone_note = str(row.get("redzone_note") or "").strip()
            self.key_personnel_changes = str(row.get("key_personnel_changes") or "").strip()
            self.division_odds = str(row.get("division_odds") or "").strip()
            self.sb_odds = str(row.get("sb_odds") or "").strip()

    @property
    def scoring_mult(self) -> float:
        if self.league_avg_implied_ppg <= 0:
            return 1.0
        return self.implied_ppg / self.league_avg_implied_ppg

    @property
    def ol_mult(self) -> float:
        return OL_TIER_MULT.get(self.ol_tier, 1.0)

    @property
    def scheme_run_mult(self) -> float:
        return SCHEME_RUN_MULT.get(self.scheme, 1.0)

    @property
    def scheme_pass_mult(self) -> float:
        return SCHEME_PASS_MULT.get(self.scheme, 1.0)

    @property
    def pace_mult(self) -> float:
        return PACE_MULT.get(self.pace, 1.0)

    @property
    def run_funnel_mult(self) -> float:
        """Combined scheme+O-line effect on RB rush *volume*."""
        return self.scheme_run_mult * self.ol_mult

    @property
    def pass_funnel_mult(self) -> float:
        """Combined scheme+pace effect on pass-game *volume* (targets/attempts)."""
        return self.scheme_pass_mult * self.pace_mult

    @property
    def rb_gamescript_mult(self) -> float:
        # +/- 2% per win above/below league-average win total, capped at +/-10%.
        delta = self.win_total - DEFAULT_WIN_TOTAL
        return _clamp(1.0 + 0.02 * delta, 0.90, 1.10)

    @property
    def pass_gamescript_mult(self) -> float:
        # Trailing teams throw more (garbage-time volume); winning teams protect
        # leads and run the ball out. Weaker effect than the RB side since a
        # lot of "trailing volume" is lower-value garbage time, not efficiency.
        delta = self.win_total - DEFAULT_WIN_TOTAL
        return _clamp(1.0 - 0.01 * delta, 0.94, 1.06)

    def env_summary(self) -> str:
        parts = [f"{self.implied_ppg:.1f} implied pts/g"]
        if self.scoring_mult >= 1.05:
            parts.append("top-tier offense")
        elif self.scoring_mult <= 0.92:
            parts.append("bottom-tier offense")
        parts.append(f"{self.ol_tier} O-line")
        parts.append(f"{self.scheme} scheme")
        if self.new_hc_or_oc and self.new_hc_or_oc.lower() not in ("no", "none", "nan", ""):
            parts.append(f"new coaching: {self.new_hc_or_oc}")
        if self.qb_change and self.qb_change.lower() not in ("no", "none", "nan", ""):
            parts.append(f"QB change: {self.qb_change}")
        return "; ".join(parts)


def _to_float(val, default: float) -> float:
    try:
        f = float(val)
        if pd.isna(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def load_team_contexts(path: str = "data/research/team_context_2026.csv") -> dict[str, TeamContext]:
    """Returns {team_name: TeamContext}. Falls back to all-neutral contexts
    (built via a single default TeamContext(None, ...)) if the research file
    isn't present yet -- lets the rest of the pipeline run before research
    lands, at the cost of zeroing out the team-environment adjustment.
    """
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    league_avg = _to_float(df["implied_ppg"].astype(float).mean() if "implied_ppg" in df else None, DEFAULT_IMPLIED_PPG)
    contexts = {}
    for _, row in df.iterrows():
        team = str(row.get("team", "")).strip()
        if team:
            contexts[team] = TeamContext(row, league_avg)
    return contexts


def get_context(contexts: dict[str, "TeamContext"], team: str, league_avg_implied_ppg: float = DEFAULT_IMPLIED_PPG) -> TeamContext:
    if team in contexts:
        return contexts[team]
    return TeamContext(None, league_avg_implied_ppg)
