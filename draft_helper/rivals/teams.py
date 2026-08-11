"""Normalizes NFL team names to the full nickname used in
`data/research/bye_weeks_2026.csv` and `data/research/team_context_2026.csv`
(e.g. "Bengals", "49ers", "Rams") -- the skill-position inputs already use
that convention, but the IDP/kicker research came back with standard
2-3 letter abbreviations (CIN, SF, LA/LAR), so both need to funnel through
this before a bye-week or team-context lookup.
"""
from __future__ import annotations

ABBR_TO_NICKNAME = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills",
    "CAR": "Panthers", "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns",
    "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GB": "Packers",
    "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "JAC": "Jaguars",
    "KC": "Chiefs", "LV": "Raiders", "LAC": "Chargers", "LA": "Rams",
    "LAR": "Rams", "MIA": "Dolphins", "MIN": "Vikings", "NE": "Patriots",
    "NO": "Saints", "NYG": "Giants", "NYJ": "Jets", "PHI": "Eagles",
    "PIT": "Steelers", "SF": "49ers", "SEA": "Seahawks", "TB": "Buccaneers",
    "TEN": "Titans", "WAS": "Commanders", "WSH": "Commanders",
}


IDP_POSITION_BUCKET = {
    # DL
    "DE": "DL", "DT": "DL", "EDGE": "DL", "NT": "DL", "DL": "DL",
    # LB
    "ILB": "LB", "MLB": "LB", "OLB": "LB", "WLB": "LB", "SLB": "LB", "LB": "LB",
    # DB
    "S": "DB", "FS": "DB", "SS": "DB", "CB": "DB", "DB": "DB", "S/CB": "DB",
}


def idp_bucket(position: str) -> str:
    """Fantrax scores DL/LB/DB as one category set each and rosters them
    as one slot each -- sub-positions (DE/DT/EDGE/NT, ILB/MLB/OLB, S/CB
    etc.) all collapse to their parent bucket for scoring/VOR/roster-slot
    purposes, even though the research keeps the specific sub-position for
    context in `explanation`.
    """
    if position is None:
        return ""
    return IDP_POSITION_BUCKET.get(str(position).strip().upper(), str(position).strip().upper())


def to_nickname(team: str) -> str:
    if team is None:
        return ""
    team = str(team).strip()
    if not team:
        return ""
    # Already a full nickname (skill-position inputs) or an unresolvable
    # free-text status ("Unsigned", "Retired", etc.) -- pass through as-is
    # rather than guessing.
    return ABBR_TO_NICKNAME.get(team.upper(), team)
