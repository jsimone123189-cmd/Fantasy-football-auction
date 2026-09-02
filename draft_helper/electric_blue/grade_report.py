"""Generates a static, self-contained HTML post-draft grade report for
Electric Blue's real 2026 snake draft, from draft_grade.grade_draft
output. See that module's docstring for the pick-value methodology.
"""
from __future__ import annotations

import html

import pandas as pd

TEMPLATE = """<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {{
  --bg: #12151b; --bg-elevated: #1a1f28; --bg-card: #1f2530;
  --ink: #eee9dd; --ink-dim: #9aa0ab; --ink-faint: #6b7180;
  --accent: #d9a441; --accent-ink: #12151b;
  --good: #5fa98c; --warn: #e0982f; --danger: #c1553d;
  --line: rgba(238, 233, 221, 0.12); --line-strong: rgba(238, 233, 221, 0.22);
  --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace;
}}
:root[data-theme="light"] {{
  --bg: #f2efe4; --bg-elevated: #ffffff; --bg-card: #fbfaf5;
  --ink: #1c1f26; --ink-dim: #5b5f6b; --ink-faint: #878c98;
  --accent: #b9812a; --accent-ink: #ffffff;
  --good: #2f7d63; --warn: #a66a1a; --danger: #a83f2a;
  --line: rgba(28, 31, 38, 0.10); --line-strong: rgba(28, 31, 38, 0.20);
}}
@media (prefers-color-scheme: light) {{
  :root:not([data-theme="dark"]) {{
    --bg: #f2efe4; --bg-elevated: #ffffff; --bg-card: #fbfaf5;
    --ink: #1c1f26; --ink-dim: #5b5f6b; --ink-faint: #878c98;
    --accent: #b9812a; --accent-ink: #ffffff;
    --good: #2f7d63; --warn: #a66a1a; --danger: #a83f2a;
    --line: rgba(28, 31, 38, 0.10); --line-strong: rgba(28, 31, 38, 0.20);
  }}
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--ink); font-family: var(--font-body); line-height: 1.55; }}
.mono {{ font-family: var(--font-mono); font-variant-numeric: tabular-nums; }}
.wrap {{ max-width: 1020px; margin: 0 auto; padding: 28px 20px 60px; }}
.eyebrow {{ font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }}
h1 {{ font-size: 28px; margin: 6px 0 8px; }}
p.dek {{ font-size: 15px; color: var(--ink-dim); max-width: 68ch; margin: 0 0 24px; }}
.callout {{
  background: var(--bg-elevated); border: 1px solid var(--line-strong); border-left: 3px solid var(--accent);
  border-radius: 8px; padding: 14px 16px; font-size: 13px; color: var(--ink-dim); margin-bottom: 20px;
}}
.callout b {{ color: var(--ink); }}
.callout + .callout {{ margin-top: -10px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.table-wrap {{ overflow-x: auto; }}
th {{
  text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;
  color: var(--ink-faint); border-bottom: 1px solid var(--line-strong); padding: 8px 10px; white-space: nowrap;
}}
td {{ padding: 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
tr:last-child td {{ border-bottom: none; }}
.num {{ text-align: right; white-space: nowrap; }}
.grade {{
  display: inline-block; font-weight: 800; font-size: 14px; padding: 2px 10px; border-radius: 999px;
  font-family: var(--font-mono);
}}
.grade.good {{ background: color-mix(in srgb, var(--good) 20%, transparent); color: var(--good); }}
.grade.mid {{ background: color-mix(in srgb, var(--warn) 20%, transparent); color: var(--warn); }}
.grade.bad {{ background: color-mix(in srgb, var(--danger) 20%, transparent); color: var(--danger); }}
.pos {{ color: var(--good); }}
.neg {{ color: var(--danger); }}
.needs {{ color: var(--ink-faint); font-size: 12px; }}
.team-name {{ font-weight: 700; }}
.footer {{ margin-top: 28px; font-size: 12px; color: var(--ink-faint); }}
</style>
<div class="wrap">
  <div class="eyebrow">{eyebrow}</div>
  <h1>{title}</h1>
  <p class="dek">{dek}</p>
  <div class="callout">
    <b>How this is graded:</b> half roster strength (projected points from each team's best possible
    starting lineup: {slots_desc}), half pick-slot value. This is a snake draft, not an auction, so
    "value" here isn't $ &mdash; it's how much later than a player's real 2026 rank you got him
    (pick number minus overall rank). A steal is a big positive number; a reach is a big negative one.
  </div>
  <div class="callout">
    <b>Why every team's value number is negative:</b> this is a 14-round, 12-team league (168 total
    picks) drawing from a real player pool that runs dry of true difference-makers well before pick
    168 &mdash; by the last few rounds, everyone is picking real bench-tier/dart-throw depth, and even
    the best option left still grades as "below its slot" on pure rank math, because there's no
    better alternative sitting there for anyone. The raw number isn't a "did you draft well" score by
    itself &mdash; the team-to-team <b>comparison</b> is what the grade is actually built on.
  </div>
  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>Grade</th><th>Team</th><th class="num">Starting pts</th><th class="num">Roster pts</th>
        <th class="num">Value surplus</th><th>Best value pick</th><th>Worst value pick</th><th>Starting-lineup needs</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
  </div>
  <div class="footer">{footer}</div>
</div>
"""

