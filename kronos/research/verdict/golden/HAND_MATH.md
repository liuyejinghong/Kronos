# Golden Cases — Hand-Computed Arithmetic (P02, v0.5.0 M0)

This document is the **independence guarantee** for the golden cases in
`cases/*.json` and `expected/*.json`: every expected number below is derived by
explicit step-by-step arithmetic that another engineer can re-compute with a
calculator and the frozen rules in `kronos/strategy/variant_rules.py` +
`kronos/strategy/spec.py`. No implementation was run to produce any expected
value. Cases G01–G11 cover the v0.5.0 M0 matrix: first long/short entry,
day-end flat, no same-bar reversal, warmup block, fee flip, funding boundary
before/after settlement, parameter-activated and parameter-inactive multiplier
changes, and end-of-data open position.

> **Cost-convention ruling (Lead, 2026-09-27).** The original draft of this
> package applied `fill = raw open x (1 +- 9bps)` plus a separate 4bps fee
> (the P02 brief's mechanics sentence, which double-counted the fee). The Lead
> ruled the canonical semantics are: **slippage 5bps in the price ONLY
> (`x (1 +- 0.0005)`), fee 4bps of fill notional charged separately** — all-in
> ~9bps per side. ALL numbers in this revision use the canonical convention,
> and G06's day-end close was rebalanced 60210 -> 60200 (see §3 G06) because
> the old move no longer flips to net-negative under canonical costs. Trade
> structures are unchanged.

---

## 1. Global conventions (identical in every case)

### 1.1 Time base

- Base day D0 = 2026-06-01T00:00:00Z = `1780272000000` ms.
- Day 1 D1 = 2026-06-02T00:00:00Z = `1780358400000` ms; Day 2 D2 = `1780444800000` ms.
- 15m grid: 96 bars/UTC day; bar `j` of a day opens at `day_start + j*900000`
  and closes at `day_start + (j+1)*900000`. Global 15m index `i` = day offset
  within the fixture; day-0 bars are indices 0–95, day-1 bars 96–191.
- `ts_ms` in the JSON is the bar OPEN time. A signal on the bar closing at time
  `T` is filled at the 1m bar opening at `T` (its `ts_ms` equals `T`).

### 1.2 Bar construction (zero-gap, two shapes)

Every bar opens exactly at the previous bar's close (zero-gap). Only two bar
shapes occur:

- **Standard bar `S(p)`**: `o = c = p`, `h = p + 50`, `l = p - 50`.
  TR `= max(100, |p+50-p|, |p-50-p|) = 100` (range carried by the wicks).
- **Body bar `B(o, c)`**: no wicks, `h = max(o,c)`, `l = min(o,c)`.
  TR `= max(|c-o|, |max(o,c)-p|, |min(o,c)-p|) = |c - o|` because `p` (previous
  close) equals `o` under zero-gap.

Consequence: **TR is 100 for every standard bar and equals the bar's absolute
move for every body bar.** All ATRs below are means of two or three explicit TR
values.

Day 0 (identical in ALL cases): 96 standard bars at p=60000.

- `TR[0] = h - l = 60050 - 59950 = 100` (no previous close; first-bar
  convention `TR = H - L`). `TR[1..95] = 100` each.
- Day-0 extremes: `H0 = 60050`, `L0 = 59950`, `C0 = 60000`.
- **Pivot for every day-1 decision bar** `= (H0 + L0 + C0)/3 = 180000/3 = 60000.0`.

A pivot is always built from the PREVIOUS COMPLETE UTC day, so it is constant
within a day. Day-2 pivots are derived per case in §3.

### 1.3 Score, ATR, warmup, decisions (frozen rules)

- `TR[i] = max(H-L, |H - prev_close|, |L - prev_close|)`; `TR[0] = H0 - L0`.
- `ATR(i) = mean(TR[i-atr_period+1 .. i])` (trailing `atr_period` completed
  bars, including bar `i`). Cases use `atr_period = 2` (G10: 3).
- `q = (close - pivot_prev_day) / (ATR * volatility_multiplier)`, evaluated on
  COMPLETED 15m bars only.
- Warmup = 96 + atr_period completed bars. With atr_period=2 the first decision
  bar is global index 98; with atr_period=3 it is index 99.
- Entries (only while flat): `q >= +1` open long, `q <= -1` open short
  (thresholds inclusive). Exits (only while holding): long `q <= 0`,
  short `q >= 0`; warmup bars (`q` undefined) never exit.
- Day-end bar (the 15m bar closing at 24:00, i.e. 23:45–00:00): force-close any
  position and take NO new entries, even if |q| >= 1.
- No same-bar reversal: a bar that exits a position cannot open the opposite
  one; entries are only evaluated while flat at bar start.

### 1.4 Fills and costs (CANONICAL, per Lead ruling 2026-09-27)

- Fill = NEXT AVAILABLE 1m bar open at/after the signal close. In these
  fixtures the 1m bar opening exactly at the signal close is always present and
  its raw open equals the signal bar's close (zero-gap).
- **Fill price = raw 1m open adjusted adversely by slippage 5bps ONLY**:
  buy at `open * (1 + 0.0005)`, sell at `open * (1 - 0.0005)`.
- **Fee = `0.0004 * qty * fill_price`** (fee_bps 4 of the notional at the
  adjusted fill), charged as its own `fee` ledger event at the fill ts. The fee
  is NOT compounded into the fill price.
- All-in cost ≈ 9bps per side (5bps slippage in price + 4bps fee),
  ≈ 18bps round trip.
- Quantity: `qty = equity_at_entry / fill_price`, **rounded to 6 decimals**;
  the ROUNDED quantity is used in every downstream number.
- Rounding: every published value is rounded to 6 decimals; derived values
  (net_pnl, totals, equity) are computed from the already-rounded published
  components, so summing the JSON numbers reproduces them exactly.

### 1.5 Funding

- Funding applies only at the `funding_events` instants declared in the case
  file (8h grid timestamps are used: 08:00 = `1780387200000`,
  16:00 = `1780416000000` on day 1).
- If a position is open at a settlement instant `ts`:
  `funding = rate * qty * ref_price * direction`, where `direction = +1` long /
  `-1` short (a long PAYS a positive rate) and `ref_price` = the close of the
  last COMPLETED 15m bar at or before `ts` (fixture convention, documented in
  the loader docstring).
- Funding hits equity immediately at `ts` and is attributed to the open trade's
  `total_fees` (sign-aware: received funding is a negative cost).

### 1.6 Equity trail and ledger event templates

Event stream per trade (field names = `contracts.ExecutionRecord`):

1. `order` at signal-close ts: `side`, `note` (decision + q value).
2. `fill` at fill ts: `side`, `qty`, `price` (adjusted fill price).
3. `fee` at fill ts: `fee` (4bps of fill notional), `fee_asset="USDT"`.
4. `position_open` (entry only): `side`, `qty`, `price`, `equity`, `note`.
5. `funding` (per settlement while open): `funding_rate`, `fee` (positive =
   paid), `equity`, `note`.
6. `position_close` (exit): `side`, `realized_pnl` (= the trade's `net_pnl`),
   `equity`, `note` (= exit reason).
7. `equity_mark` (only G11): `unrealized_pnl`, `equity`, `note`.

Equity semantics (all equity fields are true cash-equity marks at their ts):

- `fee` and `funding` events deduct immediately.
- `position_open.equity` = equity after the entry fee (first trade: `10000 -
  fee_entry`).
- `position_close.equity` = `10000 + sum(net_pnl of all closed trades)` — the
  close's cash increment is the trade's GROSS pnl (its fees were already
  charged as events).
- `equity_mark.equity` (G11) = cash equity plus the unrealized mark.
- Invariant (checked by the unit tests): `final_equity = 10000 + Σ net_pnl`.

`holding_bars` = (exit signal bar global 15m index) − (entry signal bar global
index). A `day_end_flat` exit's signal bar is the day-end bar (index 191 for a
day-1 exit).

### 1.7 Comparison tolerance

Golden comparisons should use absolute tolerance `1e-6` (all published values
are 6-decimal rounded).

---

## 2. Shared day-0 arithmetic (all cases)

- 96 standard bars `S(60000)`: each bar is `o=c=60000`, `h=60050`, `l=59950`.
- `TR[0] = 60050 - 59950 = 100`; for `i >= 1`:
  `TR[i] = max(100, |60050-60000|, |59950-60000|) = 100`.
- Day-0 `H/L/C = 60050/59950/60000` → `pivot(day1) = 60000.0`.
- Warmup for atr_period=2: bars 0..97 (96 + 2); first decision bar index 98.
  Warmup for atr_period=3 (G10): bars 0..98; first decision bar index 99.

With ATR staying 100 whenever the trailing two TRs are both 100,
`q = (close - 60000)/100` on day 1: **q = number of hundreds the close sits
above the pivot.**

### 2.1 Canonical fill prices (slippage 5bps, `x (1 ± 0.0005)`)

| raw 1m open | side | fill price |
|---|---|---|
| 60100 | buy | `60100 * 1.0005 = 60130.05` |
| 59900 | sell | `59900 * 0.9995 = 59870.05` |
| 60000 | sell | `60000 * 0.9995 = 59970.00` |
| 60000 | buy | `60000 * 1.0005 = 60030.00` |
| 58800 | sell | `58800 * 0.9995 = 58770.60` |
| 58700 | sell | `58700 * 0.9995 = 58670.65` |
| 60200 | sell | `60200 * 0.9995 = 60169.90` |
| 60100 (G03 day-2 exit) | sell | `60100 * 0.9995 = 60069.95` |

Shared long entry at equity 10000 (G01/G03/G04-T1/G06/G07/G08/G10/G11):
`qty = 10000 / 60130.05 = 0.166306198...` → **0.166306** (6dp);
notional `0.166306 * 60130.05 = 9999.988095` → entry fee
`0.0004 * 9999.988095 = 3.999995`; `position_open.equity = 9996.000005`.

---

## 3. Per-case arithmetic

### G01 — first entry long (atr_period=2, m=1.0, no funding)

Day-1 bars (global index / day-1 j): j0–j6 `S(60000)`; j7 `B(60000,60100)`;
j8–j9 `S(60100)`; j10 `B(60100,60000)`; j11–j95 `S(60000)`.

| idx (global/j) | bar o→c | TR | ATR = (TR[i-1]+TR[i])/2 | q = (c-60000)/ATR | decision |
|---|---|---|---|---|---|
| 98 / j2 | 60000→60000 | 100 | 100 | 0.0 | flat, hold |
| 99–102 / j3–j6 | 60000→60000 | 100 | 100 | 0.0 | flat, hold |
| 103 / j7 | 60000→60100 | 100 | 100 | **1.0** | q >= +1 → open_long |
| 104 / j8 | 60100→60100 | 100 | 100 | 1.0 | long, q > 0 → hold |
| 105 / j9 | 60100→60100 | 100 | 100 | 1.0 | long, q > 0 → hold |
| 106 / j10 | 60100→60000 | 100 | 100 | **0.0** | long, q <= 0 → exit |
| 107+ / j11+ | 60000→60000 | 100 | 100 | 0.0 | flat, hold (no re-entry) |

TR details: j7 `B(60000,60100)`: `max(100, |60100-60000|, |60000-60000|) = 100`;
j10 `B(60100,60000)`: `max(100, 0, 100) = 100`; j8 `S(60100)`:
`max(100, 50, 50) = 100`.

Money math:

1. Entry signal closes 02:00 → ts `D1+7200000 = 1780365600000`. Buy fill
   60130.05, qty 0.166306, entry fee 3.999995 (shared entry, §2.1).
2. Exit signal closes 02:45 → ts `1780368300000`. Raw 1m open = 60000.
   Sell fill `60000 * 0.9995 = 59970.00`.
   Notional `0.166306 * 59970.00 = 9973.370820` → exit fee `3.989348`.
3. `gross_pnl = 0.166306 * (59970.00 - 60130.05) = 0.166306 * (-160.05)
   = -26.617275`.
4. `total_fees = 3.999995 + 3.989348 = 7.989343`;
   `net_pnl = -26.617275 - 7.989343 = -34.606618`.
5. `final_equity = 10000 - 34.606618 = 9965.393382`;
   `position_close.equity = 9965.393382`.
6. `holding_bars = 106 - 103 = 3`; `exit_reason = signal_exit`.

### G02 — first entry short (mirror of G01)

Day-1: j7 `B(60000,59900)`; j8 `B(59900,59850)`; j9 `B(59850,59900)`;
j10 `B(59900,60000)`; else standard.

| idx | bar o→c | TR | ATR | q | decision |
|---|---|---|---|---|---|
| 103 / j7 | 60000→59900 | 100 | 100 | **-1.0** | q <= -1 → open_short |
| 104 / j8 | 59900→59850 | 50 | (100+50)/2 = 75 | (59850-60000)/75 = **-2.0** | short, q < 0 → hold |
| 105 / j9 | 59850→59900 | 50 | (50+50)/2 = 50 | (59900-60000)/50 = **-2.0** | short, q < 0 → hold |
| 106 / j10 | 59900→60000 | 100 | (50+100)/2 = 75 | 0/75 = **0.0** | short, q >= 0 → exit |

TR details: j8 `max(50, |59850-59900|, 0) = 50`; j9 `max(50, 0, 50) = 50`;
j10 `max(100, 100, 0) = 100`.

Money math:

1. Entry (02:00, ts 1780365600000): sell fill
   `59900 * 0.9995 = 59900 - 29.95 = 59870.05`.
2. `qty = 10000 / 59870.05 = 0.167028...` (exact 0.16702842) → **0.167028**.
   Notional `0.167028 * 59870.05 = 9999.974711` → entry fee `3.999990`;
   `position_open.equity = 9996.000010`.
3. Exit (02:45): buy fill `60000 * 1.0005 = 60030.00`. Notional
   `0.167028 * 60030.00 = 10026.690840` → exit fee `4.010676`.
4. `gross_pnl = qty * (entry_fill - exit_fill) = 0.167028 * (59870.05 -
   60030.00) = 0.167028 * (-159.95) = -26.716129`.
5. `total_fees = 3.999990 + 4.010676 = 8.010666`;
   `net_pnl = -26.716129 - 8.010666 = -34.726795`.
6. `final_equity = 10000 - 34.726795 = 9965.273205`.
7. `holding_bars = 3`; `exit_reason = signal_exit`.

### G03 — day-end flat

Day-1: j4 `B(60000,60100)`; j5–j95 `S(60100)`; day-2 j0–j3 (idx 192–195)
`S(60100)`.

| idx | bar | TR | ATR | q | decision |
|---|---|---|---|---|---|
| 100 / j4 | 60000→60100 | 100 | 100 | **1.0** | flat → open_long |
| 101–191 / j5–j95 | 60100→60100 | 100 | 100 | 1.0 | long, q > 0 → hold |
| 191 / j95 (day-end) | 60100→60100 | 100 | 100 | 1.0 | **force close (day_end_flat)**, no entry |
| 192–195 (day 2) | 60100→60100 | 100 | 100 | 0.333333 | flat, hold |

Day-2 pivot: day-1 `H1 = 60150` (wick of S(60100)), `L1 = 59950`, `C1 = 60100`
→ `(60150+59950+60100)/3 = 180200/3 = 60066.666667`;
q(day2) `= (60100 - 60066.666667)/100 = 0.333333 < 1` → no entry.

Money math:

1. Entry signal closes 01:15 → ts `1780362900000`. Buy fill 60130.05, qty
   0.166306, entry fee 3.999995 (shared entry, §2.1).
2. Exit signal = day-end bar j95, closing at `D2 00:00 = 1780444800000`.
   Fill at the FIRST 1m open of day 2 (raw 60100): sell fill
   `60100 * 0.9995 = 60100 - 30.05 = 60069.95`.
   Notional `0.166306 * 60069.95 = 9978.36 + 0.166306 * 69.95 = 9978.36 +
   11.633105 = 9989.993105` → exit fee `3.995997`.
3. `gross_pnl = 0.166306 * (60069.95 - 60130.05) = 0.166306 * (-60.10)
   = -9.994991`.
4. `total_fees = 3.999995 + 3.995997 = 7.995992`;
   `net_pnl = -9.994991 - 7.995992 = -17.990983`.
5. `final_equity = 9982.009017`. `holding_bars = 191 - 100 = 91`.
6. Note: the force-close fires although q = +1.0 > 0 (day-end rule wins), and
   the day-end bar takes no entries.

### G04 — no same-bar reversal (2 trades)

Day-1: j2 `B(60000,60100)`; j3–j6 `S(60100)`; j7 `B(60100,58800)`;
j8 `B(58800,58700)`; j9 `B(58700,58750)`; j10 `B(58750,60100)`;
j11 `B(60100,60050)`; j12+ `S(60050)`.

| idx | bar o→c | TR | ATR | q | decision |
|---|---|---|---|---|---|
| 98 / j2 | 60000→60100 | 100 | 100 | **1.0** | flat → open_long (T1) |
| 99–102 / j3–j6 | 60100→60100 | 100 | 100 | 1.0 | long, hold |
| 103 / j7 | 60100→58800 | 1300 | (100+1300)/2 = 700 | (58800-60000)/700 = **-1.714286** | long + q <= -1: EXIT ONLY (no reversal) |
| 104 / j8 | 58800→58700 | 100 | (1300+100)/2 = 700 | (58700-60000)/700 = **-1.857143** | FLAT → open_short (T2) |
| 105 / j9 | 58700→58750 | 50 | (100+50)/2 = 75 | (58750-60000)/75 = -16.666667 | short, q < 0 → hold |
| 106 / j10 | 58750→60100 | 1350 | (50+1350)/2 = 700 | (60100-60000)/700 = **0.142857** | short, q >= 0 → exit (T2) |
| 107 / j11 | 60100→60050 | 50 | (1350+50)/2 = 700 | 50/700 = 0.071429 | flat, hold |
| 108 / j12 | S(60050) | 100 | (50+100)/2 = 75 | 50/75 = 0.666667 | flat, hold |
| 109+ / j13+ | S(60050) | 100 | 100 | 0.5 | flat, hold |

Money math trade 1:

1. Entry closes 00:45 → ts `1780361100000`. Buy fill 60130.05, qty 0.166306,
   fee 3.999995 (shared entry, §2.1).
2. Exit closes 02:00 → ts `1780365600000`. Raw open 58800 → sell fill
   `58800 * 0.9995 = 58800 - 29.40 = 58770.60`. Notional
   `0.166306 * 58770.60 = 9773.903404` → exit fee `3.909561`.
3. `gross = 0.166306 * (58770.60 - 60130.05) = 0.166306 * (-1359.45)
   = -226.084692`. `total_fees = 3.999995 + 3.909561 = 7.909556`.
   `net = -226.084692 - 7.909556 = -233.994248`.
   `position_close.equity = 10000 - 233.994248 = 9766.005752`.
   `holding_bars = 103 - 98 = 5`.

Money math trade 2:

1. Entry equity = 9766.005752. Entry closes 02:15 → ts `1780366500000`.
   Raw open 58700 → sell fill `58700 * 0.9995 = 58700 - 29.35 = 58670.65`.
2. `qty2 = 9766.005752 / 58670.65 = 0.166454...` (exact 0.16645471) →
   **0.166455**. Notional `0.166455 * 58670.65 = 9766.023046` → entry fee
   `3.906409`; `position_open.equity = 9766.005752 - 3.906409 = 9762.099343`.
3. Exit closes 02:45 → ts `1780368300000`. Raw open 60100 → buy fill 60130.05.
   Notional `0.166455 * 60130.05 = 10008.947473` → exit fee `4.003579`.
4. `gross = 0.166455 * (58670.65 - 60130.05) = 0.166455 * (-1459.40)
   = -242.924427`. `total_fees = 3.906409 + 4.003579 = 7.909988`.
   `net = -242.924427 - 7.909988 = -250.834415`.
5. `final_equity = 9766.005752 - 250.834415 = 9515.171337`.
   `holding_bars = 106 - 104 = 2`.

Key assertion: exactly 2 trades; the crash bar closed the long but did NOT open
the short on the same bar.

### G05 — warmup blocked (zero trades)

Day-1: j0 `B(60000,60300)` (spike); j1 `B(60300,60100)`; j2 `B(60100,60000)`;
j3 `B(60000,60050)`; j4+ `S(60050)`.

- Warmup = 96 + 2 = 98 → decisions start at global index 98. Bars 96 (j0) and
  97 (j1) are NEVER decided.
- Would-be q at j0 (proof the move was signal-worthy):
  `TR[j0] = |60300-60000| = 300`; would-be `ATR = (100 + 300)/2 = 200`;
  would-be `q = (60300-60000)/200 = 1.5 >= 1` — **blocked by warmup**.
  (j1 would-be: `TR = 200`, `ATR = (300+200)/2 = 250`, `q = 100/250 = 0.4` —
  also inside warmup.)
- Decision bars:

| idx | bar o→c | TR | ATR | q | decision |
|---|---|---|---|---|---|
| 98 / j2 | 60100→60000 | 100 | (200+100)/2 = 150 | 0/150 = **0.0** | flat, hold |
| 99 / j3 | 60000→60050 | 50 | (100+50)/2 = 75 | 50/75 = **0.666667** | flat, hold |
| 100 / j4 | S(60050) | 100 | (50+100)/2 = 75 | 50/75 = **0.666667** | flat, hold |
| 101+ / j5+ | S(60050) | 100 | 100 | 0.5 | flat, hold |

All |q| < 1 → no entry; never holding → no exit. **Zero trades,
final_equity = 10000.0, ledger_events = [].**

### G06 — fee flip (gross > 0, net < 0)

Day-1: j8 `B(60000,60100)`; j9–j94 `S(60100)`; j95 `B(60100,60200)` (day-end
bar); day-2 j0–j3 (idx 192–195) `S(60200)`.

**Rebalance note (Lead ruling 2026-09-27):** under canonical costs (5bps
slippage + 4bps fee, ~18bps round trip) the original day-end close 60210
produced net +0.29 — no longer a flip. The day-end close was rebalanced to
60200 (raw move +100) so the case still barely flips; trade structure,
timestamps and q values are unchanged (q at j95 is still exactly 2.0).

| idx | bar | TR | ATR | q | decision |
|---|---|---|---|---|---|
| 104 / j8 | 60000→60100 | 100 | 100 | **1.0** | flat → open_long |
| 105–190 / j9–j94 | 60100→60100 | 100 | 100 | 1.0 | long, hold |
| 191 / j95 (day-end) | 60100→60200 | 100 | 100 | (60200-60000)/100 = **2.0** | day-end: entry IGNORED, force close |
| 192 / day2 j0 | S(60200) | 100 | 100 | 0.833333 | flat, hold |

Day-2 pivot: `H1 = 60200`, `L1 = 59950`, `C1 = 60200` →
`(60200+59950+60200)/3 = 180350/3 = 60116.666667`;
q(day2) `= (60200 - 60116.666667)/100 = 83.333333/100 = 0.833333 < 1` → no
entry (TR[191] = 100, so ATR[192] = 100).

Money math:

1. Entry closes 02:15 → ts `1780366500000`. Buy fill 60130.05, qty 0.166306,
   entry fee 3.999995.
2. Exit = day-end force close into the day-2 first 1m open (ts 1780444800000,
   raw 60200): sell fill `60200 * 0.9995 = 60200 - 30.10 = 60169.90`.
   Notional `0.166306 * 60169.90 = 10006.615389` → exit fee `4.002646`.
3. `gross_pnl = 0.166306 * (60169.90 - 60130.05) = 0.166306 * 39.85
   = +6.627294` — **positive**.
4. `total_fees = 3.999995 + 4.002646 = 8.002641`;
   `net_pnl = 6.627294 - 8.002641 = -1.375347` — **negative**: the ~18bps
   round-trip cost exceeds the tiny favorable move. GROSS POSITIVE, NET
   NEGATIVE = fee flip preserved.
5. `final_equity = 9998.624653`. `holding_bars = 191 - 104 = 87`.

### G07 — funding boundary A (open after settlement, zero funding)

Day-1: j32 `B(60000,60100)`; j33–j39 `S(60100)`; j40 `B(60100,60000)`;
else `S(60000)` (j0–j31, j41–j95).

| idx | bar | TR | ATR | q | decision |
|---|---|---|---|---|---|
| 128 / j32 | 60000→60100 | 100 | 100 | **1.0** | flat → open_long |
| 129–135 / j33–j39 | 60100→60100 | 100 | 100 | 1.0 | long, hold |
| 136 / j40 | 60100→60000 | 100 | 100 | **0.0** | long, q <= 0 → exit |

Timing: entry fill 08:15 (ts `1780388100000`) — AFTER the 08:00 settlement
(`1780387200000`); exit fill 10:15 (ts `1780395300000`) — BEFORE the 16:00
settlement (`1780416000000`). Both events (rate 0.0001) are declared in the
case file but neither finds the position open → **funding = 0**.

Money math (identical structure to G01): entry fill 60130.05, qty 0.166306,
fees 3.999995 + 3.989348; exit fill 59970.00;
`gross = -26.617275`, `total_fees = 7.989343`, `net = -34.606618`,
`final_equity = 9965.393382`. `holding_bars = 136 - 128 = 8`.

### G08 — funding boundary B (held across exactly one settlement)

Day-1: j24 `B(60000,60100)`; j25–j39 `S(60100)`; j40 `B(60100,60000)`;
else `S(60000)`.

| idx | bar | q | decision |
|---|---|---|---|
| 120 / j24 | 60000→60100, TR 100, ATR 100 | **1.0** | flat → open_long |
| 121–135 / j25–j39 | 60100→60100 | 1.0 | long, hold (across 08:00) |
| 136 / j40 | 60100→60000, ATR 100 | **0.0** | long, exit |

Money math:

1. Entry closes 06:15 → ts `1780380900000`. Buy fill 60130.05, qty 0.166306,
   entry fee 3.999995, `position_open.equity = 9996.000005`.
2. Settlement 08:00 (ts `1780387200000`): position open → funding.
   `ref_price` = close of the last completed 15m bar at/before 08:00 = close of
   j31 (closes 08:00) = 60100. Notional `0.166306 * 60100 = 9994.990600`.
   `funding = 0.0001 * 9994.990600 = 0.999499` (long pays).
   Equity `9996.000005 - 0.999499 = 9995.000506`.
3. Exit closes 10:15 → ts `1780395300000`. Sell fill 59970.00 (raw 60000),
   exit fee `0.0004 * 9973.370820 = 3.989348`.
   `gross = 0.166306 * (59970.00 - 60130.05) = -26.617275`.
4. `total_fees = 3.999995 + 3.989348 + 0.999499 = 8.988842` (fees + funding).
   `net = -26.617275 - 8.988842 = -35.606117`.
5. `final_equity = 10000 - 35.606117 = 9964.393883`.
   Trail check: `9995.000506 + gross - exit_fee = 9995.000506 - 26.617275 -
   3.989348 = 9964.393883` ✓.
6. The 16:00 event (declared, rate 0.0001) finds no position (closed 10:15) →
   not applied. Exactly ONE settlement crossed. `holding_bars = 136 - 120 = 16`.

### G09 — param activated (same bars as G01, m = 3.0)

Identical `bars_15m`/`bars_1m` to G01; `volatility_multiplier = 3.0`.

| idx | close | ATR | q = (c-60000)/(ATR*3) | decision |
|---|---|---|---|---|
| 98–102 | 60000 | 100 | 0.0 | flat, hold |
| 103 / j7 | 60100 | 100 | 100/300 = **0.333333** | < 1 → NO entry |
| 104–105 | 60100 | 100 | 0.333333 | flat, hold |
| 106+ | 60000 | 100 | 0.0 | flat, hold |

max |q| over all decision bars = 1/3 < 1 → **zero trades, final_equity =
10000.0**. Changing the multiplier changed the trade set (G01: 1 trade → G09:
0 trades): the parameter IS activated. `meta.param_activated = true`.

### G10 — param INACTIVE (identical ledger under m=1.0 and m=2.0)

`atr_period = 3` → warmup 96+3 = 99 → first decision bar index 99.
Day-1: j0–j2 `S(60000)`; j3 `B(60000,60050)`; j4 `B(60050,60000)`;
j5 `B(60000,60025)`; j6 `B(60025,60100)`; j7 `S(60100)`; j8 `B(60100,60000)`;
j9+ `S(60000)`.

ATR uses three TRs. q under m=1.0 (q1) and m=2.0 (q2):

| idx | bar o→c | TR | ATR = mean(last 3 TR) | c-pivot | q1 = x/ATR | q2 = q1/2 | decision (both m) |
|---|---|---|---|---|---|---|---|
| 99 / j3 | 60000→60050 | 50 | (100+100+50)/3 = 83.333333 | 50 | 0.6 | 0.3 | flat, hold |
| 100 / j4 | 60050→60000 | 50 | (100+50+50)/3 = 66.666667 | 0 | 0.0 | 0.0 | flat, hold |
| 101 / j5 | 60000→60025 | 25 | (50+50+25)/3 = 41.666667 | 25 | 0.6 | 0.3 | flat, hold |
| 102 / j6 | 60025→60100 | 75 | (50+25+75)/3 = 50.0 | 100 | **2.0** | **1.0** | q >= +1 under BOTH → open_long |
| 103 / j7 | S(60100) | 100 | (25+75+100)/3 = 66.666667 | 100 | 1.5 | 0.75 | long, q > 0 → hold |
| 104 / j8 | 60100→60000 | 100 | (75+100+100)/3 = 91.666667 | 0 | **0.0** | **0.0** | long, q <= 0 → exit (m-independent) |
| 105+ / j9+ | S(60000) | 100 | 100 | 0 | 0.0 | 0.0 | flat, hold |

TR detail at j6: `max(75, |60100-60025|, |60025-60025|) = 75` (prev close is
60025). The entry fires under both multipliers (m=2.0 lands exactly on the
inclusive +1.0 boundary) and the exit q = 0.0 is multiplier-independent, so the
m=1.0 and m=2.0 ledgers are IDENTICAL — changing the multiplier does not change
any trade: `meta.param_activated = false` (pseudo-robustness; must not be
reported as robustness evidence, per `contracts.NeighborhoodBlock`).

Money math (the published ledger = the m=1.0 run):

1. Entry closes 01:45 → ts `1780364700000`. Buy fill 60130.05, qty 0.166306,
   entry fee 3.999995.
2. Exit closes 02:15 → ts `1780366500000`. Raw open 60000 → sell fill 59970.00,
   exit fee `0.0004 * 9973.370820 = 3.989348`.
3. `gross = -26.617275`, `total_fees = 7.989343`, `net = -34.606618`,
   `final_equity = 9965.393382`. `holding_bars = 104 - 102 = 2`.

### G11 — end-of-data open (bonus)

Day-1: j0–j3 `S(60000)`; j4 `B(60000,60100)`; j5–j9 `S(60100)`. Data ENDS at
j9 (closes 02:30, ts `1780367400000`).

| idx | bar | q | decision |
|---|---|---|---|
| 100 / j4 | 60000→60100, ATR 100 | **1.0** | flat → open_long |
| 101–105 / j5–j9 | 60100→60100 | 1.0 | long, hold; data ends → still open |

No day-end bar occurs inside the data, so the position never force-closes.
Expected:

- `exit_reason = end_of_data_open`; exit ts = last bar close
  (`1780367400000`); `exit_price = 60100.0` = last 15m close (a MARK, not a
  fill — no exit fee exists).
- `gross_pnl = 0.166306 * (60100.0 - 60130.05) = 0.166306 * (-30.05)
  = -4.997495` (unrealized).
- `total_fees = 3.999995` (entry fee only).
  `net_pnl = -4.997495 - 3.999995 = -8.997490`.
- `final_equity = 10000 - 8.997490 = 9991.002510` (mark-to-market: includes
  the unrealized mark; the `equity_mark` event records
  `unrealized_pnl = -4.997495`, `equity = 9991.002510`).
- Trail check: `9996.000005 (post entry fee) - 4.997495 = 9991.002510` ✓.
- `holding_bars = 105 - 100 = 5`.

---

## 4. Cross-check ledger (recap)

| case | spec (period, m) | trades | final_equity | key property |
|---|---|---|---|---|
| G01 | 2, 1.0 | 1 long | 9965.393382 | inclusive q=+1.0 entry; signal exit |
| G02 | 2, 1.0 | 1 short | 9965.273205 | inclusive q=-1.0 entry |
| G03 | 2, 1.0 | 1 long | 9982.009017 | day_end_flat into next-day 1m open |
| G04 | 2, 1.0 | 2 (long→short) | 9515.171337 | no same-bar reversal |
| G05 | 2, 1.0 | 0 | 10000.0 | warmup blocks would-be q=1.5 |
| G06 | 2, 1.0 | 1 long | 9998.624653 | gross +6.627294 / net -1.375347 (day-end close rebalanced to 60200) |
| G07 | 2, 1.0 | 1 long | 9965.393382 | zero funding (both settlements missed) |
| G08 | 2, 1.0 | 1 long | 9964.393883 | funding 0.999499 paid once, in total_fees |
| G09 | 2, 3.0 | 0 | 10000.0 | m=3 blocks entry (param_activated) |
| G10 | 3, 1.0 | 1 long | 9965.393382 | identical ledger under m=2.0 (param inactive) |
| G11 | 2, 1.0 | 1 long (open) | 9991.002510 | end_of_data_open marked at last close |

Verification recipe for any number: (1) rebuild TR from the two bar shapes,
(2) average the trailing `atr_period` TRs, (3) divide `close - pivot_prev_day`
by `ATR * m`, (4) apply the decision table, (5) fill at the next 1m open with
`±5bps` slippage, (6) `qty = equity / fill` (6dp), (7) fee `4bps` of fill
notional per side, (8) funding `rate * qty * ref_close` at declared
settlements, (9) net = gross − fees − funding, (10) final equity = 10000 +
Σ net.
