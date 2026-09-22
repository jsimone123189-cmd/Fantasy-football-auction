# Electric Blue -- Season Mode File Layout (2026)

12-team snake, half-PPR keeper league, full season (Weeks 1-17/18, no
delayed-scoring window like Rivals). $100 season FAAB per team, "FAB w/
Continual rolling list tiebreak" (confirmed from the real Yahoo settings
page, `research/settings_172092.txt`). No kicker for 2026 -- confirmed
live during the draft, no K roster slot or scoring.

Same convention as `data/rivals/SEASON_MODE_README.md`: nothing here
auto-updates from Yahoo, there's no live API access. Every file gets
updated by hand (by Claude, prompted by the user) as real events happen.

- `draft_log_2026.csv` -- the real, completed 2026 draft (168 picks,
  already existed before season mode was set up). This is also the
  roster-ownership record: to find who owns a player, look them up here.
  `is_keeper` flags real keeper selections.
- `available_pool_2026.csv` -- every player in `2026.csv` NOT in
  `draft_log_2026.csv`, i.e., the real waiver-wire pool, sorted by the
  model's overall_rank (130 players as of the 2026 draft). Update this
  (remove the player) whenever a real waiver claim or free-agent add
  happens; add a player back if someone gets dropped.
- `faab_2026.csv` -- one row per team, `faab_total`/`faab_spent`/
  `faab_remaining` (each starts at $100). Update whenever the user
  reports a real winning FAAB bid.
- `weekly_scores_2026.csv` -- long-format log, one row per (week,
  player_name) once real games start scoring: `week, player_name,
  team_owner, position, points, note`. Populated on request using real
  box scores scored under `draft_helper/electric_blue/scoring.py`'s real
  rules -- not automatic.

  **Weeks 1-2 (2026) sourcing note**: the Yahoo Fantasy Sports API is
  currently blocked account-wide (Yahoo pulled self-serve API access
  clean off in July 2026; an access request is in with Yahoo's new
  manual-review program, ETA 1-2 weeks). Weeks 1-2 were instead computed
  from real per-play box score data pulled directly from ESPN's public
  scoreboard/summary API (passing/rushing/receiving/fumbles/return stats
  + team defensive stats), scored under this file's exact rules above
  (including deterministic per-game yardage milestone bonuses -- not the
  probabilistic season-projection version in `scoring.py`). A handful of
  rostered players had zero stat line or no game appearance at all in
  both weeks (flagged in the `note` column) -- that's a real signal
  (inactive/injured/off-roster), not a lookup failure, but isn't
  independently confirmed against news; verify before treating as fact.
  Once Yahoo access is approved, prefer official Yahoo box scores for any
  future week over this ESPN-sourced method.

## Which team is "you"

**Daejon Love the Game** (manager: justin s, per `research/managers_by_season.csv`).
Flagged as `is_you=True` in `faab_2026.csv`.

## When a real waiver move happens

1. Remove the added player's row from `available_pool_2026.csv`, add a row
   to `draft_log_2026.csv` for them (pick can be blank or "FA", team_name
   = the claiming team, is_keeper = False).
2. Add the dropped player (if any) back into `available_pool_2026.csv`.
3. Update the claiming team's `faab_spent`/`faab_remaining` in
   `faab_2026.csv`.
