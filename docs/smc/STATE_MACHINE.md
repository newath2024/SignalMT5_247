# Trading State Machine

## State Flow

```text
IDLE
  -> HTF_CONTEXT
  -> HTF_ZONE_ACTIVE
  -> LTF_WAIT_SWEEP
  -> LTF_WAIT_MSS
  -> LTF_WAIT_RETEST
  -> SIGNAL_READY
  -> SIGNAL_EXPIRED or INVALIDATED
  -> IDLE
```

## State Definitions And Transitions

### IDLE

- Description: no active trade candidate exists.
- Transition to `HTF_CONTEXT`: new synchronized HTF candle set is available.

### HTF_CONTEXT

- Description: compute HTF swings, sweeps, MSS, and zones.
- Transition to `HTF_ZONE_ACTIVE`: at least one active HTF zone exists and HTF directional bias is valid.
- Transition to `IDLE`: no valid HTF directional bias exists.

### HTF_ZONE_ACTIVE

- Description: engine has a valid HTF directional bias and at least one active HTF zone.
- Transition to `LTF_WAIT_SWEEP`: current market price enters or touches active HTF zone.
- Transition to `IDLE`: HTF zone expires or HTF bias becomes invalid.

### LTF_WAIT_SWEEP

- Description: wait for LTF liquidity event inside active HTF zone.
- Transition to `LTF_WAIT_MSS`: valid LTF sweep occurs in direction compatible with HTF bias.
- Transition to `INVALIDATED`: price exits HTF zone and exceeds zone invalidation boundary before a valid sweep.
- Transition to `IDLE`: HTF context refresh removes the active bias.

### LTF_WAIT_MSS

- Description: valid LTF sweep exists; wait for close-based structural break.
- Transition to `LTF_WAIT_RETEST`: valid LTF MSS occurs before sweep expiry.
- Transition to `INVALIDATED`: opposing sweep or opposing MSS occurs first.
- Transition to `IDLE`: HTF bias is revoked before MSS confirmation.

### LTF_WAIT_RETEST

- Description: valid LTF sweep and MSS exist; wait for retest into trigger zone.
- Transition to `SIGNAL_READY`: price retests valid FVG, IFVG, or optional order block aligned with MSS direction.
- Transition to `SIGNAL_EXPIRED`: retest does not occur within configured expiry window.
- Transition to `INVALIDATED`: price closes beyond MSS invalidation level before retest.

### SIGNAL_READY

- Description: setup is complete and may be shown to trader for approval.
- Transition to `INVALIDATED`: price closes through setup invalidation level before trader acts.
- Transition to `IDLE`: signal is consumed, rejected, or timed out by policy.

### SIGNAL_EXPIRED

- Description: valid precursor sequence existed but timing window closed.
- Transition to `IDLE`: engine clears expired setup and waits for new HTF context.

### INVALIDATED

- Description: setup chain became structurally invalid.
- Transition to `IDLE`: engine clears invalid setup and waits for next valid context.

## State Data Requirements

- `HTF bias direction`
- `active HTF zone ids`
- `active sweep id`
- `active MSS id`
- `eligible trigger zone ids`
- `signal invalidation price`
- `expiry timestamps`

## Hard Rules

- The machine cannot jump from `HTF_ZONE_ACTIVE` directly to `SIGNAL_READY`.
- `SIGNAL_READY` requires sweep, MSS, and retest completion in that order.
- Any contradictory directional event resets the chain to `INVALIDATED`.
- Manual trader approval happens after `SIGNAL_READY` and is outside the machine described here.
