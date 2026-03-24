# Design Decisions

## Key Decisions

### 1. Confirmed Swings Only

- All structural logic uses confirmed swings only.
- Reason: unconfirmed pivots repaint and break determinism.

### 2. Sweep Before MSS

- MSS is valid only after a same-sequence sweep.
- Reason: this enforces the intended SMC logic of liquidity event first, displacement second.

### 3. Close-Based Structure Break

- MSS requires close beyond pivot, not wick beyond pivot.
- Reason: wick-only breaks create false positives and inconsistent replay behavior.

### 4. HTF Location Before LTF Trigger

- LTF signals are ignored outside active HTF zones.
- Reason: location is mandatory context, not optional scoring.

### 5. FVG Is Primary Zone Primitive

- FVG and IFVG are primary actionable zones.
- Order block is secondary and optional.
- Reason: FVG has stricter, more deterministic geometry than most order block definitions.

### 6. No Trade On Conflict

- If HTF direction and LTF direction disagree, output `NO_SIGNAL`.
- Reason: forcing a directional choice introduces discretionary behavior.

## Why These Rules Were Chosen

- They map subjective chart-reading concepts into finite checks.
- They are replayable on historical candle data.
- They support explainable output with exact source candles and price levels.
- They are suitable for unit tests and regression tests.

## What Must Not Change

- Use of confirmed swings only.
- Sweep must occur before MSS in the same directional chain.
- MSS must break the nearest valid opposing confirmed pivot.
- HTF zone gating must remain mandatory.
- Equality must not be treated as break or gap.
- Modules must emit explicit invalid states instead of silently dropping ambiguous cases.

## Trade-Offs

- Stricter rules reduce signal count.
- Close-based confirmation is slower than wick-based anticipation.
- Confirmed swings introduce lag but remove repainting.
- Mandatory HTF gating removes some profitable LTF reversals, but increases consistency.
- Optional order block logic keeps flexibility without contaminating the core deterministic path.
