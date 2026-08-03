import pytest

from draft_helper.analysis.roster_needs import compute_needs, format_needs, parse_slots


def test_parse_slots():
    assert parse_slots("QB:1,RB:1,WR:1,TE:1,FLEX:3,DEF:1") == {
        "QB": 1, "RB": 1, "WR": 1, "TE": 1, "FLEX": 3, "DEF": 1,
    }


def test_compute_needs_empty_roster_needs_everything():
    needs = compute_needs([])
    assert needs["open_dedicated"] == {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "DEF": 1}
    assert needs["open_flex"] == 3
    assert not needs["starting_lineup_full"]


def test_compute_needs_fills_dedicated_before_flex():
    # Two WRs: first fills the dedicated WR slot, second goes to FLEX.
    needs = compute_needs(["WR", "WR"])
    assert "WR" not in needs["open_dedicated"]
    assert needs["open_flex"] == 2


def test_compute_needs_excess_depth_is_bench_not_need():
    # Way more RBs than slots -- extras don't create negative need or affect other slots.
    # 1 fills the dedicated RB slot, 3 fill all 3 FLEX slots, the 5th is pure bench.
    needs = compute_needs(["RB", "RB", "RB", "RB", "RB"])
    assert "RB" not in needs["open_dedicated"]
    assert needs["open_flex"] == 0
    assert needs["open_dedicated"] == {"QB": 1, "WR": 1, "TE": 1, "DEF": 1}


def test_compute_needs_full_starting_lineup():
    picks = ["QB", "RB", "WR", "TE", "DEF", "RB", "WR", "TE"]  # dedicated x5 + 3 flex
    needs = compute_needs(picks)
    assert needs["starting_lineup_full"]
    assert needs["open_dedicated"] == {}
    assert needs["open_flex"] == 0


def test_format_needs_lists_positions_and_flex():
    needs = compute_needs(["QB"])  # QB already filled, everything else still open
    text = format_needs(needs)
    assert text.startswith("needs ")
    assert "RB" in text and "WR" in text and "TE" in text and "DEF" in text and "FLEX" in text
    assert "QB" not in text


def test_format_needs_full_lineup():
    picks = ["QB", "RB", "WR", "TE", "DEF", "RB", "WR", "TE"]
    assert format_needs(compute_needs(picks)) == "starting lineup full"
