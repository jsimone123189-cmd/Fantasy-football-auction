"""Generates a static, self-contained HTML post-draft grade report from
draft_helper.analysis.draft_grade output. See that module's docstring for
the grading methodology and why it deliberately does not penalize a team
for skipping a backup DEF/QB/TE.
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
.wrap {{ max-width: 980px; margin: 0 auto; padding: 28px 20px 60px; }}
.eyebrow {{ font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }}
h1 {{ font-size: 28px; margin: 6px 0 8px; }}
p.dek {{ font-size: 15px; color: var(--ink-dim); max-width: 62ch; margin: 0 0 24px; }}
.callout {{
  background: var(--bg-elevated); border: 1px solid var(--line-strong); border-left: 3px solid var(--accent);
  border-radius: 8px; padding: 14px 16px; font-size: 13px; color: var(--ink-dim); margin-bottom: 28px;
}}
.callout b {{ color: var(--ink); }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{
  text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;
  color: var(--ink-faint); border-bottom: 1px solid var(--line-strong); padding: 8px 10px;
}}
td {{ padding: 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
tr:last-child td {{ border-bottom: none; }}
.num {{ text-align: right; }}
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
    <b>How this is graded:</b> half roster strength (projected points from each team's best
    possible starting lineup), half auction value (this year's fair price for each player,
    per your league's own historical curve, vs. what was actually paid). Unlike some default
    auto-grade tools, skipping a backup DEF, backup QB, or 2nd TE is <b>not</b> treated as a
    penalty here &mdash; those spots are graded on whatever real player actually filled them,
    not an assumed zero for a bench slot most managers stream instead of draft.
  </div>
  <table>
    <thead>
      <tr>
        <th>Grade</th><th>Team</th><th class="num">Starting pts</th><th class="num">Spent</th>
        <th class="num">Value surplus</th><th>Best value</th><th>Worst value</th><th>Starting-lineup needs</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
  <div class="footer">{footer}</div>
</div>
"""

ROW_TEMPLATE = """<tr>
  <td><span class="grade {grade_class}">{grade}</span></td>
  <td class="team-name">{team_name}</td>
  <td class="num mono">{starting_points:.0f}</td>
  <td class="num mono">${spent:.0f}</td>
  <td class="num mono {surplus_class}">{surplus_sign}${surplus_abs:.0f}</td>
  <td>{best_value_name} <span class="pos mono">(+${best_value_delta:.0f})</span></td>
  <td>{worst_value_name} <span class="{worst_class} mono">({worst_sign}${worst_abs:.0f})</span></td>
  <td class="needs">{needs}</td>
</tr>"""


def _grade_class(grade: str) -> str:
    if grade.startswith(("A",)):
        return "good"
    if grade.startswith(("B", "C")):
        return "mid"
    return "bad"


def generate_html(
    grades: pd.DataFrame,
    title: str = "Post-Draft Grades",
    eyebrow: str = "Draft Recap",
    dek: str = "Graded on starting-lineup strength and auction value, not a hypothetical bench slot.",
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
                spent=float(r["spent"]),
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
        rows="\n      ".join(rows),
        footer=html.escape(footer),
    )
