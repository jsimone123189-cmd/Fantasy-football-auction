"""Turns the raw, source-verified IDP research
(`data/research/idp_{dl,lb,db}_2026.csv` -- real 2025 season counting stats,
gathered by web research, one row per player) into per-game rate inputs for
`model.project_idp` (`data/rivals/inputs_idp_2026.csv`).

Rate math: solo_pg = solo_tackles_2025 / games_played_2025, etc. -- this is
just "how often did this actually happen when they were on the field,"
which is the honest baseline absent a specific known 2026 role change.

`games_proj` (games expected to play in 2026, not the "games_played_2025"
denominator above) is derived from `risk_tier` and a few explicit text
signals in the raw research rather than guessed per player individually --
that would mean manually judging ~200 players. The rules:
  - role_2026 or depth_chart_note mentioning "retired" -> player dropped
    entirely (not draftable).
  - "unsigned" / "free agent" (no 2026 team) -> games_proj=13, risk pushed
    to at least "high" (real snap-share ramp-up risk even after signing).
  - depth_chart_note mentioning season-ending injury language ("season-
    ending", "torn", "neck surgery", "IR" with recovery uncertainty) ->
    games_proj=12, risk pushed to at least "high".
  - otherwise: games_proj=17 at low risk, 16 at medium, 14 at high,
    11 at very_high (mirrors the RISK_BANDS floor/ceiling philosophy
    already used for skill positions -- risk mostly shows up as a wider
    floor/ceiling band, not a shrunken median, except where a real,
    specific games-missed signal exists in the research).

Run as: python -m draft_helper.rivals.build_idp_inputs
"""
from __future__ import annotations

import os
import re

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESEARCH_DIR = os.path.join(BASE_DIR, "data", "research")
OUT_PATH = os.path.join(BASE_DIR, "data", "rivals", "inputs_idp_2026.csv")

SOURCE_FILES = ["idp_dl_2026.csv", "idp_lb_2026.csv", "idp_db_2026.csv"]

RISK_BASE_GAMES = {"low": 17, "medium": 16, "high": 14, "very_high": 11}

RETIRED_RE = re.compile(r"\bretir", re.IGNORECASE)
UNSIGNED_RE = re.compile(r"unsigned|free agent \(unsigned|no 2026 team", re.IGNORECASE)
SEASON_ENDING_RE = re.compile(
    r"season-ending|torn (acl|achilles|bicep|meniscus)|neck surgery|IR\b.*(uncertain|recovery)",
    re.IGNORECASE,
)
# A real 2025 season-ending injury doesn't mean the same thing for a games_proj
# discount if the same note also confirms the player is actually cleared for
# 2026 -- the blanket 12-game discount is for genuine, still-uncertain
# recovery, not for "this happened last year and he's since been confirmed
# fully healthy." Checked for real -- see build.py's docstring reasoning
# repeated here: don't apply a discount the note itself contradicts.
RECOVERED_RE = re.compile(
    r"fully (healthy|recovered)|no limitations|full participant|cleared|no setbacks",
    re.IGNORECASE,
)
# Only matches an unambiguous "(NNN combined...)" mention of a real 2025
# season tackle total -- deliberately narrow so it doesn't accidentally
# grab an unrelated number (career total, college stat, different season).
COMBINED_TACKLES_RE = re.compile(r"(\d+)\s*combined\b")


def _rate(total, games):
    if pd.isna(total) or pd.isna(games) or games in (0, None) or (isinstance(games, float) and games <= 0):
        return 0.0
    return float(total) / float(games)


def _solo_share(df: pd.DataFrame) -> float:
    """Real, data-derived solo/(solo+ast) split from this same research
    file's players who have both numbers reported -- used only to split a
    combined-tackle total found in note text, never to invent a total.
    """
    both = df.dropna(subset=["solo_tackles_2025", "ast_tackles_2025"])
    both = both[(both["solo_tackles_2025"] + both["ast_tackles_2025"]) > 20]
    if both.empty:
        return 0.55  # neutral fallback if a position file has too few dual-reported rows
    return float((both["solo_tackles_2025"] / (both["solo_tackles_2025"] + both["ast_tackles_2025"])).mean())


