# Rivals FCL 2026 Draft Grades

19-round, 16-team snake draft, real 304 picks logged live via the Rivals Draft
Helper export feature. Grades computed from `data/rivals/2026.csv` (this
project's own VOR model) joined to the real draft log
(`data/rivals/draft_results_2026.csv`), using `draft_helper.rivals.mock_draft
.optimal_lineup_points` for each team's real best-starting-lineup point total
(the same methodology the mock-draft slot-advantage section of
`strategy_report_2026.html` already uses) -- not a raw bench-sum, which would
overstate teams that simply drafted more bodies.

"Market value" below uses real sourced ADP (`market_overall_pick`) where it
exists, excluding K (external ADP is calibrated to shallower drafts than this
league's 19 rounds, so kicker "value" numbers are a scaling artifact, not a
real signal -- every team in the league drafted a K in rounds 13-19, so it's
not a differentiator). IDP has no real public ADP to compare against at all,
so IDP picks are excluded from the value number and judged on roster
construction/bye risk instead.

## League-wide grades

| Rank | Team | Optimal Starting Pts | Grade | Note |
|---|---|---|---|---|
| 1 | **Calculated chaos (you)** | 1253.6 | **A** | Best in the league; only 1 player on the Wk11 championship bye |
| 2 | The Leviathan | 1181.4 | A | Strong core, 3 players on the Wk11 bye |
| 3 | Spokane Jackalopes | 1084.2 | A- | Deep, well-rounded |
| 4 | SD Boyz | 1102.9 | A- | Elite RB1 anchors it |
| 5 | Welcome To The Big Show | 1139.7 | B+ | High points but overpaid across the board (worst market value in the league) |
| 6 | Legion of Worst | 1021.7 | B+ | Best real-market value in the league (+27, only positive team), modest ceiling |
| 7 | WashMo | 1071.4 | B | Solid, unspectacular |
| 8 | Church of Gronk | 1073.9 | B | RB-heavy (7 RBs), thin at WR |
| 9 | A.I see what you done there? | 1029.7 | B- | Good value, modest ceiling |
| 10 | Favre Dolar Footlong | 1029.8 | B- | Reasonable, unremarkable |
| 11 | Southeastern FL | 1028.9 | C+ | 6 players on the Wk11 bye -- real landmine risk |
| 12 | RigoRigo | 978.7 | C+ | Good value-hunting, ceiling too low |
| 13 | The Jaxsen Tyus's | 994.5 | C | Middling everywhere |
| 14 | GeetheWhiz | 955.7 | C | Lowest points in the league |
| 15 | MMFFL | 965.4 | C- | 6 players on the Wk11 bye, low ceiling |
| 16 | Steely | 991.2 | C- | 8 players on the Wk11 championship bye -- worst landmine exposure in the league |

## Calculated Chaos (your team) -- pick by pick

| Rd | Player | Pos | Note |
|---|---|---|---|
| 1 | CeeDee Lamb | WR | Correct -- market price, no discount, no reach |
| 2 | Trey McBride | TE | Excellent -- elite TE at true TE1 value |
| 3 | Lamar Jackson | QB | The one real debate: paid full price 3 rounds before most of the league moved on QB. Justified given this format's real QB scoring weight, but the single biggest swing decision on the board |
| 4 | Marvin Harrison Jr. | WR | Fine value, real WR2 |
| 5 | Alec Pierce | WR | Slight reach, low-impact bench WR |
| 6 | Jordyn Brooks | LB | Real IDP anchor, correctly early for this scoring system |
| 7 | Rico Dowdle | RB | Committee back, not a true lead role |
| 8 | Jeffery Simmons | DL | Solid IDP value |
| 9 | Jake Ferguson | TE2 | Low-value duplicate -- TE was already solved in round 2 |
| 10 | Kenneth Gainwell | RB | Depth, not a real role |
| 11 | Jeremy Chinn | DB | Fine IDP floor |
| 12 | Jamien Sherwood | LB2 | Real tackle-volume value, but 3rd LB wasn't the bottleneck |
| 13 | Baker Mayfield | QB2 | Unnecessary given an elite locked-in QB1 -- should've gone to RB depth |
| 14 | Evan McPherson | K | Normal timing |
| 15 | Jalen Carter | DL2 | Fine depth |
| 16 | Devaughn Vele | WR | Low-impact bench |
| 17 | Ted Hurst III | WR | Real late-camp-helium flier |
| 18 | Chris Brooks | RB | Real, verified Packers RB2 role (live in-draft fix) |
| 19 | Marlon Humphrey | DB | Legit starting corner, zero injury risk |

## Trade: Rd 4+ slot swap with Legion of Worst

No clean winner. Legion of Worst ended up with the best real-market-value
board in the league (+27 vs. real ADP, the only team to finish positive) but
a modest 1,021.7-point ceiling. Calculated Chaos ended up with the single
most points-productive roster in the league. Different currencies, both
real -- in a bracket format where Weeks 9-12 count 1.5x and ceiling matters
more than draft-capital efficiency, call this a net win for Calculated Chaos.

## What could have been better (Calculated Chaos)

1. **RB depth is the real soft spot.** Three total RBs (Dowdle, Gainwell,
   Brooks), none a clear lead role -- all committee/change-of-pace types.
   RB wins the flex ~50% of the time in this format, so that's thin. Round
   13 (Baker Mayfield, an unneeded QB2) is the pick that should have gone to
   a 4th, more clearly-defined RB.
2. **Jake Ferguson at TE2** (round 9) was low-value -- TE was already solved
   with McBride in round 2.
3. Everything else holds up -- several late picks (Chris Brooks, Marlon
   Humphrey) exist directly because of live data corrections made during the
   draft itself.

**First waiver priority once the season starts: a 4th real RB**, especially
if Dowdle or Gainwell underperform early.
