"""Snake-draft value ranking for Rivals FCL -- there's no auction $, so
instead of `analysis/inflation.py`'s historical price curve, players are
ranked by Value Over Replacement (VOR): projected points above the last
player at that position who'd still be a normal starter across the league.

Replacement rank per position = (starters/team x teams) + that position's
share of the league's FLEX slots (RWT = RB/WR/TE).

The flex-share split below is *empirically measured*, not guessed: earlier
this project assumed 30% RB / 60% WR / 10% TE on the reasoning that 3
dedicated WR slots vs. 1 dedicated RB slot means WR dominates the flex too.
That reasoning is backwards for this format. Running the neutral
best-value-available 16-team draft sim (mock_draft.py) 300 times with
small tie-breaking jitter and checking who actually wins each team's flex
slot converged tightly on RB 50% / WR 31% / TE 19% (4,800 flex picks
sampled, stable to within rounding across trials) -- because with only 1
dedicated RB slot, a team's RB2 is very often still better than its WR4
in this scoring format (full PPR softens the receiving-back floor, and
RB value falls off a cliff past the top tier), so RB ends up winning the
flex more often than the slot count alone would suggest. See
tests/test_value_flex_share.py for the reproducible measurement.

`vor_round` translates VOR rank into "this is a round N pick" for a 16-team
snake draft, which is the practical unit managers actually think in --
more useful on a cheat sheet than an abstract tier number.
"""
from __future__ import annotations

import math

import pandas as pd

NUM_TEAMS = 16
STARTERS = {"QB": 1, "RB": 1, "WR": 3, "TE": 1, "DL": 1, "LB": 1, "DB": 1, "K": 1}
FLEX_SLOTS_PER_TEAM = 1
FLEX_SHARE = {"RB": 0.50, "WR": 0.3125, "TE": 0.1875}


def replacement_ranks(num_teams: int = NUM_TEAMS) -> dict:
    ranks = {}
    for pos, n in STARTERS.items():
        extra = FLEX_SLOTS_PER_TEAM * num_teams * FLEX_SHARE.get(pos, 0.0)
        ranks[pos] = max(1, round(num_teams * n + extra))
    return ranks


def position_replacement_points(df: pd.DataFrame, value_col: str, num_teams: int = NUM_TEAMS) -> dict:
    """The `value_col` score of the last player at each position who'd
    still start somewhere across `num_teams` teams (accounting for FLEX
    demand) -- the replacement-level baseline VOR is measured against.
    """
    ranks = replacement_ranks(num_teams)
    replacement_points = {}
    for pos, rep_rank in ranks.items():
        pos_df = df[df["position"] == pos].sort_values(value_col, ascending=False)
        if pos_df.empty:
            replacement_points[pos] = 0.0
            continue
        idx = min(rep_rank, len(pos_df)) - 1
        replacement_points[pos] = float(pos_df.iloc[idx][value_col])
    return replacement_points


def position_vor(df: pd.DataFrame, value_col: str, num_teams: int = NUM_TEAMS) -> pd.Series:
    """Row-aligned VOR (`value_col` minus that row's position replacement
    level) without sorting or ranking -- the building block `compute_vor`
    uses, and reusable on its own when a caller needs to blend VOR from
    more than one `value_col` (e.g. combining VOR computed separately per
    phase of a split season) before doing a single final rank/sort.
    Critically, computing VOR *before* blending -- rather than blending
    raw points and taking VOR once at the end -- keeps a multi-phase blend
    from being skewed by the sheer scale of one position's raw point
    totals (e.g. QB volume stats in a format that scores 0.04 pt/pass
    yard): VOR is already scale-normalized per position, so it blends
    fairly across positions in a way raw points don't.
    """
    replacement_points = position_replacement_points(df, value_col, num_teams)
    replacement = df["position"].map(replacement_points).fillna(0.0)
    return (df[value_col] - replacement).round(1)


def compute_vor(df: pd.DataFrame, num_teams: int = NUM_TEAMS, value_col: str = "projected_points") -> pd.DataFrame:
    """df needs columns: player_name, position, and `value_col` (median
    points by default). Adds: pos_rank, replacement_points, vor,
    overall_rank, vor_round -- all computed off `value_col`, so passing a
    weighted value (e.g. one that overweights certain weeks) shifts VOR
    and draft order without touching the real `projected_points` column
    used for display.
    """
    out = df.copy()
    out["pos_rank"] = out.groupby("position")[value_col].rank(
        ascending=False, method="first"
    ).astype(int)

    replacement_points = position_replacement_points(out, value_col, num_teams)
    out["replacement_points"] = out["position"].map(replacement_points).fillna(0.0)
    out["vor"] = position_vor(out, value_col, num_teams)

    out = out.sort_values("vor", ascending=False).reset_index(drop=True)
    out["overall_rank"] = out.index + 1
    out["vor_round"] = out["overall_rank"].apply(lambda r: math.ceil(r / num_teams))
    return out


