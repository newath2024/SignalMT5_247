# System Decisions

## Key System Decisions

### Confirmed Swings Only

- All structure logic uses confirmed swings only.
- Reason: unconfirmed swings repaint and produce non-deterministic outputs.

### Sweep Before MSS

- MSS is valid only if it follows a valid sweep in the same setup chain.
- Reason: this preserves the intended SMC sequence of liquidity event first, structure shift second.

### Close-Based Structure Break

- MSS requires a candle close beyond the reference pivot.
- Wick-only breaches are invalid.
- Reason: close-based confirmation is deterministic and less noisy.

### HTF Gating Is Mandatory

- LTF triggers are ignored unless price is inside or touching an active HTF zone.
- Reason: LTF timing without HTF location creates inconsistent setup quality.

### FVG And IFVG Are Primary Zones

- FVG and IFVG are the primary trigger-zone primitives.
- Order block is optional confluence only.
- Reason: FVG and IFVG have stricter geometric definitions and lower interpretation variance.

### No Trade On Conflict

- If HTF direction and LTF direction disagree, the system returns `NO_SIGNAL`.
- Reason: choosing one side manually would reintroduce discretionary logic.

## What Must Not Change

- Confirmed-swings-only policy.
- Sweep before MSS sequence.
- MSS must break the nearest valid opposing confirmed pivot.
- Equality must remain invalid for gap, break, and sweep confirmation.
- HTF zone gating must remain mandatory.
- Order block must remain optional and secondary.
- Ambiguous cases must resolve to `invalid` or `NO_SIGNAL`, not silent acceptance.

## Design Philosophy

- Translate visual SMC concepts into explicit machine rules.
- Prefer fewer signals over ambiguous signals.
- Keep every module explainable with source candles and source levels.
- Preserve one source of truth for each concept.
- Treat trader approval as part of the operating model, not a failure of automation.

## Module Responsibility Boundaries

- `Sweep` does not confirm direction. It only confirms liquidity take and rejection.
- `MSS` does not detect liquidity. It consumes sweep output and confirms directional break.
- `FVG` does not decide entry eligibility. It only defines imbalance zones.
- `IFVG` does not create new imbalance geometry. It reclassifies an existing FVG after full traversal.
- `Order Block` does not replace FVG or IFVG. It adds optional confluence only.
- `State Machine` does not detect patterns. It only governs sequence and invalidation.

## Inconsistencies Fixed In The Reorganization

- HTF zone eligibility is now stated consistently across overview, state machine, and module behavior.
- The entry lifecycle now explicitly separates `ENTRY_READY` from post-acceptance `EXIT_MANAGEMENT`.
- Order block priority is now defined consistently as optional confluence and never a replacement for FVG or IFVG.
- Retest timing is now explicit: retests must occur after confirmation events, not in the same candle that creates them.
- Downstream invalidation now explicitly follows upstream replacement or invalidation.
