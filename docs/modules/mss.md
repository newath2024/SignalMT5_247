# MSS Module

## Definition

A Market Structure Shift (MSS) is a close-based break of the nearest valid opposing confirmed pivot after a valid sweep.

- Bullish MSS:
  - requires a prior sell-side sweep
  - breaks above the nearest confirmed lower high
- Bearish MSS:
  - requires a prior buy-side sweep
  - breaks below the nearest confirmed higher low

## Valid Conditions

### Bullish

- a valid sell-side sweep exists
- the reference pivot is the nearest confirmed lower high that formed at or before the sweep candle
- a later candle closes above that pivot
- the close exceeds the pivot by at least configured break tolerance
- the break occurs before sweep expiry
- the break candle closes after the source sweep candle closes

### Bearish

- a valid buy-side sweep exists
- the reference pivot is the nearest confirmed higher low that formed at or before the sweep candle
- a later candle closes below that pivot
- the close exceeds the pivot by at least configured break tolerance
- the break occurs before sweep expiry
- the break candle closes after the source sweep candle closes

## Invalid Conditions

- no valid source sweep exists
- source sweep is `replaced` or `invalid`
- break occurs by wick only
- broken pivot is not the nearest valid opposing confirmed pivot
- break happens after the sweep expiry window
- break occurs on the same candle as the sweep
- contradictory break occurs before confirmation

## Edge Cases

- if multiple opposing pivots exist, the nearest valid confirmed pivot is the only valid reference
- if a newer same-side sweep replaces the earlier sweep, pivot selection must be recalculated from the new sweep
- equality at the pivot price is invalid

## Input

- ordered candle series
- confirmed swing structure
- valid sweep events
- break tolerance
- sweep expiry window

## Output

- `id`
- `timeframe`
- `direction`
- `source_sweep_id`
- `reference_pivot_id`
- `break_candle_index`
- `break_price`
- `confirm_time`
- `invalidation_price`
- `status`: `valid | expired | invalid`

## Implementation Notes

- MSS is confirmation, not entry.
- MSS must be calculated from candle close, not wick range.
- The pivot-selection rule must be fixed in code and must not depend on manual chart reading.
- Downstream retest logic starts only after MSS is confirmed.
- MSS must not re-run sweep logic internally. It consumes sweep output only.
