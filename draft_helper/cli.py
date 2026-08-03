from __future__ import annotations

import logging
import os

import click
import pandas as pd
from dotenv import load_dotenv

from . import fetch_history, storage
from .analysis.cheat_sheet import generate_cheat_sheet, load_projections
from .analysis.inflation import build_position_rank_curve
from .analysis.roster_needs import parse_slots
from .analysis.tendencies import build_tendency_profiles, format_profile_text
from .auth import YahooOAuth
from .live_assistant import LiveDraftShell
from .web import generate_html as generate_live_web_html
from .yahoo_client import YahooFantasyClient

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")


def _oauth() -> YahooOAuth:
    return YahooOAuth(
        client_id=os.environ.get("YAHOO_CLIENT_ID", ""),
        client_secret=os.environ.get("YAHOO_CLIENT_SECRET", ""),
    )


@click.group()
def cli():
    """Fantasy football auction draft helper, built on your league's own Yahoo history."""


@cli.command()
@click.option("--code", default=None, help="Skip the interactive prompt: exchange this verifier code directly.")
@click.option("--show-url", is_flag=True, help="Just print the authorize URL and exit (no exchange).")
def auth(code, show_url):
    """One-time (or as-needed) Yahoo login. Opens a URL for you to approve access,
    then asks you to paste back the verifier code Yahoo shows you."""
    oauth = _oauth()
    if show_url:
        print(oauth.authorize_url())
        return
    if code:
        oauth.exchange_code(code)
        print("Login successful — token saved.")
        return
    oauth.interactive_login()


@cli.command()
def leagues():
    """List every NFL league Yahoo has on file for your account (all seasons).

    Use this to find your league_id / league_keys if `fetch-history` auto-discovery
    misses a year (e.g. the league was recreated at some point).
    """
    client = YahooFantasyClient(_oauth())
    for league in sorted(client.get_user_leagues(), key=lambda x: (x.get("season") or "", x.get("name") or "")):
        print(
            f"{league.get('season'):<6} {league.get('league_key'):<18} "
            f"league_id={league.get('league_id'):<8} draft_status={league.get('draft_status'):<10} "
            f"{league.get('name')}"
        )


@cli.command("fetch-history")
@click.option("--league-id", default=lambda: os.environ.get("YAHOO_LEAGUE_ID"), help="Yahoo league_id (stable across renewed seasons).")
@click.option("--league-keys", default=None, help="Explicit override, e.g. '2022=406.l.12345,2023=423.l.12345'")
def fetch_history_cmd(league_id, league_keys):
    """Pull and cache every auction season of your league's draft history."""
    client = YahooFantasyClient(_oauth())
    keys_map = None
    if league_keys:
        keys_map = dict(pair.split("=", 1) for pair in league_keys.split(","))
    if not league_id and not keys_map:
        raise click.UsageError("Provide --league-id (or set YAHOO_LEAGUE_ID) or --league-keys.")
    results = fetch_history.fetch_history(client, league_id=league_id, league_keys=keys_map)
    for r in results:
        if r.get("skipped"):
            print(f"{r['season']}: skipped ({r['reason']})")
        else:
            print(f"{r['season']}: {r['picks']} picks -> {r['path']}")


@cli.command("debug-endpoint")
@click.argument("path")
def debug_endpoint(path):
    """Fetch raw JSON from an arbitrary Yahoo endpoint path, e.g. /league/423.l.123/teams.

    Useful if a real response's shape doesn't match what yahoo_client.py expects —
    dump it here, compare to the extract_* functions, and adjust.
    """
    import json

    client = YahooFantasyClient(_oauth())
    print(json.dumps(client.raw_get(path), indent=2))


@cli.command()
@click.option("--seasons", default=None, help="Comma-separated seasons to include (default: all cached).")
@click.option("--csv", "csv_out", default=None, help="Optional path to also save profiles as CSV.")
def profiles(seasons, csv_out):
    """Print owner tendency profiles built from your cached draft history."""
    df = storage.load_all_drafts()
    if df.empty:
        raise click.ClickException("No cached draft data found. Run `fetch-history` first.")
    if seasons:
        wanted = set(s.strip() for s in seasons.split(","))
        df = df[df["season"].astype(str).isin(wanted)]
    profile_df = build_tendency_profiles(df)
    for _, row in profile_df.iterrows():
        print(format_profile_text(row))
        print()
    if csv_out:
        profile_df.to_csv(csv_out, index=False)
        print(f"Saved to {csv_out}")


