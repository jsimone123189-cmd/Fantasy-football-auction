# Rivals FCL -- Season Mode File Layout (2026)

The draft is over (304/304 picks, 19 rounds, 16 teams). Scored season is
Weeks 4-12 only, Weeks 9-12 weighted 1.5x. $500 FAAB per team for the season.
Your team is "Calculated chaos".

These files are the durable, git-tracked record for the season. Nothing here
auto-updates from Fantrax -- there's no live API access, so every file below
gets updated by hand (by Claude, prompted by the user) as real events happen.
Treat these as the source of truth between conversations, the same way the
draft-era `data/rivals/2026.csv` was for the draft itself.

- `draft_results_2026.csv` -- the real, final 304-pick draft log (pick,
  round, team, player, pos). This is also the roster-ownership record: to
  find who owns a player, look them up here. Static -- the draft is over,
  this file doesn't change unless a real add/drop needs reflecting (see
  below).
- `available_pool_2026.csv` -- every player in `2026.csv` NOT in
  `draft_results_2026.csv`, i.e., the real waiver-wire pool, sorted by the
  model's overall_rank. Update this (remove the player) whenever a real
  waiver claim or free-agent add happens; add a player back to it if
  someone gets dropped.
- `faab_2026.csv` -- one row per team, `faab_total`/`faab_spent`/
  `faab_remaining` (each starts at $500). Update `faab_spent` and
  `faab_remaining` whenever the user reports a real winning FAAB bid
  (theirs or an observed one worth tracking).
- `weekly_scores_2026.csv` -- long-format log, one row per (week,
  player_name) once real games start scoring (Week 4+): `week,
  player_name, team_owner, position, points, note`. Populate this by
  looking up real box scores and scoring them under this league's real
  rules (`draft_helper/rivals/model.py`'s scoring functions) when the user
  asks about a given week, or asks for a waiver-wire scan. This is what
  "log scores for waiver decisions" means in practice -- it's not automatic,
  it happens each time the user checks in.
- `draft_grades_2026.md` -- the full draft postmortem/grades, frozen as of
  the end of the draft. Doesn't get overwritten during the season; season
  performance gets tracked in the files above instead.

## When a real waiver move happens

1. Remove the added player's row from `available_pool_2026.csv`, add a row
   to `draft_results_2026.csv` for them (pick/round can be blank or "FA",
   team = the claiming team).
2. Add the dropped player (if any) back into `available_pool_2026.csv`.
3. Update the claiming team's `faab_spent`/`faab_remaining` in
   `faab_2026.csv`.

## Lineup decisions

There's no separate file for these -- they're a point-in-time question
(who should start this week), answered live using `draft_results_2026.csv`
for the roster, real current injury/role news, and this league's actual
scoring rules. Nothing to log ahead of time; just be ready to search real
injury reports and matchups when the user asks, starting Week 4.
