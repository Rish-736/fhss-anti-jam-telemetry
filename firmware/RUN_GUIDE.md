# Test Matrix Run Guide

9 runs, about 70 seconds each. Set the flags, flash both boards, let it
finish, copy the `CSV,...` line from the receiver's serial monitor into
`results/results.csv`.

## Before anything else: calibrate the threshold

`JAM_RSSI_THRESHOLD` in `05_adaptive_tx` decides what counts as an
occupied channel. Calibrate it once:

1. Flash `05_adaptive_tx` with `CHANNEL_DENIED` all `false`.
2. Watch the `sensed ... -> RSSI ...` lines in the serial monitor.
3. Note the typical quiet reading (likely somewhere around -85 to -95 dBm).
4. Set `JAM_RSSI_THRESHOLD` about 15-20 dB above that floor.

Check: with nothing denied you should see **no** `OCCUPIED` lines. If you
do, the threshold is too close to the noise floor - make it more negative.

## Timing — how long to leave each run

Measured on the bench, a packet actually takes about **1.2 s**, not the
700 ms of `PACKET_INTERVAL`: `SendData()` and the serial prints add the
rest. So a 100-packet run is about **120 s** of transmission.

Runs that end on SEQ:99 print their summary straight away. Runs where the
receiver never sees SEQ:99 — anything with denial — only finish after the
15 s idle timeout, so budget **~140 s**:

```bash
python analysis/dual_monitor.py --seconds 150
```

Start the receiver first, then reset the transmitter, and **do not press
reset on either board mid-run** - the summary prints at the very end, so
a reset at 129 s throws away the whole run.

Do not change `PACKET_INTERVAL` partway through the matrix. Every run has
to share the same timing or the comparison is contaminated.

## The rule that matters most

`CHANNEL_DENIED[]` must be **identical in the transmitter and the
receiver** for every run. If they disagree, the two halves of the
experiment are testing different things and the numbers are meaningless.

Denial patterns used below:

| Denied count | Array |
|---|---|
| 0 | `{ false, false, false, false, false }` |
| 1 | `{ false, false, true,  false, false }` |
| 2 | `{ false, false, true,  false, true  }` |

## The runs

### Run 1 - Fixed, nothing denied  *(already measured: 0% loss)*
`01_fixed_tx` + `02_fixed_rx`, `CHANNEL_DENIED = false`.
Re-run only if you want a fresh number.

### Run 2 - Fixed, channel denied
`01_fixed_tx` + `02_fixed_rx`, `CHANNEL_DENIED = true`.
Expect 100% loss: a fixed link has nowhere else to go. This is the
motivation for the whole project.

### Run 3 - Basic FHSS, nothing denied  *(already measured: 5% loss)*
`03_fhss_tx` + `04_fhss_rx` with `ADAPTIVE_RUN = false`,
`RESYNC_ENABLED = false`, 0 denied.

### Run 4 - Basic FHSS, 1 denied, no recovery
`03_fhss_tx` + `04_fhss_rx`, `RESYNC_ENABLED = false`, 1 denied.
Expect the link to collapse rather than lose a neat 20%: the dropped
packet takes its `NEXT` instruction with it, so the receiver is stranded.
Watch for `(idle timeout reached)`. **This is a finding, not a bug** -
it is the fragility of in-band hop scheduling, and it is what motivates
both the rendezvous recovery and the adaptive sensing.

### Run 5 - Basic FHSS + rendezvous, 1 denied
Same, but `RESYNC_ENABLED = true`. Expect partial loss and a non-zero
`Resync events` count: the link keeps recovering and keeps walking back
into the denied channel because nothing tells it not to.

### Run 6 - Basic FHSS + rendezvous, 2 denied
Same as run 5 with 2 denied. Expect roughly double the loss of run 5.

### Run 7 - Adaptive, nothing denied
`05_adaptive_tx` + `04_fhss_rx` with `ADAPTIVE_RUN = true`,
`RESYNC_ENABLED = true`, 0 denied in both.
Expect something close to run 3, plus a little sensing overhead. This run
is also the only one where the RSSI readings are genuinely from the radio,
so it is what validates the sensing path.

### Run 8 - Adaptive, 1 denied
1 denied in **both** sketches. Expect loss close to run 7, and
`OCCUPIED ... blacklisting` lines in the transmitter log. The per-channel
table at the end should show **0 packets** on the denied channel - that is
the single most convincing line of output in the whole project.

### Run 9 - Adaptive, 2 denied
2 denied in both. Expect slightly worse than run 8 (fewer channels left to
use) but still far better than runs 5 and 6.

## After the runs

```bash
python analysis/plot_results.py
```

Writes three figures into `results/`. Figure 1 is the headline: adaptive
staying flat while the others climb.

## What this does and does not show

Say this plainly in the paper and the viva. Channel denial is **emulated
in firmware** - no interference is transmitted at any point. Denied
channels have their packets discarded at the receiver, and the adaptive
transmitter is fed a synthetic high RSSI for them.

So these runs validate the **avoidance and recovery logic**. They do not
validate the RF sensing front end against a real interferer; only run 7,
with nothing denied, exercises real radio readings. Testing against a
genuine interference source needs a third radio and an appropriate
conducted setup, which is correctly listed as future work.
