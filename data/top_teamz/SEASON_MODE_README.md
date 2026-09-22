# Top Teamz -- Season Mode File Layout (2026)

12-team auction ($200 draft budget), 0.5 PPR, full season (Weeks 1-17/18,
no delayed-scoring window like Rivals). $100 season FAAB per team plus
numbered waiver priority (1-12). Your team is **Maserati Marv**
(manager "justin s" -- explicitly marked "(you)" in the prior
`season_companion_2026.html`).

Same convention as the other two leagues: nothing here auto-updates from
Yahoo, there's no live API access. Every file gets updated by hand (by
Claude, prompted by the user) as real events happen. This is the first
time Top Teamz's season state has structured CSV backing -- previously it
only existed as hand-written prose/HTML inside `season_companion_2026.html`
(draft-night rosters, grades, and a manual moves log). That HTML file still
has the full draft-grade writeups; these CSVs are the operational layer for
ongoing season/waiver work.

- `auction_results_2026.csv` -- the real, historical auction result (168
  picks, price paid per player). Reconstructed from `season_companion_
  2026.html` by reversing the 3 logged season moves back out, then
  verified: every team's reconstructed total spend matches that team's
  real "$ spent" stat on its draft-grade card exactly. **Static** -- this
  never changes, it's the draft-night record.
- `draft_results_2026.csv` -- **current roster ownership**, derived from
  `auction_results_2026.csv` with the 3 logged moves applied (the real
  trade + 2 waiver adds, see below). This is the file to check for "who
  owns this player right now." Update this whenever a new real move
  happens, same as the Rivals/Electric Blue convention.
- `available_pool_2026.csv` -- every player in the shared skill-position
  pool (`data/projections/2026.csv`) plus real team defenses, minus
  everyone in `draft_results_2026.csv` (current ownership, not auction
  night) -- 138 players as of the 3 known moves. Sorted by
  `projected_rank`. IDP/kicker are not part of this league's ruleset
  (0.5 PPR, no K/IDP slots), so this pool is skill positions + DEF only.
- `faab_2026.csv` -- one row per team: `faab_total` (100, confirmed),
  `faab_spent`/`faab_remaining`, `waiver_priority` (1-12, from the
  season-companion doc), `is_you`. **Caveat: faab_spent/remaining are
  inferred, not directly stated anywhere in the source.** The HTML only
  ever states the $100 budget "as of draft night." The $1 shown for Bye
  Week and Tee Time came from the $1 price_paid on their two waiver-add
  players in the roster tables, not a stated bid amount -- treat these two
  numbers as a reasonable guess, not confirmed fact, until the user
  verifies the real FAAB ledger.
- `moves_log_2026.csv` -- the 3 real season moves captured in the prior
  HTML doc: a trade (Maserati Marv <-> Bye Week, TreVeyon Henderson
  for Jayden Daniels) and 2 waiver adds (Bye Week added Ravens D/ST, Tee
  Time dropped Kenyon Sadiq for Kaleb Johnson). Add a new row here for
  every future move, in addition to updating `draft_results_2026.csv` and
  `faab_2026.csv`.
- `weekly_scores_2026.csv` -- long-format log, one row per (week,
  player_name) once real games start scoring: `week, player_name,
  team_owner, position, points, note`. Populated on request using real
  box scores scored under `draft_helper/projections/scoring.py`'s real
  rules -- not automatic.

  **Weeks 1-2 (2026) sourcing note**: the Yahoo Fantasy Sports API is
  currently blocked account-wide (Yahoo pulled self-serve API access
  clean off in July 2026; an access request is in with Yahoo's new
  manual-review program, ETA 1-2 weeks). Weeks 1-2 were instead computed
  from real per-play box score data pulled directly from ESPN's public
  scoreboard/summary API (passing/rushing/receiving/fumbles/return stats
  + team defensive stats: sacks/INT/fumble-rec/def-TD from
  `draft_helper/projections/def_model.py`'s confirmed points-/yards-
  allowed tiers), scored with deterministic per-game yardage milestone
  bonuses (not the probabilistic season-projection version in
  `scoring.py`). A handful of rostered players had zero stat line or no
  game appearance at all in both weeks (flagged in the `note` column) --
  that's a real signal (inactive/injured/off-roster), not a lookup
  failure, but isn't independently confirmed against news; verify before
  treating as fact. Once Yahoo access is approved, prefer official Yahoo
  box scores for any future week over this ESPN-sourced method.

## Known open gap: Bye Week's roster is 15 players, not 14

`draft_results_2026.csv` currently has Bye Week at 15 rostered players
after the Ravens D/ST add, because the source moves-log text never named a
corresponding drop for that pickup. Either a drop happened and wasn't
recorded in the text we extracted, or Bye Week is genuinely carrying an
extra roster spot for some other real reason. **Don't treat Bye Week's
15th player as settled fact** -- confirm the real drop (if any) next time
this comes up, and fix `draft_results_2026.csv`/`available_pool_2026.csv`
accordingly.

## Two other data caveats worth knowing

- Real NFL teams for skill-position players were backfilled from
  `data/projections/2026.csv` by name match (the source HTML never states
  a skill player's NFL team anywhere) -- two name-variant mismatches
  (Kenny Gainwell -> Kenneth Gainwell/Buccaneers, Jordy Tyson -> Jordyn
  Tyson/Saints) were fixed by hand.
- Kenyon Sadiq's position/team were unrecoverable from the moves-log
  prose alone (he's named only as the player Tee Time dropped) -- pulled
  from `data/projections/2026.csv` instead (TE, Jets).

## When a real waiver move or trade happens

1. Update `draft_results_2026.csv` (change team, or add/remove rows).
2. Update `available_pool_2026.csv` to match (remove the add, add back any
   real drop).
3. Update the moving team's `faab_spent`/`faab_remaining` in
   `faab_2026.csv` if it was a FAAB move.
4. Add a row to `moves_log_2026.csv`.
