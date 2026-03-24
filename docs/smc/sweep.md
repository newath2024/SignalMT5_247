# Sweep Module Specification

## Definition

A liquidity sweep is a deliberate take of a confirmed swing level followed by a rejection close back inside the pre-sweep range.

- Buy-side sweep: price trades above a confirmed swing high, then closes below that swing high.
- Sell-side sweep: price trades below a confirmed swing low, then closes above that swing low.

## Valid Conditions

### Buy-Side Sweep

- Target is a confirmed swing high.
- Current candle high exceeds target swing high by at least `1 tick`.
- Current candle close is below target swing high.
- No newer confirmed swing high exists between target swing and sweep candle.

### Sell-Side Sweep

- Target is a confirmed swing low.
- Current candle low is below target swing low by at least `1 tick`.
- Current candle close is above target swing low.
- No newer confirmed swing low exists between target swing and sweep candle.

## Invalid Conditions

- Candle only touches the swing level without overshoot.
- Candle closes beyond the swept level instead of rejecting back inside.
- Target swing is not confirmed.
- Sweep references an obsolete swing that has already been superseded by a newer same-side confirmed swing.
- Multiple candles grind through the level without a single rejection event.

## Edge Cases

- A candle can sweep multiple older levels; only the nearest valid unswept confirmed level is linked as the primary sweep target.
- If a later candle forms a deeper sweep before MSS confirmation, the latest valid sweep replaces the earlier one.
- Equal high or equal low clusters are treated as one liquidity pool if all levels lie within configured equality tolerance.

## Input

- Ordered candle series for one timeframe.
- Confirmed swing points.
- Tick size.
- Equality tolerance.

## Output

- `id`
- `timeframe`
- `direction`: `bullish_reversal_candidate` after sell-side sweep, `bearish_reversal_candidate` after buy-side sweep
- `sweep_side`: `sell_side` or `buy_side`
- `target_swing_id`
- `sweep_candle_index`
- `target_price`
- `extreme_price`
- `close_back_inside`: boolean
- `status`: `valid`, `replaced`, `invalid`

## Notes For Implementation

- A sweep alone is not a trade signal.
- Sweep direction is reversal-oriented:
  - Sell-side sweep suggests bullish potential.
  - Buy-side sweep suggests bearish potential.
- Use confirmed swings only. Real-time unconfirmed pivots create non-deterministic behavior and are forbidden.
- The detector should emit the first valid rejection candle only once per target swing.
