# Module Test Cases

## FVG

### Case FVG-1 Valid Bullish

- Input: `high(A)=100`, `low(C)=104`, bullish `B`, min gap `2`.
- Expected: bullish FVG valid with bounds `100..104`.

### Case FVG-2 Valid Bearish

- Input: `low(A)=120`, `high(C)=116`, bearish `B`, min gap `2`.
- Expected: bearish FVG valid with bounds `116..120`.

### Case FVG-3 Invalid Overlap

- Input: `high(A)=100`, `low(C)=100`.
- Expected: invalid because strict gap does not exist.

### Case FVG-4 Invalid Small Gap

- Input: geometric gap exists but size is `1 tick` while minimum is `2 ticks`.
- Expected: invalid.

### Case FVG-5 Edge Partial Fill

- Input: valid bullish FVG later touched only to midpoint.
- Expected: status `partially_filled`, not `filled`.

## Sweep

### Case SWEEP-1 Valid Sell-Side Sweep

- Input: confirmed swing low `95`, sweep candle low `94.5`, close `95.5`.
- Expected: valid sell-side sweep and bullish reversal candidate.

### Case SWEEP-2 Valid Buy-Side Sweep

- Input: confirmed swing high `110`, sweep candle high `111`, close `109.5`.
- Expected: valid buy-side sweep and bearish reversal candidate.

### Case SWEEP-3 Invalid No Overshoot

- Input: swing high `110`, candle high `110`, close `109.5`.
- Expected: invalid because no tick beyond liquidity.

### Case SWEEP-4 Invalid No Rejection Close

- Input: swing low `95`, candle low `94.5`, close `94.8`.
- Expected: invalid because close remains beyond swept level.

### Case SWEEP-5 Edge Equal-Low Cluster

- Input: three swing lows within equality tolerance, candle sweeps below all and closes back above cluster.
- Expected: one valid sweep linked to nearest cluster representative.

## MSS

### Case MSS-1 Valid Bullish

- Input: valid sell-side sweep, nearest lower high `102`, later candle closes `103`.
- Expected: bullish MSS valid.

### Case MSS-2 Valid Bearish

- Input: valid buy-side sweep, nearest higher low `108`, later candle closes `107`.
- Expected: bearish MSS valid.

### Case MSS-3 Invalid Wick Break

- Input: candle high trades above pivot but close remains below pivot.
- Expected: invalid MSS.

### Case MSS-4 Invalid Missing Sweep

- Input: pivot break occurs without prior valid sweep.
- Expected: invalid MSS.

### Case MSS-5 Edge Replaced Sweep

- Input: initial sweep occurs, deeper same-side sweep occurs before break, then pivot breaks.
- Expected: MSS linked only to latest sweep.

## IFVG

### Case IFVG-1 Valid Bullish Inversion

- Input: bearish FVG `120..124`, later close above `124`, later retest into `120..124` from above.
- Expected: bullish IFVG valid.

### Case IFVG-2 Valid Bearish Inversion

- Input: bullish FVG `100..104`, later close below `100`, later retest into `100..104` from below.
- Expected: bearish IFVG valid.

### Case IFVG-3 Invalid Partial Traverse

- Input: bearish FVG retested from above but no prior close above far boundary.
- Expected: invalid.

### Case IFVG-4 Invalid Same-Candle Traverse And Retest

- Input: candle traverses and retests in one candle.
- Expected: invalid because retest requires later candle.

### Case IFVG-5 Edge Multiple Retests

- Input: valid inversion followed by three retests.
- Expected: first retest is primary actionable event; later retests are secondary or ignored per policy.

## Order Block

### Case OB-1 Valid Bullish

- Input: bearish candle immediately before bullish displacement leg that creates bullish MSS and bullish FVG.
- Expected: bullish order block valid.

### Case OB-2 Valid Bearish

- Input: bullish candle immediately before bearish displacement leg that creates bearish MSS and bearish FVG.
- Expected: bearish order block valid.

### Case OB-3 Invalid No MSS

- Input: displacement candle exists but no valid MSS sequence.
- Expected: invalid.

### Case OB-4 Invalid No FVG In Break Leg

- Input: MSS exists but break leg contains no valid FVG.
- Expected: invalid order block.

### Case OB-5 Edge Consecutive Opposite Candles

- Input: three bearish candles before bullish displacement.
- Expected: use the last bearish candle only.
