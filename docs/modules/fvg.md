# FVG Module

## Definition

A Fair Value Gap (FVG) is a three-candle imbalance defined on candles `A`, `B`, and `C`, where candle `B` displaces strongly enough that candles `A` and `C` do not overlap on one side.

- Bullish FVG: `high(A) < low(C)`
- Bearish FVG: `low(A) > high(C)`
- Candle mapping is fixed:
  - `A = i - 1`
  - `B = i`
  - `C = i + 1`

## Valid Conditions

### Bullish

- `high(A) < low(C)`
- `B` is bullish
- `range(B)` is greater than or equal to configured displacement threshold
- `low(C) - high(A)` is greater than or equal to minimum gap size
- candle `C` has closed

### Bearish

- `low(A) > high(C)`
- `B` is bearish
- `range(B)` is greater than or equal to configured displacement threshold
- `low(A) - high(C)` is greater than or equal to minimum gap size
- candle `C` has closed

## Invalid Conditions

- `A` and `C` overlap on the gap side
- gap size is below configured minimum
- `B` does not meet displacement threshold
- candle sequence is incomplete because `C` has not closed
- source candles include missing data and session-gap filtering is enabled
- later price action fully fills the gap and module status is recalculated

## Edge Cases

- Partial fill keeps the FVG active with status `partially_filled`
- Equal price on the boundary is not a valid gap
- Overlapping FVGs are stored independently
- Nested FVGs are allowed and resolved by higher-level signal ranking

## Input

- ordered candle series for one timeframe
- tick size
- minimum gap size in ticks
- displacement threshold
- optional session-gap filter

## Output

- `id`
- `timeframe`
- `direction`
- `source_indices`
- `confirm_index`
 - `confirm_time`
- `lower_bound`
- `upper_bound`
- `midpoint`
- `status`: `active | partially_filled | filled | invalid`

## Implementation Notes

- Bound storage must be consistent:
  - bullish: `lower_bound = high(A)`, `upper_bound = low(C)`
  - bearish: `lower_bound = high(C)`, `upper_bound = low(A)`
- The detector must not merge nearby gaps.
- FVG direction is fixed at creation and must not be rewritten from later price behavior.
- Full fill occurs only when later price trades through both bounds.
- FVG detection is geometry-only and must not depend on sweep, MSS, or HTF bias.