@cli.command("cheat-sheet")
@click.option("--projections", required=True, help="CSV with player_name, position, and projected_rank or projected_points.")
@click.option("--num-teams", required=True, type=int)
@click.option("--budget-per-team", default=lambda: float(os.environ.get("LEAGUE_BUDGET", 200)), type=float)
@click.option("--keepers", default=None, help="Optional CSV of this year's locked keepers: player_name,cost,team_name.")
@click.option("--out", "out_path", default=None, help="Optional path to save the cheat sheet as CSV.")
def cheat_sheet_cmd(projections, num_teams, budget_per_team, keepers, out_path):
    """Generate target auction prices for this year's players from your league's historical curve."""
    df = storage.load_all_drafts()
    if df.empty:
        raise click.ClickException("No cached draft data found. Run `fetch-history` first.")
    curve = build_position_rank_curve(df)
    proj = load_projections(projections)
    keeper_df = pd.read_csv(keepers) if keepers else None
    sheet = generate_cheat_sheet(proj, curve, num_teams, budget_per_team, keeper_costs=keeper_df)
    print(sheet.to_string(index=False))
    if out_path:
        sheet.to_csv(out_path, index=False)
        print(f"Saved to {out_path}")


@cli.command()
@click.option("--projections", required=True, help="CSV with player_name, position, and projected_rank or projected_points.")
@click.option("--teams", required=True, help="Comma-separated team names participating tonight.")
@click.option("--budget-per-team", default=lambda: float(os.environ.get("LEAGUE_BUDGET", 200)), type=float)
@click.option("--roster-size", required=True, type=int, help="Total roster spots per team.")
@click.option("--profiles-csv", default=None, help="Optional tendency profiles CSV (from `profiles --csv`) for the `tendencies` command.")
@click.option("--log-path", default="draft_log.csv")
@click.option(
    "--starting-slots",
    default="QB:1,RB:1,WR:1,TE:1,FLEX:3,DEF:1",
    help="Starting lineup slots as POS:COUNT pairs, used only for the `needs`/`budgets` positional-need "
    "display (never affects suggested prices). FLEX is filled from RB/WR/TE. Default matches this league's "
    "real roster; override if you're running this for a different league.",
)
def live(projections, teams, budget_per_team, roster_size, profiles_csv, log_path, starting_slots):
    """Start the interactive live-draft assistant."""
    df = storage.load_all_drafts()
    if df.empty:
        raise click.ClickException("No cached draft data found. Run `fetch-history` first.")
    curve = build_position_rank_curve(df)
    proj = load_projections(projections)
    team_list = [t.strip() for t in teams.split(",")]
    profile_df = pd.read_csv(profiles_csv) if profiles_csv else None
    slots = parse_slots(starting_slots)
    shell = LiveDraftShell(proj, curve, team_list, budget_per_team, roster_size, profile_df, log_path, starting_slots=slots)
    shell.cmdloop()


@cli.command("live-web")
@click.option("--projections", required=True, help="CSV with player_name, position, and projected_rank or projected_points.")
@click.option("--teams", required=True, help="Comma-separated team names to pre-fill (editable in the page's Setup tab).")
@click.option("--num-teams", default=None, type=int, help="Defaults to the count of --teams.")
@click.option("--budget-per-team", default=lambda: float(os.environ.get("LEAGUE_BUDGET", 200)), type=float)
@click.option("--roster-size", required=True, type=int, help="Total roster spots per team.")
@click.option("--title", default="Draft Assistant")
@click.option("--eyebrow", default="Live Draft Assistant")
@click.option("--keepers", default=None, help="Optional CSV of locked keepers: player_name,position,team_name,cost.")
@click.option(
    "--starting-slots",
    default="QB:1,RB:1,WR:1,TE:1,FLEX:3,DEF:1",
    help="Starting lineup slots as POS:COUNT pairs, used only for the Budgets tab's positional-need display "
    "(never affects suggested prices). FLEX is filled from RB/WR/TE. Default matches this league's real roster.",
)
@click.option("--out", "out_path", default="draft_assistant.html")
def live_web(projections, teams, num_teams, budget_per_team, roster_size, title, eyebrow, keepers, starting_slots, out_path):
    """Generate the self-contained live-draft web page (see README) as a static HTML file.

    Publish the resulting file (e.g. via an Artifact) or just open it in a
    browser -- everything runs client-side, no server needed, so it stays
    fast under a live auction's bid timer.
    """
    df = storage.load_all_drafts()
    if df.empty:
        raise click.ClickException("No cached draft data found. Run `fetch-history` first.")
    curve = build_position_rank_curve(df)
    proj = load_projections(projections)
    team_list = [t.strip() for t in teams.split(",")]
    keeper_df = pd.read_csv(keepers) if keepers else None
    slots = parse_slots(starting_slots)
    html = generate_live_web_html(
        curve,
        proj,
        num_teams or len(team_list),
        budget_per_team,
        roster_size,
        team_list,
        title=title,
        keepers=keeper_df,
        eyebrow=eyebrow,
        starting_slots=slots,
    )
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Wrote {out_path} ({len(html)} bytes)")


if __name__ == "__main__":
    cli()
