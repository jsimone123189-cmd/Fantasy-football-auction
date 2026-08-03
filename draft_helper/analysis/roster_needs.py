"""Tracks each team's still-open *starting* roster slots from their pick
log, so the live tools can show positional need alongside budget/inflation.

This is informational only -- it does not feed back into suggested prices
(see README for why: turning "need" into a price adjustment is a real
modeling assumption, not just a display of facts, and is left as a
possible future step rather than baked in here).

Default slots match this league's real confirmed Yahoo roster (1 QB, 1 RB,
1 WR, 1 TE, 3 FLEX (RB/WR/TE), 1 DEF -- bench and IR spots aren't tracked
as "needs" since any position can fill them).
"""
from __future__ import annotations

FLEX_ELIGIBLE = {"RB", "WR", "TE"}

DEFAULT_SLOTS = {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "DEF": 1, "FLEX": 3}


def parse_slots(spec: str) -> dict:
    """Parse "QB:1,RB:1,WR:1,TE:1,FLEX:3,DEF:1" into {"QB": 1, ...}."""
    slots = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        pos, _, count = part.partition(":")
        slots[pos.strip().upper()] = int(count.strip())
    return slots


def compute_needs(pick_positions: list[str], slots: dict | None = None) -> dict:
    """pick_positions: a team's drafted players' positions, in draft order.
    Greedily fills each position's own dedicated slot first, then FLEX,
    then treats anything left over as bench depth with no effect on need.
    Order matters only in the sense that whichever picks arrive first claim
    the dedicated slot before FLEX -- a reasonable approximation of how a
    real manager would actually slot their roster.
    """
    slots = dict(slots or DEFAULT_SLOTS)
    flex_remaining = slots.pop("FLEX", 0)
    remaining = dict(slots)

    for raw_pos in pick_positions:
        pos = str(raw_pos).strip().upper()
        if remaining.get(pos, 0) > 0:
            remaining[pos] -= 1
        elif pos in FLEX_ELIGIBLE and flex_remaining > 0:
            flex_remaining -= 1
        # else: bench/IR depth -- doesn't affect starting-lineup need

    open_dedicated = {pos: n for pos, n in remaining.items() if n > 0}
    return {
        "open_dedicated": open_dedicated,
        "open_flex": flex_remaining,
        "starting_lineup_full": not open_dedicated and flex_remaining == 0,
    }


def format_needs(needs: dict) -> str:
    parts = [f"{n} {pos}" if n > 1 else pos for pos, n in needs["open_dedicated"].items()]
    if needs["open_flex"] > 0:
        parts.append(f"{needs['open_flex']} FLEX" if needs["open_flex"] > 1 else "FLEX")
    return "needs " + ", ".join(parts) if parts else "starting lineup full"