ROW_TEMPLATE = """<tr>
  <td><span class="grade {grade_class}">{grade}</span></td>
  <td class="team-name">{team_name}</td>
  <td class="num mono">{starting_points:.0f}</td>
  <td class="num mono">{roster_points:.0f}</td>
  <td class="num mono {surplus_class}">{surplus_sign}{surplus_abs:.0f}</td>
  <td>{best_value_name} <span class="pos mono">(+{best_value_delta:.0f})</span></td>
  <td>{worst_value_name} <span class="{worst_class} mono">({worst_sign}{worst_abs:.0f})</span></td>
  <td class="needs">{needs}</td>
</tr>"""


def _grade_class(grade: str) -> str:
    if grade.startswith("A"):
        return "good"
    if grade.startswith(("B", "C")):
        return "mid"
    return "bad"


def generate_html(
    grades: pd.DataFrame,
    title: str = "Electric Blue Post-Draft Grades",
    eyebrow: str = "Draft Recap",
    dek: str = "Graded on starting-lineup strength and real pick-slot value, not a hypothetical bench slot.",
    slots_desc: str = "1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 DEF",
    footer: str = "",
) -> str:
    rows = []
    for _, r in grades.iterrows():
        surplus = float(r["value_surplus"])
        worst = float(r["worst_value_delta"])
        rows.append(
            ROW_TEMPLATE.format(
                grade_class=_grade_class(r["grade"]),
                grade=html.escape(str(r["grade"])),
                team_name=html.escape(str(r["team_name"])),
                starting_points=float(r["starting_points"]),
                roster_points=float(r["roster_points"]),
                surplus_class="pos" if surplus >= 0 else "neg",
                surplus_sign="+" if surplus >= 0 else "-",
                surplus_abs=abs(surplus),
                best_value_name=html.escape(str(r["best_value_name"])),
                best_value_delta=float(r["best_value_delta"]),
                worst_value_name=html.escape(str(r["worst_value_name"])),
                worst_class="pos" if worst >= 0 else "neg",
                worst_sign="+" if worst >= 0 else "-",
                worst_abs=abs(worst),
                needs=html.escape(str(r["needs"])),
            )
        )
    return TEMPLATE.format(
        title=html.escape(title),
        eyebrow=html.escape(eyebrow),
        dek=html.escape(dek),
        slots_desc=html.escape(slots_desc),
        rows="\n      ".join(rows),
        footer=html.escape(footer),
    )
