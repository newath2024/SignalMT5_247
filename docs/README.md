# Documentation Structure

## Active Structure

- `docs/system`
  - system-wide behavior, lifecycle, and architecture
- `docs/modules`
  - deterministic specifications for each trading concept
- `docs/tests`
  - reference test cases for implementation and regression
- `docs/decisions`
  - non-negotiable design decisions and philosophy

## Legacy Structure

- `docs/smc`
  - preserved as the original documentation set for backward compatibility
  - not removed or renamed

## Reorganization Rule

- New documentation must be added to the active structure above.
- Existing files under `docs/smc` remain available as legacy references unless explicitly deprecated in a future change.
