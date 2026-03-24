# Order Block Module Specification

## Definition

An order block is the last opposite-colored candle before a displacement move that creates a valid MSS and at least one valid FVG in the same direction.

- Bullish order block: last bearish candle before bullish displacement.
- Bearish order block: last bullish candle before bearish displacement.

## Valid Conditions

### Bullish Order Block

- A bullish MSS exists.
- The MSS break leg contains or creates at least one bullish FVG.
- Select the last bearish candle before the displacement leg begins.
- The selected candle low to high defines the full order block range.
- The order block remains valid until fully traded through by close below its low.

### Bearish Order Block

- A bearish MSS exists.
- The MSS break leg contains or creates at least one bearish FVG.
- Select the last bullish candle before the displacement leg begins.
- The selected candle low to high defines the full order block range.
- The order block remains valid until fully traded through by close above its high.

## Invalid Conditions

- No MSS exists.
- No displacement FVG exists in the break leg.
- Selected candle is not the final opposite-colored candle before displacement.
- Candle is a doji when doji exclusion is enabled by configuration.
- Zone is already invalidated by close beyond opposite boundary.

## Edge Cases

- If multiple consecutive opposite-colored candles exist, choose the last one before displacement.
- If displacement starts with a same-colored continuation and no opposite-colored candle exists immediately before it, no order block is created.
- Nested order blocks are allowed and handled by higher-level scoring.

## Input

- Ordered candle series.
- Confirmed MSS events.
- Confirmed FVG events.
- Optional doji threshold.

## Output

- `id`
- `timeframe`
- `direction`: `bullish` or `bearish`
- `source_mss_id`
- `source_fvg_id`
- `origin_candle_index`
- `lower_bound`
- `upper_bound`
- `status`: `active`, `retested`, `invalid`

## Notes For Implementation

- Order block is optional confluence only.
- The system must not create an order block from visual judgment alone.
- If order block logic conflicts with FVG or IFVG logic, FVG and IFVG take priority because they have stricter geometric definitions.
