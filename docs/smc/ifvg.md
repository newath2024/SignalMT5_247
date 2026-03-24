# IFVG Module Specification

## Definition

An Inversion Fair Value Gap (IFVG) is a previously confirmed FVG that has been invalidated by full price traversal and then reused from the opposite side as a reaction zone.

- Bullish IFVG comes from a previously bearish FVG that was fully crossed upward and is later retested from above.
- Bearish IFVG comes from a previously bullish FVG that was fully crossed downward and is later retested from below.

## Valid Conditions

### Bullish IFVG

- Source zone is a confirmed bearish FVG.
- A later candle closes above the source FVG upper bound, proving full upward traversal.
- After traversal, price retests the former bearish FVG zone from above.
- Retest candle range intersects the zone.
- Retest occurs after the traversal close, not during the same candle.

### Bearish IFVG

- Source zone is a confirmed bullish FVG.
- A later candle closes below the source FVG lower bound, proving full downward traversal.
- After traversal, price retests the former bullish FVG zone from below.
- Retest candle range intersects the zone.
- Retest occurs after the traversal close, not during the same candle.

## Invalid Conditions

- Source FVG was never confirmed.
- Source FVG was only partially penetrated and never fully crossed.
- Retest occurs before full traversal close.
- Retest happens after zone expiry if expiry rules are enabled.
- Zone direction is reused without inversion.

## Edge Cases

- Multiple traversals: first valid full traversal creates the inversion state.
- Multiple retests: first untouched retest is primary; later retests may be ranked lower or ignored by strategy policy.
- Overlapping IFVG and fresh FVG zones are both retained and resolved by higher-level scoring.

## Input

- Confirmed FVG records.
- Ordered candle series.
- Retest tolerance.
- Optional zone expiry.

## Output

- `id`
- `timeframe`
- `direction`: `bullish` or `bearish`
- `source_fvg_id`
- `inversion_confirm_index`
- `retest_index`
- `lower_bound`
- `upper_bound`
- `status`: `active`, `retested`, `expired`, `invalid`

## Notes For Implementation

- IFVG is derived state. It must never be detected directly from raw candles without linking to a source FVG.
- Full traversal must be defined by candle close beyond the far boundary.
- A valid IFVG is a trigger zone only when it aligns with an existing directional MSS.
