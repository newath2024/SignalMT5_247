# MSS Module Specification

## Definition

A Market Structure Shift (MSS) is a post-sweep break of the most recent opposing confirmed structural pivot, proving directional intent.

- Bullish MSS follows a sell-side sweep and breaks the most recent confirmed lower high.
- Bearish MSS follows a buy-side sweep and breaks the most recent confirmed higher low.

## Valid Conditions

### Bullish MSS

- A valid sell-side sweep already exists.
- Identify the most recent confirmed lower high that formed before or at the sweep candle.
- A later candle closes above that lower high.
- The close beyond the pivot must exceed the pivot by at least configured break tolerance.
- The break candle must occur within configured expiry window after the sweep.

### Bearish MSS

- A valid buy-side sweep already exists.
- Identify the most recent confirmed higher low that formed before or at the sweep candle.
- A later candle closes below that higher low.
- The close beyond the pivot must exceed the pivot by at least configured break tolerance.
- The break candle must occur within configured expiry window after the sweep.

## Invalid Conditions

- No preceding valid sweep exists.
- Break occurs only by wick and not by candle close.
- Broken pivot is not the nearest valid opposing structural pivot.
- Break occurs after sweep expiry window.
- Price breaks in both directions before confirmation, creating structural contradiction.

## Edge Cases

- If multiple opposing pivots exist, use the nearest confirmed pivot in time.
- If a deeper sweep occurs before break, recompute the reference pivot from the latest sweep.
- Equal-close break at the exact pivot price is invalid. Break requires strict beyond-pivot close plus tolerance.

## Input

- Ordered candle series.
- Confirmed swing structure.
- Valid sweep events.
- Break tolerance.
- Sweep expiry window.

## Output

- `id`
- `timeframe`
- `direction`: `bullish` or `bearish`
- `source_sweep_id`
- `reference_pivot_id`
- `break_candle_index`
- `break_price`
- `confirm_time`
- `status`: `valid`, `expired`, `invalid`

## Notes For Implementation

- MSS is directional confirmation, not entry.
- The pivot selection rule must be fixed in code and never chosen manually.
- MSS must be computed from close prices, not intrabar extremes.
- Once MSS is confirmed, downstream modules may search for retest into FVG, IFVG, or order block.