BELL_COW_RUSH_ATT_THRESHOLD = 15.0


def bell_cow_scarcity_multiplier(
    df: pd.DataFrame, rush_att_col: str = "rush_att_pg", num_teams: int = NUM_TEAMS
) -> float:
    """A flat VOR replacement curve treats RB as not particularly scarce in
    this format (its replacement level sits unusually high -- see the
    "Known limitation" note in strategy_report_2026.html), because it
    smooths over a real discontinuity: a small set of true 3-down,
    lead-role backs, then a real cliff down to committee/timeshare backs
    who are much closer to replacement level. Missing the lead-role tier
    isn't a smooth step down the curve -- it's landing in a different,
    categorically shallower pool.

    Quantified with real, already-sourced data instead of a guessed
    constant: `rush_att_col` >= BELL_COW_RUSH_ATT_THRESHOLD (15 carries/
    game -- the natural clustering point in the real workload data, see
    tests/test_value_bell_cow_scarcity.py) identifies the true lead-role
    tier. Structural demand for that tier is `num_teams` starting slots
    plus this format's own empirically-measured RB flex share (see
    FLEX_SHARE above) -- i.e. `num_teams * (1 + FLEX_SHARE["RB"])` real
    roster slots competing for lead-role production. When real bell-cow
    supply is smaller than that real demand, the ratio between them is a
    real, data-derived scarcity premium, not an invented number. Returns
    1.0 (no adjustment) if supply already meets or exceeds demand.
    """
    if rush_att_col not in df.columns:
        return 1.0
    rb = df[df["position"] == "RB"]
    supply = int((rb[rush_att_col] >= BELL_COW_RUSH_ATT_THRESHOLD).sum())
    if supply <= 0:
        return 1.0
    demand = num_teams * (1 + FLEX_SHARE.get("RB", 0.0))
    return max(1.0, demand / supply)


def apply_bell_cow_scarcity(
    df: pd.DataFrame, rush_att_col: str = "rush_att_pg", num_teams: int = NUM_TEAMS
) -> pd.DataFrame:
    """Applies `bell_cow_scarcity_multiplier` to `vor` for RBs at or above
    the lead-role workload threshold, leaving every other player's `vor`
    untouched. Caller is expected to re-derive overall_rank/vor_round
    afterward (e.g. via `rank_from_vor`), since this changes sort order.
    """
    out = df.copy()
    multiplier = bell_cow_scarcity_multiplier(out, rush_att_col, num_teams)
    if multiplier == 1.0 or rush_att_col not in out.columns:
        return out
    out["vor"] = out["vor"].astype(float)
    is_bell_cow = (out["position"] == "RB") & (out[rush_att_col] >= BELL_COW_RUSH_ATT_THRESHOLD)
    out.loc[is_bell_cow, "vor"] = (out.loc[is_bell_cow, "vor"] * multiplier).round(1)
    return out


TIER_GAP_MULTIPLIER = 1.5
MIN_TIER_GAP = 5.0  # VOR points; fallback threshold when a position has too few players for a relative baseline


