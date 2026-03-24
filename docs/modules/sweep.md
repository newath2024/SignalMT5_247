# Sweep Module

## Definition

A sweep is a liquidity event where price trades beyond a confirmed swing level and then closes back inside the pre-sweep range on the same candle.

- Buy-side sweep:
  - target is a confirmed swing high
  - candle high exceeds that swing high
  - candle close returns below that swing high
- Sell-side sweep:
  - target is a confirmed swing low
  - candle low trades below that swing low
  - candle close returns above that swing low

## Valid Conditions

### Buy-Side Sweep

- target is the nearest valid unswept confirmed swing high
- sweep candle high exceeds target by at least `1 tick`
- sweep candle close is below the target level
- target swing was confirmed before the sweep candle closed
- no newer confirmed swing high exists between target swing and sweep candle

### Sell-Side Sweep

- target is the nearest valid unswept confirmed swing low
- sweep candle low exceeds target on the downside by at least `1 tick`
- sweep candle close is above the target level
- target swing was confirmed before the sweep candle closed
- no newer confirmed swing low exists between target swing and sweep candle

## Invalid Conditions

- candle only touches the swing level
- candle closes beyond the swept level instead of rejecting back inside
- target swing is not confirmed
- sweep candle closes before target swing becomes confirmed
- target swing has been superseded by a newer same-side confirmed swing
- price grinds through the level across several candles without a single rejection candle

## Edge Cases

- one candle may sweep multiple historical levels; the nearest valid unswept level is the linked target
- if a deeper same-side sweep occurs before MSS confirmation, the deeper sweep replaces the prior sweep in the active chain
- equal-high or equal-low clusters inside configured tolerance are treated as one liquidity pool

## Input

- ordered candle series
- confirmed swing list
- tick size
- equality tolerance

## Output

- `id`
- `timeframe`
- `sweep_side`
- `direction_hint`: `bullish` after sell-side sweep, `bearish` after buy-side sweep
- `target_swing_id`
- `sweep_candle_index`
- `target_price`
- `extreme_price`
- `confirm_time`
- `status`: `valid | replaced | invalid`

## Implementation Notes

- The module emits liquidity events only. It does not emit entry signals.
- Confirmed swings are mandatory.
- A target swing can produce only one primary valid sweep event.
- Sweep direction is reversal-oriented and must align with downstream MSS logic.
- If a sweep is replaced, any downstream MSS candidate linked to the older sweep must be invalidated by the validation layer.
