# System Overview

## System Goal

The system converts Smart Money Concept (SMC) trading analysis into deterministic, testable, and explainable software logic. Its purpose is to detect high-quality setups, describe why they exist, and present them to a human trader for final approval.

## Architecture

```text
MT5 Data
  -> Candle Normalization
  -> Timeframe Partitioning
  -> Swing Detection
  -> Module Detection
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

## Shared Contract

- All modules operate on closed candles only.
- All prices are normalized to instrument tick size before validation.
- All time comparisons use candle close time, not candle open time.
- Each detected object must include:
  - stable `id`
  - `timeframe`
  - `direction` where applicable
  - source references to upstream objects
  - explicit `status`
- Status values must be updated by deterministic lifecycle rules only.
- A downstream module may reference an upstream object only when the upstream object is not `invalid`.

## Trading Logic Flow

### 1. Higher-Timeframe Context

- Canonical strategy HTF is structural-only: `M15 -> M30 -> H1 -> H4`.
- Build active HTF context only from confirmed `OB` and `FVG` zones.
- Remove session/day/week high-low anchors from active execution.
- Mark HTF directional bias from the strongest active structural zone and its reaction quality.

### 2. Lower-Timeframe Trigger

- Derive confirmation timeframes dynamically from the active HTF.
- Default confirmation policy uses the nearest lower 2 frames.
- Search for triggers only while price is inside or touching an active HTF zone.
- Require the following sequence in order:
  - LTF sweep
  - LTF MSS
  - strict LTF iFVG
- A trigger zone is eligible only when:
  - it is on the same timeframe as the active trigger search,
  - it is not `invalid`,
  - it is directionally aligned with the active MSS,
  - its retest occurs after its own confirmation event.
- Reject the setup immediately if LTF direction conflicts with HTF directional bias.

### 3. Entry Preparation

- Create an entry candidate only after the full LTF trigger sequence is complete.
- Attach exact metadata:
  - symbol
  - timeframe chain
  - source swing ids
  - source zone ids
  - direction
  - invalidation price
  - expiry time
  - reasons list
- Return `NO_SIGNAL` when any mandatory condition is absent, expired, or contradicted.

## Deterministic Constraints

- No guessing logic is allowed.
- No module may rely on unconfirmed swings.
- No module may infer direction from future candles unless explicit confirmation rules require later candles.
- Equality is not treated as a break, sweep, or gap. Strict inequality is required.
- Every zone must have fixed numeric bounds.
- Every setup must be reproducible from the same candle data and parameter set.
- When rules conflict, the system must return `NO_SIGNAL`.
- A downstream module must not duplicate upstream detection logic.
- If an upstream object is replaced, all dependent downstream objects derived from it become invalid.

## Non-Goals

- Full autonomous trade execution.
- Subjective chart annotation.
- Manual pattern interpretation inside the signal engine.
- Predictive logic without structural confirmation.
- Trader-specific risk sizing or portfolio allocation.

## Core Principles

- HTF defines location.
- LTF defines timing.
- Sweep must occur before MSS.
- MSS confirms intent but does not authorize entry by itself.
- FVG and IFVG are the primary trigger zones.
- Order block is optional confluence and must never override the core sweep-plus-MSS sequence.

## Module Ownership

- `Sweep` owns liquidity-take detection.
- `MSS` owns direction-confirmation after sweep.
- `FVG` owns three-candle imbalance detection.
- `IFVG` owns inversion of previously confirmed FVG only.
- `Order Block` owns optional pre-displacement origin zone detection.
- `Validation Engine` owns cross-module gating, conflict resolution, expiry handling, and final signal authorization.
