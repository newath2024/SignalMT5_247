# Module Test Cases

## FVG

### FVG-1 Valid Bullish

- Input: `high(A)=100`, `low(C)=104`, bullish `B`, minimum gap `2`
- Expected output: valid bullish FVG with bounds `100..104`

### FVG-2 Invalid Overlap

- Input: `high(A)=100`, `low(C)=100`
- Expected output: invalid because strict gap does not exist

### FVG-3 Edge Partial Fill

- Input: valid bullish FVG later traded only to midpoint
- Expected output: status `partially_filled`

### FVG-4 Invalid Unclosed Sequence

- Input: candles `A` and `B` exist but candle `C` has not closed yet
- Expected output: no confirmed FVG object

## Sweep

### SWEEP-1 Valid Sell-Side Sweep

- Input: confirmed swing low `95`, sweep candle low `94.5`, close `95.5`
- Expected output: valid sweep with `sweep_side = sell_side` and `direction_hint = bullish`

### SWEEP-2 Invalid No Rejection

- Input: confirmed swing high `110`, candle high `111`, close `110.5`
- Expected output: invalid because close remains beyond swept level

### SWEEP-3 Edge Equal-Low Cluster

- Input: three confirmed swing lows inside equality tolerance, one candle trades below all and closes above the cluster
- Expected output: one valid sweep linked to the nearest cluster representative

### SWEEP-4 Invalid Unconfirmed Target

- Input: price sweeps a provisional swing before right-side confirmation candles complete
- Expected output: invalid sweep because target swing is not yet confirmed

## MSS

### MSS-1 Valid Bullish

- Input: valid sell-side sweep, nearest confirmed lower high `102`, later candle closes `103`
- Expected output: valid bullish MSS linked to that sweep and pivot

### MSS-2 Invalid Wick Break

- Input: candle high exceeds pivot, candle close remains below pivot
- Expected output: invalid MSS

### MSS-3 Edge Replaced Sweep

- Input: one valid sweep occurs, a deeper same-side sweep occurs before break, then pivot breaks
- Expected output: valid MSS linked only to the latest sweep

### MSS-4 Invalid Same-Candle Break

- Input: one candle both performs the sweep and closes beyond the opposing pivot
- Expected output: invalid MSS because break must occur after the sweep candle

## IFVG

### IFVG-1 Valid Bullish Inversion

- Input: bearish FVG `120..124`, later close above `124`, later retest from above
- Expected output: valid bullish IFVG

### IFVG-2 Invalid Partial Traverse

- Input: source bearish FVG retested from above without any prior close above the far boundary
- Expected output: invalid IFVG

### IFVG-3 Edge Multiple Retests

- Input: valid inversion, then three retests
- Expected output: first retest is primary actionable retest; later retests are secondary or ignored by policy

### IFVG-4 Invalid Source Zone

- Input: source FVG record is already marked `invalid` before inversion evaluation
- Expected output: invalid IFVG

## Order Block

### OB-1 Valid Bullish

- Input: bullish MSS exists, bullish displacement leg contains bullish FVG, final bearish candle before displacement is present
- Expected output: valid bullish order block using that final bearish candle range

### OB-2 Invalid Missing FVG

- Input: bullish MSS exists but the displacement leg contains no bullish FVG
- Expected output: invalid order block

### OB-3 Edge Consecutive Opposite Candles

- Input: three bearish candles appear before bullish displacement
- Expected output: the last bearish candle only is selected as the order block origin

### OB-4 Invalid Source MSS

- Input: candidate order block exists but linked MSS is `expired`
- Expected output: invalid order block

## Cross-Module Consistency Tests

### XMOD-1 Sweep Without MSS

- Input: valid sweep exists, no valid MSS occurs before expiry
- Expected output: no entry candidate and state transitions to `EXPIRED`

### XMOD-2 MSS Outside HTF Zone

- Input: valid LTF sweep and MSS form entirely outside active HTF zone
- Expected output: `NO_SIGNAL`

### XMOD-3 Order Block Conflicts With FVG

- Input: valid order block exists but conflicts with same-chain FVG selection
- Expected output: FVG remains primary trigger zone, order block remains optional confluence
