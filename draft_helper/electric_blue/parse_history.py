"""Parses Electric Blue's raw pasted Yahoo Draft Results page text
(`data/electric_blue/raw_paste/{season}.txt`) into structured per-pick CSVs
-- Electric Blue has no API access (Yahoo blocks both the developer-app
route, which needs an approval the league doesn't have, and cookie-reuse via
curl, which Yahoo's bot detection rejects outright). The actual data came
from the user manually visiting each season's Draft Results page in their
real logged-in browser and pasting the rendered text, one season at a time.

Each raw file is a sequence of "Round N" headers followed by pick lines:
    1.    Player Name    Team Name...
(Yahoo's UI truncates long team names with "..." -- see `dename.py` for how
those get resolved to full names via the captured manager roster.)

Run as: python -m draft_helper.electric_blue.parse_history
"""
from __future__ import annotations

import os
import re

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE_DIR, "data", "electric_blue", "raw_paste")
OUT_DIR = os.path.join(BASE_DIR, "data", "electric_blue")

ROUND_RE = re.compile(r"^Round\s+(\d+)\s*$")
# Pick line: "<pick#>.    <player name>    <team name>" -- fields are
# separated by runs of 2+ spaces (player/team names only ever have single
# internal spaces, so this split is unambiguous).
PICK_RE = re.compile(r"^(\d+)\.\s{2,}(.+?)\s{2,}(.+?)\s*$")
NUM_TEAMS = 12


def parse_file(path: str, season: int) -> list[dict]:
    rows = []
    current_round = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if line.startswith("league_id:"):
                continue
            m = ROUND_RE.match(line)
            if m:
                current_round = int(m.group(1))
                continue
            m = PICK_RE.match(line)
            if m and current_round is not None:
                pick_in_round = int(m.group(1))
                player_name = m.group(2).strip()
                team_name = m.group(3).strip()
                overall_pick = (current_round - 1) * NUM_TEAMS + pick_in_round
                rows.append({
                    "season": season,
                    "round": current_round,
                    "pick_in_round": pick_in_round,
                    "overall_pick": overall_pick,
                    "player_name": player_name,
                    "team_name_raw": team_name,
                })
    return rows


def build() -> pd.DataFrame:
    all_rows = []
    if not os.path.isdir(RAW_DIR):
        return pd.DataFrame()
    for fname in sorted(os.listdir(RAW_DIR)):
        if not fname.endswith(".txt"):
            continue
        season = int(fname.replace(".txt", ""))
        path = os.path.join(RAW_DIR, fname)
        all_rows.extend(parse_file(path, season))
    return pd.DataFrame(all_rows)


def main():
    out = build()
    out_path = os.path.join(OUT_DIR, "draft_history_raw.csv")
    out.to_csv(out_path, index=False)
    by_season = out.groupby("season").size() if not out.empty else {}
    print(f"Wrote {len(out)} picks across {out['season'].nunique() if not out.empty else 0} seasons to {out_path}")
    for season, n in by_season.items():
        print(f"  {season}: {n} picks ({n // NUM_TEAMS} rounds)")


if __name__ == "__main__":
    main()