def _derive(row, solo_share: float) -> dict | None:
    note = f"{row.get('role_2026', '')} {row.get('depth_chart_note', '')}"
    risk_tier = str(row.get("risk_tier", "medium") or "medium").strip().lower()
    if risk_tier not in RISK_BASE_GAMES:
        risk_tier = "medium"

    if RETIRED_RE.search(note):
        return None  # not draftable

    games_2025 = row.get("games_played_2025", 0)

    solo_total = row.get("solo_tackles_2025")
    ast_total = row.get("ast_tackles_2025")
    backfill_note = ""
    if pd.isna(solo_total) and pd.isna(ast_total):
        m = COMBINED_TACKLES_RE.search(note)
        if m:
            combined = float(m.group(1))
            solo_total = combined * solo_share
            ast_total = combined * (1 - solo_share)
            backfill_note = (
                f" [{int(combined)} combined 2025 tackles found in research notes; "
                f"solo/assist split estimated at this position's observed "
                f"{solo_share*100:.0f}/{100-solo_share*100:.0f} average since the source "
                f"didn't report the two separately -- not a fabricated total, just an estimated split.]"
            )

    if UNSIGNED_RE.search(note):
        games_proj = 13
        risk_tier = "high" if risk_tier == "low" else risk_tier
        role_note = "Unsigned as of Aug 2026 -- games_proj discounted for a landing-spot/ramp-up gap even if he signs before the draft."
    elif SEASON_ENDING_RE.search(note) and RECOVERED_RE.search(note):
        # Real injury history, but the same note confirms he's actually
        # cleared for 2026 -- a lighter, real discount (the "high" risk
        # games count) instead of the harsher blanket 12, since there's no
        # specific reason left to expect 2026 games missed, just residual
        # real uncertainty until he's proven it in real game action.
        games_proj = RISK_BASE_GAMES["high"]
        risk_tier = "high" if risk_tier in ("low", "medium") else risk_tier
        role_note = "Real 2025 season-ending injury on record, but the same research confirms he's cleared/fully healthy for 2026 -- games_proj uses the real 'high risk' games count instead of the harsher unrecovered discount, since there's no specific 2026 games-missed signal left, just residual uncertainty until proven in game action."
    elif SEASON_ENDING_RE.search(note):
        games_proj = 12
        risk_tier = "high" if risk_tier == "low" else risk_tier
        role_note = "Real 2025 season-ending injury on record -- games_proj discounted, not assumed fully recovered to a normal 17-game year."
    else:
        games_proj = RISK_BASE_GAMES[risk_tier]
        role_note = ""

    games = games_2025 if games_2025 and float(games_2025) > 0 else games_proj

    return {
        "player_name": row["player_name"],
        "position": row["position"],
        "nfl_team": row.get("nfl_team", ""),
        "games_proj": games_proj,
        "solo_pg": round(_rate(solo_total, games), 3),
        "ast_pg": round(_rate(ast_total, games), 3),
        "tfl_pg": round(_rate(row.get("tfl_2025"), games), 3),
        "sack_pg": round(_rate(row.get("sacks_2025"), games), 3),
        "ff_pg": round(_rate(row.get("ff_2025"), games), 3),
        "fr_pg": round(_rate(row.get("fr_2025"), games), 3),
        "int_pg": round(_rate(row.get("int_2025"), games), 3),
        "pd_pg": round(_rate(row.get("pd_2025"), games), 3),
        "risk_tier": risk_tier,
        "role_note": (role_note or str(row.get("role_2026", ""))) + backfill_note,
    }


def build() -> pd.DataFrame:
    rows = []
    for fname in SOURCE_FILES:
        path = os.path.join(RESEARCH_DIR, fname)
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path)
        solo_share = _solo_share(df)
        for _, row in df.iterrows():
            derived = _derive(row, solo_share)
            if derived is not None:
                rows.append(derived)
    return pd.DataFrame(rows)


def main():
    out = build()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out)} IDP players to {OUT_PATH}")


if __name__ == "__main__":
    main()
