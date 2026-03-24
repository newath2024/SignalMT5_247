# SMC Trading Documentation Overview

## System Goal

This system converts discretionary Smart Money Concept (SMC) analysis into deterministic, testable, and explainable rule-based logic. The output is a ranked setup signal for trader review. The system does not place orders automatically.

## Architecture

```text
MT5 Data Feed
  -> Candle Normalization
  -> Swing Extraction
  -> Feature Detection
       - Sweep
       - FVG
       - IFVG
       - MSS
       - Order Block
  -> HTF Context Engine
  -> LTF Trigger Engine
  -> Validation Engine
  -> Explainable Signal Output
```

## Core Logic Flow

### 1. Higher-Timeframe Context

- Evaluate HTF in this order: `W1 -> D1 -> H4 -> H1 -> M30`.
- Detect active liquidity levels from confirmed swing highs and swing lows.
- Detect HTF imbalance zones using FVG and optional order block logic.
- Mark directional bias only when a valid HTF sweep and a valid HTF MSS exist in the same directional sequence.

### 2. Lower-Timeframe Trigger Search

- Evaluate LTF in this order: `M15 -> M5 -> M3`.
- Search only inside an active HTF zone.
- Require a valid LTF sweep, then a valid LTF MSS, then a valid trigger zone retest.
- Trigger zones are limited to `FVG`, `IFVG`, and optional `Order Block`.

### 3. Signal Formation

- Build a setup only when all mandatory stages are complete.
- Attach exact reasons for the setup: source timeframe, source candles, direction, prices, invalidation level, and confluence list.
- Return `NO_SIGNAL` when any mandatory stage is absent or contradictory.

## Deterministic Constraints

- No guessing logic is allowed.
- Every pattern must be defined by exact candle relationships.
- Every zone must have a fixed upper bound and lower bound.
- Every event must reference confirmed candles only.
- No future candle may be used to validate a historical signal except where confirmation is explicitly defined.
- A setup is either valid or invalid. There is no discretionary middle state in the engine.

## Definitions Used Across Modules

- `Candle`: OHLCV bar with timestamp and timeframe.
- `Bullish candle`: `close > open`.
- `Bearish candle`: `close < open`.
- `Body high`: `max(open, close)`.
- `Body low`: `min(open, close)`.
- `Range high`: `high`.
- `Range low`: `low`.
- `Swing high`: candle `i` whose high is greater than highs of `n` candles on both sides.
- `Swing low`: candle `i` whose low is lower than lows of `n` candles on both sides.
- `Confirmed swing`: swing whose right-side lookback is complete.
- `Sweep`: liquidity take beyond a confirmed swing followed by close back inside the prior range.
- `MSS`: break of the most recent opposing structural pivot after a sweep.
- `HTF zone`: validated HTF FVG or validated HTF order block.
- `LTF trigger`: validated LTF MSS plus retest into FVG, IFVG, or order block.

## Required Parameters

- Swing strength `n`: default `2`.
- Minimum candle count for structure validation: default `20`.
- Minimum gap size: instrument-specific, configured in ticks.
- Sweep overshoot: minimum `1 tick` beyond target liquidity.
- Retest tolerance: configured in ticks.
- Signal expiry: configured in candles by timeframe.

## Non-Goals

- Full autonomous order execution.
- Prediction without structural confirmation.
- Pattern labeling from subjective visual interpretation.
- Strategy optimization inside documentation.
- Risk management personalization for each trader.

## Philosophy

- HTF defines location.
- LTF defines timing.
- Sweeps define liquidity event.
- MSS defines directional intent.
- FVG and IFVG define efficient re-entry zones.
- Order block is optional confirmation, never a replacement for sweep plus MSS.
- When rules conflict, the engine chooses no trade.
