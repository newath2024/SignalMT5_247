# IFVG Module

## Definition

An Inversion Fair Value Gap (IFVG) is a previously confirmed FVG that has been fully crossed by close and is later reused from the opposite side as a retest zone.

- Bullish IFVG:
  - source is a bearish FVG
  - price closes above the source zone
  - price later retests that zone from above
- Bearish IFVG:
  - source is a bullish FVG
  - price closes below the source zone
  - price later retests that zone from below

## Valid Conditions

### Bullish

- source FVG is confirmed and bearish
- later candle closes above the source FVG upper bound
- retest happens after that traversal close
- retest candle range intersects the source zone from above
- source FVG is not `invalid`

### Bearish

- source FVG is confirmed and bullish
- later candle closes below the source FVG lower bound
- retest happens after that traversal close
- retest candle range intersects the source zone from below
- source FVG is not `invalid`

## Invalid Conditions

- source FVG was never confirmed
- source FVG is `invalid`
- source FVG was only partially crossed
- retest occurs before the full traversal close
- retest occurs in the same candle as traversal confirmation
- optional expiry rule marks the zone expired before retest

## Edge Cases

- first valid full traversal creates the inversion state
- first untouched retest is the primary actionable retest
- overlapping fresh FVG and IFVG zones can coexist and must be resolved by higher-level scoring

## Input

- confirmed FVG records
- ordered candle series
- retest tolerance
- optional zone expiry

## Output

- `id`
- `timeframe`
- `direction`
- `source_fvg_id`
- `inversion_confirm_index`
- `inversion_confirm_time`
- `retest_index`
- `lower_bound`
- `upper_bound`
- `status`: `active | retested | expired | invalid`

## Implementation Notes

- IFVG is derived only from a previously confirmed FVG.
- Full traversal requires close beyond the far boundary.
- IFVG is a valid trigger zone only when its direction matches the active MSS chain.
- The module must not detect IFVG directly from raw candles without source-FVG linkage.
- IFVG must not duplicate FVG geometry checks beyond validating the referenced source zone.
