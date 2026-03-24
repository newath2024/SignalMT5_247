# Order Block Module

## Definition

An order block is the last opposite-colored candle before a displacement leg that produces both:

- a valid MSS
- at least one valid FVG in the same direction

This module is optional and secondary to FVG and IFVG logic.

- Displacement leg begins on the first candle after the origin candle.
- Displacement leg ends on the candle that confirms the source MSS.

## Valid Conditions

### Bullish

- a bullish MSS exists
- source MSS status is `valid`
- the bullish break leg contains at least one bullish FVG
- the last bearish candle before the displacement leg is selected
- the order block range is the full high-low range of that candle
- no later close has invalidated the block by closing below its low

### Bearish

- a bearish MSS exists
- source MSS status is `valid`
- the bearish break leg contains at least one bearish FVG
- the last bullish candle before the displacement leg is selected
- the order block range is the full high-low range of that candle
- no later close has invalidated the block by closing above its high

## Invalid Conditions

- no MSS exists
- source MSS is `expired` or `invalid`
- no same-direction FVG exists in the displacement leg
- selected candle is not the final opposite-colored candle before displacement
- selected candle is a doji and doji exclusion is enabled
- zone has already been invalidated by close beyond the opposite boundary

## Edge Cases

- if multiple consecutive opposite-colored candles exist, choose the last one only
- if displacement starts without a qualifying opposite-colored candle, no order block is created
- nested order blocks may coexist and are resolved by higher-level ranking

## Input

- ordered candle series
- confirmed MSS events
- confirmed FVG events
- optional doji threshold

## Output

- `id`
- `timeframe`
- `direction`
- `source_mss_id`
- `source_fvg_id`
- `origin_candle_index`
- `lower_bound`
- `upper_bound`
- `confirm_time`
- `status`: `active | retested | invalid`

## Implementation Notes

- Order block is optional confluence only.
- The module must never replace the required sweep-plus-MSS sequence.
- If order block conflicts with FVG or IFVG selection, FVG and IFVG take priority.
- The detector must not rely on visual interpretation or discretionary anchor selection.
- Order block detection must consume MSS and FVG outputs rather than recomputing displacement logic independently.
