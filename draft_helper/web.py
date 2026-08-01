"""Generates the self-contained live-draft web assistant (see README).

All computation happens client-side in the browser once loaded — no network
calls, no server — so it stays fast under a live auction's bid timer. Only
the player pool (baseline $ values) ships in the page; owner tendency
history lives in the separate strategy report instead (`draft-helper
strategy-report`), by design — the live tool is for in-the-moment mechanics
only.
"""
from __future__ import annotations

import json

import pandas as pd

from .analysis.inflation import baseline_value

TEMPLATE = r"""<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
:root {{
  --bg: #12151b;
  --bg-elevated: #1a1f28;
  --bg-card: #1f2530;
  --ink: #eee9dd;
  --ink-dim: #9aa0ab;
  --ink-faint: #6b7180;
  --accent: #d9a441;
  --accent-ink: #12151b;
  --good: #5fa98c;
  --good-bg: rgba(95, 169, 140, 0.14);
  --warn: #e0982f;
  --warn-bg: rgba(224, 152, 47, 0.14);
  --danger: #c1553d;
  --danger-bg: rgba(193, 85, 61, 0.16);
  --line: rgba(238, 233, 221, 0.12);
  --line-strong: rgba(238, 233, 221, 0.22);
  --shadow: 0 12px 32px rgba(0,0,0,0.35);
  --radius: 14px;
  --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace;
}}
:root[data-theme="light"] {{
  --bg: #f2efe4;
  --bg-elevated: #ffffff;
  --bg-card: #fbfaf5;
  --ink: #1c1f26;
  --ink-dim: #5b5f6b;
  --ink-faint: #878c98;
  --accent: #b9812a;
  --accent-ink: #ffffff;
  --good: #2f7d63;
  --good-bg: rgba(47, 125, 99, 0.10);
  --warn: #a66a1a;
  --warn-bg: rgba(166, 106, 26, 0.10);
  --danger: #a83f2a;
  --danger-bg: rgba(168, 63, 42, 0.10);
  --line: rgba(28, 31, 38, 0.10);
  --line-strong: rgba(28, 31, 38, 0.20);
  --shadow: 0 12px 28px rgba(28,31,38,0.10);
}}
@media (prefers-color-scheme: light) {{
  :root:not([data-theme="dark"]) {{
    --bg: #f2efe4;
    --bg-elevated: #ffffff;
    --bg-card: #fbfaf5;
    --ink: #1c1f26;
    --ink-dim: #5b5f6b;
    --ink-faint: #878c98;
    --accent: #b9812a;
    --accent-ink: #ffffff;
    --good: #2f7d63;
    --good-bg: rgba(47, 125, 99, 0.10);
    --warn: #a66a1a;
    --warn-bg: rgba(166, 106, 26, 0.10);
    --danger: #a83f2a;
    --danger-bg: rgba(168, 63, 42, 0.10);
    --line: rgba(28, 31, 38, 0.10);
    --line-strong: rgba(28, 31, 38, 0.20);
    --shadow: 0 12px 28px rgba(28,31,38,0.10);
  }}
}}
* {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font-body);
  min-height: 100vh;
  padding-bottom: 84px;
  overflow-x: hidden;
}}
h1, h2, h3 {{ text-wrap: balance; margin: 0; }}
.mono {{ font-family: var(--font-mono); font-variant-numeric: tabular-nums; }}
button, input, select {{ font-family: inherit; }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; transition: none !important; }} }}

header.topbar {{
  position: sticky; top: 0; z-index: 20;
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line);
  padding: 10px 16px;
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
}}
.brand {{ display: flex; flex-direction: column; line-height: 1.1; }}
.brand .eyebrow {{
  font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--ink-faint); font-weight: 600;
}}
.brand .title {{ font-size: 17px; font-weight: 800; letter-spacing: -0.01em; }}
.inflation-gauge {{
  display: flex; align-items: center; gap: 8px;
  background: var(--bg-card); border: 1px solid var(--line);
  border-radius: 999px; padding: 6px 12px 6px 10px;
}}
.inflation-gauge .dot {{ width: 8px; height: 8px; border-radius: 50%; flex: none; }}
.inflation-gauge .val {{ font-family: var(--font-mono); font-weight: 700; font-size: 14px; }}
.inflation-gauge .lbl {{ font-size: 10px; color: var(--ink-faint); text-transform: uppercase; letter-spacing: 0.08em; }}

nav.tabs {{
  position: sticky; top: 49px; z-index: 19;
  display: flex; gap: 2px;
  background: var(--bg);
  border-bottom: 1px solid var(--line);
  padding: 0 12px;
  overflow-x: auto;
}}
nav.tabs button {{
  background: none; border: none; color: var(--ink-dim);
  padding: 11px 14px; font-size: 13px; font-weight: 700;
  border-bottom: 2px solid transparent; cursor: pointer; white-space: nowrap;
}}
nav.tabs button.active {{ color: var(--ink); border-bottom-color: var(--accent); }}

main {{ max-width: 640px; margin: 0 auto; padding: 16px; }}
.panel {{ display: none; }}
.panel.active {{ display: block; }}

.card {{
  background: var(--bg-elevated); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 16px; margin-bottom: 14px;
}}
.card h2 {{
  font-size: 12px; text-transform: uppercase; letter-spacing: 0.09em;
  color: var(--ink-faint); font-weight: 700; margin-bottom: 12px;
}}

.field {{ margin-bottom: 12px; }}
.field label {{
  display: block; font-size: 11px; color: var(--ink-faint);
  text-transform: uppercase; letter-spacing: 0.07em; font-weight: 700; margin-bottom: 6px;
}}
input[type="text"], input[type="number"] {{
  width: 100%; background: var(--bg-card); border: 1px solid var(--line-strong);
  color: var(--ink); border-radius: 10px; padding: 12px 12px; font-size: 16px;
}}
.suggest-list {{
  margin-top: 6px; border: 1px solid var(--line); border-radius: 10px;
  overflow: hidden; max-height: 220px; overflow-y: auto;
}}
.suggest-row {{
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 12px; border-bottom: 1px solid var(--line); cursor: pointer;
  background: var(--bg-card);
}}
.suggest-row:last-child {{ border-bottom: none; }}
.suggest-row:active {{ background: var(--bg); }}
.suggest-row .nm {{ font-weight: 600; font-size: 14px; }}
.suggest-row .meta {{ font-size: 11px; color: var(--ink-faint); }}
.suggest-row .px {{ font-family: var(--font-mono); font-weight: 700; color: var(--accent); }}

.picked-player {{
  display: flex; justify-content: space-between; align-items: center;
  background: var(--bg-card); border: 1px solid var(--line-strong);
  border-radius: 10px; padding: 12px 14px; margin-bottom: 12px;
}}
.picked-player .nm {{ font-weight: 800; font-size: 15px; }}
.picked-player .meta {{ font-size: 12px; color: var(--ink-dim); margin-top: 2px; }}
.picked-player .suggested {{ text-align: right; }}
.picked-player .suggested .amt {{ font-family: var(--font-mono); font-weight: 800; font-size: 18px; color: var(--accent); }}
.picked-player .suggested .lbl {{ font-size: 10px; color: var(--ink-faint); text-transform: uppercase; letter-spacing: 0.06em; }}

.chip-row {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }}
.chip {{
  background: var(--bg-card); border: 1px solid var(--line-strong);
  color: var(--ink); border-radius: 999px; padding: 9px 14px;
  font-size: 13px; font-weight: 700; cursor: pointer; white-space: nowrap;
}}
.chip.selected {{ background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }}
.chip .sub {{ font-weight: 500; opacity: 0.75; font-size: 11px; margin-left: 5px; }}

button.primary {{
  width: 100%; background: var(--accent); color: var(--accent-ink); border: none;
  border-radius: 10px; padding: 15px; font-size: 15px; font-weight: 800;
  letter-spacing: 0.01em; cursor: pointer;
}}
button.primary:disabled {{ opacity: 0.4; }}
button.ghost {{
  width: 100%; background: none; border: 1px solid var(--line-strong); color: var(--ink-dim);
  border-radius: 10px; padding: 12px; font-size: 13px; font-weight: 700; cursor: pointer; margin-top: 8px;
}}

.budget-scroll {{ display: flex; gap: 10px; overflow-x: auto; padding-bottom: 4px; margin: -2px; padding: 2px 2px 8px; }}
.budget-card {{
  flex: none; width: 140px; border-radius: 12px; padding: 12px;
  border: 1px solid var(--line-strong); background: var(--bg-card);
}}
.budget-card.health-good {{ border-color: color-mix(in srgb, var(--good) 45%, var(--line-strong)); }}
.budget-card.health-warn {{ border-color: color-mix(in srgb, var(--warn) 45%, var(--line-strong)); }}
.budget-card.health-danger {{ border-color: color-mix(in srgb, var(--danger) 55%, var(--line-strong)); }}
.budget-card .nm {{ font-weight: 800; font-size: 13px; margin-bottom: 8px; }}
.budget-card .row {{ display: flex; justify-content: space-between; font-size: 11px; color: var(--ink-faint); margin-bottom: 2px; }}
.budget-card .row .v {{ font-family: var(--font-mono); color: var(--ink); font-weight: 700; }}
.pill {{
  display: inline-block; font-size: 10px; font-weight: 800; letter-spacing: 0.04em;
  padding: 3px 8px; border-radius: 999px; margin-top: 6px; text-transform: uppercase;
}}
.pill.health-good {{ background: var(--good-bg); color: var(--good); }}
.pill.health-warn {{ background: var(--warn-bg); color: var(--warn); }}
.pill.health-danger {{ background: var(--danger-bg); color: var(--danger); }}

.pos-filter {{ display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }}
.pos-filter button {{
  background: var(--bg-card); border: 1px solid var(--line-strong); color: var(--ink-dim);
  border-radius: 8px; padding: 7px 11px; font-size: 12px; font-weight: 700; cursor: pointer;
}}
.pos-filter button.active {{ background: var(--ink); color: var(--bg-elevated); border-color: var(--ink); }}
table.board {{ width: 100%; border-collapse: collapse; }}
table.board th {{
  text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--ink-faint); font-weight: 700; padding: 6px 8px; border-bottom: 1px solid var(--line-strong);
}}
table.board td {{ padding: 9px 8px; border-bottom: 1px solid var(--line); font-size: 13px; }}
table.board td.num {{ font-family: var(--font-mono); text-align: right; font-weight: 700; }}
table.board td.px {{ color: var(--accent); }}
.board-wrap {{ overflow-x: auto; }}
.pos-tag {{
  font-size: 10px; font-weight: 800; color: var(--ink-faint);
  border: 1px solid var(--line-strong); border-radius: 5px; padding: 1px 5px; margin-left: 6px;
}}

.log-row {{ display: flex; justify-content: space-between; align-items: center; padding: 9px 0; border-bottom: 1px solid var(--line); font-size: 13px; }}
.log-row:last-child {{ border-bottom: none; }}
.log-row .nm {{ font-weight: 700; }}
.log-row .to {{ color: var(--ink-faint); font-size: 12px; }}
.log-row .amt {{ font-family: var(--font-mono); font-weight: 800; }}

.team-edit-row {{ display: flex; gap: 8px; margin-bottom: 8px; align-items: center; }}
.team-edit-row input {{ flex: 1; }}
.team-edit-row button.rm {{
  flex: none; background: var(--bg-card); border: 1px solid var(--line-strong); color: var(--danger);
  border-radius: 8px; width: 38px; height: 38px; font-size: 16px; cursor: pointer;
}}
.hint {{ font-size: 12px; color: var(--ink-faint); line-height: 1.5; margin-top: 4px; }}

.empty {{ text-align: center; padding: 24px 12px; color: var(--ink-faint); font-size: 13px; }}
.toast {{
  position: fixed; bottom: 90px; left: 50%; transform: translateX(-50%);
  background: var(--ink); color: var(--bg); padding: 10px 18px; border-radius: 999px;
  font-size: 13px; font-weight: 700; box-shadow: var(--shadow); z-index: 50;
  opacity: 0; pointer-events: none; transition: opacity 0.2s, transform 0.2s;
}}
.toast.show {{ opacity: 1; }}
</style>

<header class="topbar">
  <div class="brand">
    <span class="eyebrow">{eyebrow}</span>
    <span class="title">Draft Assistant</span>
  </div>
  <div class="inflation-gauge" id="inflationGauge">
    <span class="dot" id="inflationDot"></span>
    <span><span class="val mono" id="inflationVal">1.00x</span><br><span class="lbl">inflation</span></span>
  </div>
</header>

<nav class="tabs">
  <button data-panel="draft" class="active">Nominate</button>
  <button data-panel="board">Board</button>
  <button data-panel="budgets">Budgets</button>
  <button data-panel="setup">Setup</button>
</nav>

<main>

  <section class="panel active" id="panel-draft">
    <div class="card">
      <h2>Who's up?</h2>
      <div class="field">
        <label for="playerSearch">Player</label>
        <input type="text" id="playerSearch" placeholder="Start typing a name&hellip;" autocomplete="off">
        <div class="suggest-list" id="suggestList" style="display:none;"></div>
      </div>
      <div id="pickedPlayerWrap"></div>
      <div class="field">
        <label>Team</label>
        <div class="chip-row" id="teamChips"></div>
      </div>
      <div class="field">
        <label for="priceInput">Winning bid ($)</label>
        <input type="number" id="priceInput" min="1" step="1" placeholder="$">
      </div>
      <button class="primary" id="logPickBtn" disabled>Log pick</button>
      <button class="ghost" id="undoBtn" style="display:none;">Undo last pick</button>
    </div>

    <div class="card" id="recentCard" style="display:none;">
      <h2>Recent picks</h2>
      <div id="recentLog"></div>
    </div>
  </section>

  <section class="panel" id="panel-board">
    <div class="card">
      <h2>Undrafted, by suggested max bid</h2>
      <div class="pos-filter" id="posFilter"></div>
      <div class="board-wrap">
        <table class="board">
          <thead><tr><th>Player</th><th class="num">Base</th><th class="num">Max&nbsp;bid</th></tr></thead>
          <tbody id="boardBody"></tbody>
        </table>
      </div>
    </div>
  </section>

  <section class="panel" id="panel-budgets">
    <div class="card">
      <h2>Remaining budget &amp; max bid</h2>
      <div class="budget-scroll" id="budgetScroll"></div>
      <p class="hint">Max bid = budget left minus $1 for every other roster spot still open.</p>
    </div>
  </section>

  <section class="panel" id="panel-setup">
    <div class="card">
      <h2>Tonight's teams</h2>
      <div id="teamEditList"></div>
      <button class="ghost" id="addTeamBtn">+ Add team</button>
    </div>
    <div class="card">
      <h2>League settings</h2>
      <div class="field">
        <label for="budgetPerTeam">Budget per team ($)</label>
        <input type="number" id="budgetPerTeam" min="1">
      </div>
      <div class="field">
        <label for="rosterSize">Roster spots per team</label>
        <input type="number" id="rosterSize" min="1">
      </div>
      <button class="primary" id="applySetupBtn">Apply &amp; start / restart draft</button>
      <p class="hint">Restarting clears logged picks for a fresh draft, but keeps your team list and settings.</p>
    </div>
  </section>

</main>

<div class="toast" id="toast"></div>

<script id="draftData" type="application/json">{data_json}</script>
<script>
(function () {{
  "use strict";
  var DATA = JSON.parse(document.getElementById("draftData").textContent);
  var STORAGE_KEY = "{storage_key}";

  var DEFAULT_TEAMS = {default_teams_json};

  function loadState() {{
    var raw = null;
    try {{ raw = localStorage.getItem(STORAGE_KEY); }} catch (e) {{}}
    if (raw) {{
      try {{ return JSON.parse(raw); }} catch (e) {{}}
    }}
    return {{
      budgetPerTeam: DATA.budget,
      rosterSize: DATA.rosterSize,
      teamNames: DEFAULT_TEAMS.slice(),
      teams: {{}},
      pool: DATA.players.map(function (p) {{ return Object.assign({{ drafted: false }}, p); }}),
      log: []
    }};
  }}

  var state = loadState();
  ensureTeams();

  function ensureTeams() {{
    var next = {{}};
    state.teamNames.forEach(function (name) {{
      next[name] = state.teams[name] || {{ spent: 0, picks: [] }};
    }});
    state.teams = next;
  }}

  function save() {{
    try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }} catch (e) {{}}
  }}

  function totalBudget() {{ return state.teamNames.length * state.budgetPerTeam; }}

  function baselineTotal() {{
    return state.pool.reduce(function (s, p) {{ return s + p.baseline; }}, 0);
  }}
  function baselineDrafted() {{
    return state.pool.filter(function (p) {{ return p.drafted; }}).reduce(function (s, p) {{ return s + p.baseline; }}, 0);
  }}
  function dollarsSpent() {{
    var s = 0;
    Object.keys(state.teams).forEach(function (t) {{ s += state.teams[t].spent; }});
    return s;
  }}
  function inflation() {{
    var remaining = baselineTotal() - baselineDrafted();
    if (remaining <= 0) return 1;
    return (totalBudget() - dollarsSpent()) / remaining;
  }}

  function fmt(n) {{ return "$" + Math.round(n); }}

  function renderInflation() {{
    var infl = inflation();
    document.getElementById("inflationVal").textContent = infl.toFixed(2) + "x";
    var dot = document.getElementById("inflationDot");
    var color = "var(--good)";
    if (infl >= 1.12) color = "var(--danger)";
    else if (infl >= 1.03) color = "var(--warn)";
    dot.style.background = color;
  }}

  var selectedPlayer = null;
  var selectedTeam = state.teamNames[0] || null;

  function renderTeamChips() {{
    var wrap = document.getElementById("teamChips");
    wrap.innerHTML = "";
    state.teamNames.forEach(function (name) {{
      var t = state.teams[name];
      var spotsLeft = state.rosterSize - t.picks.length;
      var chip = document.createElement("button");
      chip.className = "chip" + (name === selectedTeam ? " selected" : "");
      chip.type = "button";
      chip.innerHTML = name + '<span class="sub">$' + Math.round(state.budgetPerTeam - t.spent) + "</span>";
      chip.disabled = spotsLeft <= 0;
      chip.addEventListener("click", function () {{ selectedTeam = name; renderTeamChips(); updateLogButton(); }});
      wrap.appendChild(chip);
    }});
  }}

  function maxBid(name) {{
    var t = state.teams[name];
    var spotsLeft = state.rosterSize - t.picks.length;
    if (spotsLeft <= 0) return 0;
    return Math.max(0, (state.budgetPerTeam - t.spent) - (spotsLeft - 1));
  }}

  function healthClass(name) {{
    var mb = maxBid(name);
    var avg = state.budgetPerTeam / state.rosterSize;
    if (mb <= avg * 0.4) return "danger";
    if (mb <= avg * 0.9) return "warn";
    return "good";
  }}

  function renderSuggest(query) {{
    var box = document.getElementById("suggestList");
    if (!query) {{ box.style.display = "none"; box.innerHTML = ""; return; }}
    var q = query.toLowerCase();
    var infl = inflation();
    var matches = state.pool.filter(function (p) {{
      return !p.drafted && p.name.toLowerCase().indexOf(q) !== -1;
    }}).slice(0, 8);
    if (!matches.length) {{ box.style.display = "none"; box.innerHTML = ""; return; }}
    box.innerHTML = "";
    matches.forEach(function (p) {{
      var row = document.createElement("div");
      row.className = "suggest-row";
      row.innerHTML =
        '<div><div class="nm">' + p.name + '</div><div class="meta">' + p.pos + " " + p.rank + " &middot; base " + fmt(p.baseline) + '</div></div>' +
        '<div class="px mono">' + fmt(p.baseline * infl) + "</div>";
      row.addEventListener("click", function () {{
        selectedPlayer = p;
        document.getElementById("playerSearch").value = p.name;
        box.style.display = "none";
        renderPickedPlayer();
        updateLogButton();
      }});
      box.appendChild(row);
    }});
    box.style.display = "block";
  }}

  function renderPickedPlayer() {{
    var wrap = document.getElementById("pickedPlayerWrap");
    if (!selectedPlayer) {{ wrap.innerHTML = ""; return; }}
    var infl = inflation();
    wrap.innerHTML =
      '<div class="picked-player"><div><div class="nm">' + selectedPlayer.name + '</div><div class="meta">' +
      selectedPlayer.pos + " " + selectedPlayer.rank + " &middot; base " + fmt(selectedPlayer.baseline) +
      '</div></div><div class="suggested"><div class="amt mono">' + fmt(selectedPlayer.baseline * infl) +
      '</div><div class="lbl">suggested max</div></div></div>';
  }}

  function updateLogButton() {{
    var btn = document.getElementById("logPickBtn");
    var price = parseFloat(document.getElementById("priceInput").value);
    btn.disabled = !(selectedPlayer && selectedTeam && price > 0);
  }}

  function showToast(msg) {{
    var t = document.getElementById("toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(showToast._h);
    showToast._h = setTimeout(function () {{ t.classList.remove("show"); }}, 1800);
  }}

  function logPick() {{
    var price = parseFloat(document.getElementById("priceInput").value);
    if (!selectedPlayer || !selectedTeam || !(price > 0)) return;
    selectedPlayer.drafted = true;
    var t = state.teams[selectedTeam];
    t.spent += price;
    t.picks.push(selectedPlayer.name);
    state.log.push({{ name: selectedPlayer.name, pos: selectedPlayer.pos, team: selectedTeam, price: price, baseline: selectedPlayer.baseline }});
    save();
    showToast(selectedPlayer.name + " → " + selectedTeam + " for " + fmt(price));
    selectedPlayer = null;
    document.getElementById("playerSearch").value = "";
    document.getElementById("priceInput").value = "";
    renderAll();
  }}

  function undoLast() {{
    var entry = state.log.pop();
    if (!entry) return;
    var t = state.teams[entry.team];
    t.spent -= entry.price;
    var idx = t.picks.lastIndexOf(entry.name);
    if (idx !== -1) t.picks.splice(idx, 1);
    var p = state.pool.filter(function (pl) {{ return pl.name === entry.name; }})[0];
    if (p) p.drafted = false;
    save();
    showToast("Undid " + entry.name);
    renderAll();
  }}

  function renderRecent() {{
    var card = document.getElementById("recentCard");
    var wrap = document.getElementById("recentLog");
    if (!state.log.length) {{ card.style.display = "none"; document.getElementById("undoBtn").style.display = "none"; return; }}
    card.style.display = "block";
    document.getElementById("undoBtn").style.display = "block";
    var recent = state.log.slice(-8).reverse();
    wrap.innerHTML = "";
    recent.forEach(function (e) {{
      var row = document.createElement("div");
      row.className = "log-row";
      row.innerHTML = '<div><span class="nm">' + e.name + '</span> <span class="to">→ ' + e.team + '</span></div><div class="amt mono">' + fmt(e.price) + "</div>";
      wrap.appendChild(row);
    }});
  }}

  var currentPosFilter = "ALL";
  function renderPosFilter() {{
    var wrap = document.getElementById("posFilter");
    var positions = ["ALL", "QB", "RB", "WR", "TE", "DEF"];
    wrap.innerHTML = "";
    positions.forEach(function (pos) {{
      var b = document.createElement("button");
      b.textContent = pos;
      b.className = pos === currentPosFilter ? "active" : "";
      b.addEventListener("click", function () {{ currentPosFilter = pos; renderBoard(); }});
      wrap.appendChild(b);
    }});
  }}

  function renderBoard() {{
    renderPosFilter();
    var infl = inflation();
    var body = document.getElementById("boardBody");
    var rows = state.pool.filter(function (p) {{ return !p.drafted && (currentPosFilter === "ALL" || p.pos === currentPosFilter); }});
    rows.sort(function (a, b) {{ return (b.baseline * infl) - (a.baseline * infl); }});
    rows = rows.slice(0, 60);
    body.innerHTML = "";
    if (!rows.length) {{
      body.innerHTML = '<tr><td colspan="3" class="empty">Nobody left at this position.</td></tr>';
      return;
    }}
    rows.forEach(function (p) {{
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + p.name + '<span class="pos-tag">' + p.pos + "</span></td>" +
        '<td class="num mono">' + fmt(p.baseline) + "</td>" +
        '<td class="num mono px">' + fmt(p.baseline * infl) + "</td>";
      body.appendChild(tr);
    }});
  }}

  function renderBudgets() {{
    var wrap = document.getElementById("budgetScroll");
    wrap.innerHTML = "";
    var names = state.teamNames.slice().sort(function (a, b) {{ return maxBid(b) - maxBid(a); }});
    names.forEach(function (name) {{
      var t = state.teams[name];
      var spotsLeft = state.rosterSize - t.picks.length;
      var h = healthClass(name);
      var card = document.createElement("div");
      card.className = "budget-card health-" + h;
      card.innerHTML =
        '<div class="nm">' + name + "</div>" +
        '<div class="row"><span>Left</span><span class="v">' + fmt(state.budgetPerTeam - t.spent) + "</span></div>" +
        '<div class="row"><span>Spots</span><span class="v">' + spotsLeft + "</span></div>" +
        '<div class="row"><span>Max bid</span><span class="v">' + fmt(maxBid(name)) + "</span></div>" +
        '<span class="pill health-' + h + '">' + (h === "good" ? "healthy" : h === "warn" ? "tightening" : "capped") + "</span>";
      wrap.appendChild(card);
    }});
  }}

  function renderTeamEditList() {{
    var wrap = document.getElementById("teamEditList");
    wrap.innerHTML = "";
    state.teamNames.forEach(function (name, i) {{
      var row = document.createElement("div");
      row.className = "team-edit-row";
      row.innerHTML = '<input type="text" value="' + name.replace(/"/g, "&quot;") + '" data-idx="' + i + '">' +
        '<button class="rm" type="button" data-idx="' + i + '">×</button>';
      wrap.appendChild(row);
    }});
    wrap.querySelectorAll("input").forEach(function (inp) {{
      inp.addEventListener("change", function () {{
        state.teamNames[parseInt(inp.getAttribute("data-idx"), 10)] = inp.value.trim() || "Team";
      }});
    }});
    wrap.querySelectorAll("button.rm").forEach(function (btn) {{
      btn.addEventListener("click", function () {{
        state.teamNames.splice(parseInt(btn.getAttribute("data-idx"), 10), 1);
        renderTeamEditList();
      }});
    }});
  }}

  function renderAll() {{
    renderInflation();
    renderTeamChips();
    renderRecent();
    renderBoard();
    renderBudgets();
    updateLogButton();
  }}

  document.querySelectorAll("nav.tabs button").forEach(function (b) {{
    b.addEventListener("click", function () {{
      document.querySelectorAll("nav.tabs button").forEach(function (x) {{ x.classList.remove("active"); }});
      document.querySelectorAll(".panel").forEach(function (x) {{ x.classList.remove("active"); }});
      b.classList.add("active");
      document.getElementById("panel-" + b.getAttribute("data-panel")).classList.add("active");
    }});
  }});

  document.getElementById("playerSearch").addEventListener("input", function (e) {{
    if (selectedPlayer && e.target.value !== selectedPlayer.name) selectedPlayer = null;
    renderSuggest(e.target.value);
    updateLogButton();
  }});
  document.getElementById("priceInput").addEventListener("input", updateLogButton);
  document.getElementById("logPickBtn").addEventListener("click", logPick);
  document.getElementById("undoBtn").addEventListener("click", undoLast);
  document.getElementById("addTeamBtn").addEventListener("click", function () {{
    state.teamNames.push("New team");
    renderTeamEditList();
  }});
  document.getElementById("applySetupBtn").addEventListener("click", function () {{
    state.budgetPerTeam = parseFloat(document.getElementById("budgetPerTeam").value) || DATA.budget;
    state.rosterSize = parseInt(document.getElementById("rosterSize").value, 10) || DATA.rosterSize;
    state.pool = DATA.players.map(function (p) {{ return Object.assign({{ drafted: false }}, p); }});
    state.log = [];
    ensureTeams();
    Object.keys(state.teams).forEach(function (k) {{ state.teams[k] = {{ spent: 0, picks: [] }}; }});
    selectedTeam = state.teamNames[0] || null;
    save();
    showToast("Draft reset with " + state.teamNames.length + " teams.");
    renderAll();
    document.querySelector('nav.tabs button[data-panel="draft"]').click();
  }});

  document.getElementById("budgetPerTeam").value = state.budgetPerTeam;
  document.getElementById("rosterSize").value = state.rosterSize;
  renderTeamEditList();
  renderAll();
}})();
</script>
"""


def generate_html(
    curve: pd.DataFrame,
    projections: pd.DataFrame,
    num_teams: int,
    budget_per_team: float,
    roster_size: int,
    team_names: list[str],
    title: str = "Draft Assistant",
    eyebrow: str = "Live Draft Assistant",
    storage_key: str = "draft-assistant-v1",
) -> str:
    total_budget = num_teams * budget_per_team
    players = []
    for _, row in projections.iterrows():
        bv = baseline_value(curve, row["position"], int(row["projected_rank"]), total_budget)
        players.append({"name": row["player_name"], "pos": row["position"], "rank": int(row["projected_rank"]), "baseline": bv})
    players.sort(key=lambda p: -p["baseline"])

    data = {"players": players, "budget": budget_per_team, "rosterSize": roster_size}
    return TEMPLATE.format(
        title=title,
        eyebrow=eyebrow,
        data_json=json.dumps(data),
        storage_key=storage_key,
        default_teams_json=json.dumps(team_names),
    )