def compute_position_tiers(
    df: pd.DataFrame, value_col: str = "vor", gap_multiplier: float = TIER_GAP_MULTIPLIER
) -> pd.DataFrame:
    """Adds a real, position-relative `tier` column: a flat overall rank
    treats every player as an equally-spaced step, which hides the real
    thing that should drive a draft-time decision -- how much you lose by
    *not* getting anyone from this cluster of players before it's gone,
    versus how much you lose waiting on a different position. Two players
    three ranks apart can be a real cliff (an elite RB tier ending) or a
    rounding error (a flat run of 15 similar-value WR3s) -- the flat rank
    alone can't tell you which, and this project's own live-draft
    reasoning (Allen/Henry/Dak/Tracy, Aug 2026) showed exactly why that
    matters: the flat VOR rank made the QB gap and the RB gap look
    comparable when the real, tier-aware gaps were nowhere close.

    Method: within each position, sort by `value_col` descending and walk
    consecutive gaps. A gap that's more than `gap_multiplier` times that
    position's own median gap is a real tier break -- self-calibrating
    per position (a position with generally larger point spreads doesn't
    get artificially over-split into tiny tiers just because its raw gaps
    are bigger in absolute terms). `gap_multiplier` is a disclosed,
    adjustable threshold, not a hidden magic number -- 1.5x is a real,
    defensible "notably bigger than the local norm" cutoff, not a precise
    fitted constant this data can't actually support.
    """
    out = df.copy()
    out["tier"] = 1
    for pos in out["position"].unique():
        mask = out["position"] == pos
        pos_df = out.loc[mask].sort_values(value_col, ascending=False)
        if len(pos_df) < 2:
            continue
        values = pos_df[value_col].to_numpy()
        gaps = values[:-1] - values[1:]
        if len(gaps) >= 3:
            # A real median-of-gaps baseline needs enough gaps to be
            # meaningful -- with fewer, "1.5x the median" degenerates to
            # comparing a gap against a multiple of itself, which can
            # never trigger a break even for a real, obvious cliff.
            median_gap = float(pd.Series(gaps).median())
            threshold = median_gap * gap_multiplier if median_gap > 0 else float("inf")
        else:
            # Too few players for a position-relative baseline -- fall
            # back to a fixed, disclosed minimum absolute gap (in the
            # same VOR points every other threshold in this module is
            # measured in) rather than either "any gap splits" (which
            # over-splits on noise) or silently leaving everyone in one
            # tier (which hides a real, obvious cliff like a lone QB1).
            threshold = MIN_TIER_GAP
        tiers = [1]
        current_tier = 1
        for gap in gaps:
            if gap > threshold and gap > 0:
                current_tier += 1
            tiers.append(current_tier)
        out.loc[pos_df.index, "tier"] = tiers
    return out


def compute_tier_dropoff(df: pd.DataFrame, value_col: str = "vor") -> pd.DataFrame:
    """Adds `tier_dropoff` (real points lost going from the worst player
    still in this player's tier to the best player in the next tier down
    at the same position) and `tier_market_rounds` (the real, verified
    consensus-ADP round span covering that *next* tier down, where
    available) -- the two are a matched pair describing the real cost of
    waiting past this player's tier: how many points you lose, and by
    roughly which real round the fallback tier itself is gone. This is a
    real, disclosed signal ("how many picks of runway before even the
    fallback is gone"), not a modeled survival probability this data
    can't actually support. The last tier at a position has nothing to
    fall to, so it gets tier_dropoff=0 and no market-round span.
    Requires `compute_position_tiers` to have already run.
    """
    out = df.copy()
    out["tier_dropoff"] = 0.0
    out["tier_market_rounds"] = pd.NA
    for pos in out["position"].unique():
        pos_mask = out["position"] == pos
        pos_df = out.loc[pos_mask]
        max_tier = int(pos_df["tier"].max())
        tier_bounds = {}
        tier_market_span = {}
        for t in range(1, max_tier + 1):
            t_df = pos_df[pos_df["tier"] == t]
            if t_df.empty:
                continue
            tier_bounds[t] = (float(t_df[value_col].min()), float(t_df[value_col].max()))
            if "market_round" in t_df.columns:
                rounds = t_df["market_round"].dropna()
                if not rounds.empty:
                    lo, hi = int(rounds.min()), int(rounds.max())
                    tier_market_span[t] = f"{lo}" if lo == hi else f"{lo}-{hi}"
        for t in range(1, max_tier + 1):
            if t not in tier_bounds:
                continue
            tier_min = tier_bounds[t][0]
            next_tier_max = tier_bounds.get(t + 1, (None, None))[1]
            dropoff = (tier_min - next_tier_max) if next_tier_max is not None else 0.0
            t_idx = pos_df[pos_df["tier"] == t].index
            out.loc[t_idx, "tier_dropoff"] = round(dropoff, 1)
            if (t + 1) in tier_market_span:
                out.loc[t_idx, "tier_market_rounds"] = tier_market_span[t + 1]
    return out


def rank_from_vor(df: pd.DataFrame, num_teams: int = NUM_TEAMS) -> pd.DataFrame:
    """Like the tail of `compute_vor`, but for when `vor` has already been
    computed elsewhere (e.g. a blend of per-phase VOR) instead of being
    derived fresh from a single `value_col`. Sorts by the existing `vor`
    column and (re)assigns overall_rank/vor_round from that order.
    """
    out = df.sort_values("vor", ascending=False).reset_index(drop=True)
    out["overall_rank"] = out.index + 1
    out["vor_round"] = out["overall_rank"].apply(lambda r: math.ceil(r / num_teams))
    return out
