"""Interactive live-draft assistant.

Run during your actual auction: log each pick as it happens and get a
running suggested max bid (historical baseline price x live inflation),
plus budget-cap warnings for opponents so you know who can't outbid you.
"""
from __future__ import annotations

import cmd
from dataclasses import dataclass, field

import pandas as pd
from tabulate import tabulate

from .analysis import tendencies as tendencies_mod
from .analysis.inflation import baseline_value, inflation_rate
from .analysis.roster_needs import DEFAULT_SLOTS, compute_needs, format_needs


@dataclass
class TeamState:
    name: str
    budget: float
    roster_spots: int
    spent: float = 0.0
    picks: list = field(default_factory=list)
    pick_positions: list = field(default_factory=list)

    @property
    def remaining_budget(self) -> float:
        return self.budget - self.spent

    @property
    def remaining_spots(self) -> int:
        return self.roster_spots - len(self.picks)

    @property
    def max_bid(self) -> float:
        # Must leave at least $1 for every other remaining roster spot.
        if self.remaining_spots <= 0:
            return 0.0
        return max(0.0, self.remaining_budget - (self.remaining_spots - 1))


class LiveDraftShell(cmd.Cmd):
    intro = "Live draft assistant. Type `help` for commands, `quit` to exit and save.\n"
    prompt = "draft> "

    def __init__(
        self,
        projections: pd.DataFrame,
        curve: pd.DataFrame,
        teams: list[str],
        budget_per_team: float,
        roster_size: int,
        tendency_profiles: pd.DataFrame | None = None,
        log_path: str = "draft_log.csv",
        starting_slots: dict | None = None,
    ):
        super().__init__()
        self.curve = curve
        self.budget_per_team = budget_per_team
        self.num_teams = len(teams)
        self.total_budget = self.num_teams * budget_per_team
        self.teams = {t: TeamState(t, budget_per_team, roster_size) for t in teams}
        self.tendency_profiles = tendency_profiles
        self.log_path = log_path
        self.log: list[dict] = []
        self.starting_slots = starting_slots or DEFAULT_SLOTS

        self.pool = projections.copy()
        self.pool["baseline_value"] = self.pool.apply(
            lambda r: baseline_value(curve, r["position"], int(r["projected_rank"]), self.total_budget),
            axis=1,
        )
        self.pool["drafted"] = False
        self.baseline_value_total = float(self.pool["baseline_value"].sum())
        self.baseline_value_drafted = 0.0
        self.dollars_spent = 0.0

    # -- helpers --------------------------------------------------------

    def _current_inflation(self) -> float:
        return inflation_rate(
            self.total_budget, self.dollars_spent, self.baseline_value_drafted, self.baseline_value_total
        )

    def _find_player(self, name: str) -> pd.DataFrame:
        name = name.strip().lower()
        matches = self.pool[self.pool["player_name"].str.lower() == name]
        if matches.empty:
            matches = self.pool[self.pool["player_name"].str.lower().str.contains(name, regex=False)]
        return matches

    # -- commands ---------------------------------------------------------

    def do_value(self, arg):
        "value <player name>: suggested max bid at current inflation."
        matches = self._find_player(arg)
        if matches.empty:
            print(f"No match for {arg!r}.")
            return
        infl = self._current_inflation()
        for _, row in matches.head(5).iterrows():
            suggested = round(row["baseline_value"] * infl, 1)
            status = " (DRAFTED)" if row["drafted"] else ""
            print(
                f"  {row['player_name']:<25} {row['position']:<4} "
                f"baseline ${row['baseline_value']:.0f} -> suggested max ${suggested:.0f}{status}"
            )
        print(f"  (current league inflation: {infl:.2f}x)")

    def do_pick(self, arg):
        "pick <player name> / <team> / <cost>  -- log a completed pick"
        parts = [p.strip() for p in arg.split("/")]
        if len(parts) != 3:
            print("Usage: pick <player name> / <team> / <cost>")
            return
        name, team_name, cost_s = parts
        try:
            cost = float(cost_s)
        except ValueError:
            print(f"Bad cost: {cost_s!r}")
            return
        if team_name not in self.teams:
            print(f"Unknown team {team_name!r}. Known teams: {', '.join(self.teams)}")
            return

        matches = self._find_player(name)
        if matches.empty:
            print(f"No match for {name!r} in the pool — logging cost with no baseline value.")
            baseline, position, player_name = 0.0, "?", name
        else:
            idx = matches.index[0]
            self.pool.loc[idx, "drafted"] = True
            row = self.pool.loc[idx]
            baseline, position, player_name = row["baseline_value"], row["position"], row["player_name"]

        team = self.teams[team_name]
        team.spent += cost
        team.picks.append(player_name)
        team.pick_positions.append(position)
        self.dollars_spent += cost
        self.baseline_value_drafted += baseline

        self.log.append(
            {
                "player_name": player_name,
                "position": position,
                "team_name": team_name,
                "cost": cost,
                "baseline_value": baseline,
            }
        )
        print(
            f"Logged: {player_name} ({position}) -> {team_name} for ${cost:.0f}. "
            f"{team_name} has ${team.remaining_budget:.0f} left, max bid ${team.max_bid:.0f}."
        )
        print(f"League inflation now {self._current_inflation():.2f}x")

    def do_budgets(self, arg):
        "budgets: show remaining budget / max bid / starting-lineup needs per team"
        rows = [
            (
                t.name, f"${t.remaining_budget:.0f}", t.remaining_spots, f"${t.max_bid:.0f}",
                format_needs(compute_needs(t.pick_positions, self.starting_slots)),
            )
            for t in self.teams.values()
        ]
        rows.sort(key=lambda r: -float(r[3].lstrip("$")))
        print(tabulate(rows, headers=["Team", "Budget left", "Spots left", "Max bid", "Starting-lineup needs"]))

    def do_needs(self, arg):
        "needs [team]: show starting-lineup needs for one team, or all teams if omitted.\n"
        "Informational only -- doesn't change any suggested price, just tells you who\n"
        "still needs to fill which starting slots (1 QB/RB/WR/TE, 3 FLEX, 1 DEF by default)."
        arg = arg.strip()
        team_names = [arg] if arg else list(self.teams)
        for name in team_names:
            if name not in self.teams:
                print(f"Unknown team {name!r}. Known teams: {', '.join(self.teams)}")
                continue
            t = self.teams[name]
            needs = compute_needs(t.pick_positions, self.starting_slots)
            print(f"  {t.name:<20} {format_needs(needs)}")

    def do_board(self, arg):
        "board [n]: top n undrafted players by suggested max bid (default 25)"
        n = int(arg.strip()) if arg.strip() else 25
        infl = self._current_inflation()
        undrafted = self.pool[~self.pool["drafted"]].copy()
        undrafted["suggested_max"] = (undrafted["baseline_value"] * infl).round(1)
        undrafted = undrafted.sort_values("suggested_max", ascending=False).head(n)
        print(
            tabulate(
                undrafted[["player_name", "position", "baseline_value", "suggested_max"]],
                headers=["Player", "Pos", "Baseline", "Suggested max"],
                showindex=False,
            )
        )

    def do_tendencies(self, arg):
        "tendencies <manager name>: print their historical tendency profile"
        if self.tendency_profiles is None:
            print("No tendency profiles loaded (run `profiles --csv` first and pass --profiles-csv here).")
            return
        name = arg.strip().lower()
        matches = self.tendency_profiles[
            self.tendency_profiles["manager_name"].str.lower().str.contains(name, regex=False)
        ]
        if matches.empty:
            print(f"No profile found for {arg!r}.")
            return
        for _, row in matches.iterrows():
            print(tendencies_mod.format_profile_text(row))

    def do_quit(self, arg):
        "quit: save the draft log and exit"
        if self.log:
            pd.DataFrame(self.log).to_csv(self.log_path, index=False)
            print(f"Saved draft log to {self.log_path}")
        return True

    do_exit = do_quit
    do_EOF = do_quit
