# FVG Module Specification

## Definition

A Fair Value Gap (FVG) is a three-candle imbalance where candle `B` displaces strongly enough that candle `A` and candle `C` do not overlap on one side.

- Bullish FVG exists when `high(A) < low(C)`.
- Bearish FVG exists when `low(A) > high(C)`.
- Candle order is fixed: `A = i-1`, `B = i`, `C = i+1`.

## Valid Conditions

### Bullish FVG

- `high(A) < low(C)`.
- `B` is bullish.
- `range(B)` is greater than or equal to configured displacement threshold.
- Gap size `low(C) - high(A)` is greater than or equal to configured minimum gap size.
- FVG is confirmed only after candle `C` closes.

### Bearish FVG

- `low(A) > high(C)`.
- `B` is bearish.
- `range(B)` is greater than or equal to configured displacement threshold.
- Gap size `low(A) - high(C)` is greater than or equal to configured minimum gap size.
- FVG is confirmed only after candle `C` closes.

## Invalid Conditions

- Candle `A` and candle `C` overlap on the gap side.
- Gap size is below minimum configured size.
- Candle `B` does not meet displacement threshold.
- FVG is already fully filled by later candle action.
- Gap is formed across missing data or session discontinuity and session-gap filtering is enabled.

## Edge Cases

- Partial fill: FVG remains valid until fully traded through.
- Multi-candle overlap: each FVG is stored independently by source candle triplet.
- Nested FVGs: keep both; prioritization is handled by the signal engine, not by the detector.
- Equal prices: equality does not qualify as a gap. Strict inequality is required.

## Input

- Ordered candle series for one timeframe.
- Instrument tick size.
- Minimum gap size in ticks.
- Displacement threshold.
- Optional session filter flag.

## Output

- `id`
- `timeframe`
- `direction`: `bullish` or `bearish`
- `start_time`: candle `A` time
- `confirm_time`: candle `C` close time
- `upper_bound`
- `lower_bound`
- `midpoint`
- `source_indices`: `[A, B, C]`
- `status`: `active`, `partially_filled`, `filled`, `invalid`

## Notes For Implementation

- Store bounds consistently:
  - Bullish FVG: `lower_bound = high(A)`, `upper_bound = low(C)`.
  - Bearish FVG: `lower_bound = high(C)`, `upper_bound = low(A)`.
- A later candle fills the gap when its range trades through both bounds.
- Do not merge adjacent gaps in the detector. Merge only in a higher-level zone aggregator if required.
- The module must not infer direction from future price reaction. Direction is defined at creation time only.
