# Trading State Machine

## State Flow

```text
IDLE
  -> HTF_CONTEXT
  -> LTF_TRIGGER
  -> MSS_CONFIRMED
  -> ENTRY_READY
  -> EXIT_MANAGEMENT
  -> IDLE

Failure paths:
HTF_CONTEXT -> IDLE
LTF_TRIGGER -> INVALIDATED -> IDLE
MSS_CONFIRMED -> INVALIDATED -> IDLE
ENTRY_READY -> EXPIRED -> IDLE
EXIT_MANAGEMENT -> CLOSED -> IDLE
```

## States

### IDLE

- Description: no active setup chain exists for the symbol and timeframe stack.
- Transition to `HTF_CONTEXT`: a new synchronized HTF dataset is available for evaluation.

### HTF_CONTEXT

- Description: evaluate HTF sweeps, HTF MSS, and HTF zones to determine whether valid directional context exists.
- Transition to `LTF_TRIGGER`: a valid HTF directional bias exists and price is inside or touching an active HTF zone.
- Transition to `IDLE`: no valid HTF directional bias exists.
- Transition to `INVALIDATED`: HTF bias existed and was later revoked before LTF trigger search completed.

### LTF_TRIGGER

- Description: evaluate LTF sweep conditions inside the active HTF zone and determine whether a valid pre-MSS trigger chain exists.
- Transition to `MSS_CONFIRMED`: a valid LTF sweep exists and a valid LTF MSS closes in the same direction as HTF bias.
- Transition to `INVALIDATED`: price exits the HTF zone, HTF direction changes, or contradictory LTF structure appears before MSS confirmation.
- Transition to `EXPIRED`: configured trigger window ends before MSS confirmation.

### MSS_CONFIRMED

- Description: the system has a valid LTF sweep plus a valid LTF MSS and is waiting for retest into a valid trigger zone.
- Transition to `ENTRY_READY`: price retests a valid FVG, IFVG, or optional order block aligned with the confirmed MSS direction.
- Transition to `INVALIDATED`: price closes beyond the MSS invalidation level before retest.
- Transition to `EXPIRED`: retest does not occur before configured expiry.

### ENTRY_READY

- Description: the setup is complete and can be presented to the trader as a semi-automated entry candidate.
- Transition to `EXIT_MANAGEMENT`: the trader accepts the setup and records an entry.
- Transition to `INVALIDATED`: price breaks the setup invalidation level before trader acceptance.
- Transition to `EXPIRED`: trader does not act before signal expiry.

### EXIT_MANAGEMENT

- Description: an accepted trade is live and the system tracks post-entry conditions for reporting and trader support.
- Transition to `CLOSED`: exit event is recorded by trader action, stop-loss event, target event, or manual close event.

### INVALIDATED

- Description: the setup chain became structurally invalid and must not be promoted as a valid signal.
- Transition to `IDLE`: the invalid chain is cleared and the engine waits for the next evaluation cycle.

### EXPIRED

- Description: the setup chain was structurally valid but its timing window ended.
- Transition to `IDLE`: the expired chain is cleared and the engine waits for new context.

### CLOSED

- Description: the tracked trade lifecycle is complete.
- Transition to `IDLE`: post-trade data is stored and the engine returns to scanning mode.

## Hard Rules

- The engine must not skip from `HTF_CONTEXT` to `ENTRY_READY`.
- `ENTRY_READY` requires the ordered chain `HTF context -> LTF sweep -> LTF MSS -> retest`.
- `EXIT_MANAGEMENT` starts only after trader acceptance of `ENTRY_READY`.
- Contradictory directional events always transition the chain to `INVALIDATED`.
- A replaced sweep invalidates any pending MSS candidate derived from the earlier sweep.
- An invalidated MSS invalidates any dependent retest candidate.
