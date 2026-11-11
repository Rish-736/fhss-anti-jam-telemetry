# The Project, End to End

Everything needed to explain this project to someone who has not seen it:
what each program does, what each experiment proves, and what the numbers
mean. Read in order.

---

## 1. The problem

A conventional drone telemetry link transmits on one fixed frequency.
That makes it trivially easy to disrupt: anything putting energy on that
frequency takes the link down, and with it the commands the drone depends
on, including return-to-home and failsafe.

**Frequency hopping spread spectrum (FHSS)** answers this by refusing to
stay still. The transmitter and receiver agree on a list of channels and
move through it together. Something sitting on one channel now only
affects the fraction of packets sent while the link happens to be there.

Our project builds that link, measures it, and then adds a layer on top:
the transmitter **checks a channel before hopping to it** and avoids ones
that look occupied.

**The honest claim** - worth stating exactly this way, because it is what
the measurements support: *frequency hopping improves reliability when
interference affects some of the channels, not all of them.* If something
denies the whole band, hopping has nowhere to go and does not help.

---

## 2. The hardware

| Part | Count | Role |
|---|---|---|
| ESP32 DevKit | 2 | Runs the logic, drives the radio over SPI |
| CC1101 433 MHz transceiver | 2 | The radio itself |
| Spring antenna | 2 | One per module |

Wiring is identical on both boards, SPI at 3.3 V:

| CC1101 | ESP32 |
|---|---|
| VCC | 3.3 V (**never 5 V**) |
| GND | GND |
| SCK | GPIO 18 |
| MOSI / SI | GPIO 23 |
| MISO / SO | GPIO 19 |
| CSN / CS | GPIO 5 |

One board is the transmitter, one the receiver. Each is plugged into the
laptop by USB, which both powers it and carries the serial log.

---

## 3. The radio settings, and why each one

All in `firmware/shared/rf_config.h`, applied identically at both ends by
`applyRadioConfig()`. If the two ends disagree on any of these, nothing is
received at all.

| Setting | Value | What it does |
|---|---|---|
| Modulation | 2-FSK | Two frequencies represent 0 and 1 |
| Deviation | 47.60 kHz | How far each symbol shifts from centre |
| Data rate | 99.97 kbps | Bit rate on the air |
| Receive bandwidth | 270.83 kHz | Width of the receiver's filter |
| Sync word | 211, 145 | A fixed pattern starting every packet, so the receiver only accepts our traffic |
| CRC | on | Checksum; corrupted packets are rejected in hardware |
| Packet length | variable, max 61 B | Our packets are short text strings |
| PA power | 10 | Transmit power setting |

### The channel plan, and why 400 kHz

Five channels: **433.05, 433.45, 433.85, 434.25, 434.65 MHz**, all inside
the licence-free 433.05-434.79 MHz ISM band.

The spacing is the part worth understanding, because we got it wrong at
first and the measurements caught it.

By **Carson's rule**, one transmission occupies roughly

```
BW  =  2 x (deviation + bitrate/2)
    =  2 x (47.6 + 50)
    ≈  195 kHz
```

The original design spaced channels **200 kHz** apart with a **812.50 kHz**
receive bandwidth. Two problems followed:

1. Each signal was ~195 kHz wide in a 200 kHz grid - the transmissions
   nearly touched their neighbours.
2. The receiver's filter (±406 kHz) was **wider than the entire 800 kHz
   hop span**, so a receiver tuned to any one channel still heard most of
   the others.

Run 4 measured this directly: a receiver stranded on a single channel
still picked up **50 of 100** transmissions. With that configuration,
hopping gave essentially no frequency isolation, so the anti-jamming
premise would not have held up.

The fix: **400 kHz spacing with a 270.83 kHz filter (±135 kHz)**. The
nearest energy from an adjacent channel now sits about 302 kHz off
centre, well outside the filter. The channels are genuinely separate.

### Processing gain

The spread-spectrum figure of merit, and the Module 6 tie-in:

```
PG  =  total hopping bandwidth / instantaneous bandwidth
    ≈  1.8 MHz / 195 kHz
    ≈  9.2      (about 9.6 dB)
```

In words: an interferer has to cover about nine times more spectrum to
affect us as much as it would a fixed link.

---

## 4. The three link designs

### A. Fixed frequency - the control

`01_fixed_tx` + `02_fixed_rx`

The transmitter sends 100 numbered packets on 433.05 MHz and stops. The
receiver counts what arrives. No hopping, no sensing. This is how a
conventional telemetry radio behaves, and it is the baseline everything
else is compared against.

Packet: `SEQ:42`

### B. Basic FHSS - hopping, but blind

`03_fhss_tx` + `04_fhss_rx`

The transmitter walks the channel list in order, one channel per packet.
It never looks at a channel before using it. If a channel is unusable, it
walks straight into it.

Packet: `SEQ:42,NEXT:3` - the sequence number plus **which channel it is
about to move to**.

### C. Adaptive FHSS - sense before hopping

`05_adaptive_tx` + `04_fhss_rx` (same receiver)

Before each hop the transmitter:

1. **Senses** - tunes briefly to the candidate channel and reads its RSSI
2. **Decides** - if the reading is above the threshold, treats it as occupied
3. **Avoids** - blacklists that channel for 3 cycles and tries the next
4. **Announces** - puts whichever channel it chose into the `NEXT` field

**The receiver is unchanged between B and C.** It just goes where it is
told. That is the design point worth emphasising: all the intelligence
sits at the transmitter, so the upgrade carries no risk to a working
receiver.

If every channel looks occupied, it falls back to hopping sequentially
rather than stalling - a link that keeps trying beats a link that stops.

---

## 5. How the two ends stay synchronised

This is the heart of the protocol and the most likely thing to be asked
about.

Hopping only works if both ends are on the same channel at the same
moment. Normally that needs a shared clock or a separate control channel.
We avoid both: **the hop schedule travels inside the data.**

```
TX on 433.05  ─ sends ─>  "SEQ:20,NEXT:1"
                          RX reads NEXT=1, retunes to 433.45
TX retunes to 433.45
TX on 433.45  ─ sends ─>  "SEQ:21,NEXT:2"
                          RX reads NEXT=2, retunes to 433.85
```

Elegant, and it costs nothing - but it has a failure mode we measured
rather than assumed:

> **If a packet is lost, the receiver loses more than that packet. It
> loses its instruction for where to go next.** The transmitter moves on,
> the receiver stays put, and the link is gone.

Run 4 is that failure, measured: **1 packet out of 100**.

### Rendezvous recovery (`RESYNC_ENABLED`)

The fix. If the receiver hears nothing valid for 2 seconds, it returns to
a pre-agreed channel - **433.05, the rendezvous channel** - and waits.
The transmitter passes through it once per cycle, so the link comes back
within about five packets.

This turns total collapse into partial loss. Runs 5 and 6 measure it.

---

## 6. How we emulate channel denial

**No interference is transmitted at any point in this project.** This is
deliberate, and there are three reasons:

1. Operating a jammer is illegal without authorisation.
2. It would need a third radio, which we do not have.
3. Emulation is perfectly repeatable, so runs are actually comparable.

Instead, `DENY_MASK` marks channels as denied in firmware:

- **At the receiver** - packets arriving while tuned to a denied channel
  are discarded on arrival, taking their `NEXT` instruction with them.
  This reproduces exactly what an unusable channel costs.
- **At the adaptive transmitter** - `senseChannelRSSI()` returns a
  synthetic -35 dBm for a denied channel, so the avoidance logic reacts
  as it would to a genuinely occupied one.

### What this does and does not prove

Say this plainly, because an examiner will ask:

- **It validates the avoidance and recovery logic** - the decision-making
  under channel denial.
- **It does not validate the RF sensing front end** against a real
  interferer. Only run 7, where nothing is denied, uses genuine radio
  readings.
- Testing against a real interference source needs a third radio and a
  conducted (cabled) setup, and is correctly listed as future work.

---

## 7. The nine runs

| # | Mode | Denied | What it is for |
|---|---|---|---|
| 1 | Fixed | 0 | The control. Proves the link is healthy |
| 2 | Fixed | 1 | A fixed link with its channel denied. **Motivates the project** |
| 3 | Basic FHSS | 0 | Hopping baseline. Proves even use of all 5 channels |
| 4 | Basic FHSS, no recovery | 1 | **The collapse.** Shows in-band scheduling is fragile |
| 5 | Basic FHSS + rendezvous | 1 | Recovery turns collapse into partial loss |
| 6 | Basic FHSS + rendezvous | 2 | Degradation scales with how much is denied |
| 7 | Adaptive | 0 | Adaptive baseline, and the only run using real RSSI readings |
| 8 | Adaptive | 1 | **The payoff.** Avoids the denied channel entirely |
| 9 | Adaptive | 2 | Still works with two channels gone |

### The story the table tells

1. Fixed links die when their channel goes (run 2)
2. Hopping helps - but naive hopping dies differently, by losing sync (run 4)
3. Recovery keeps it alive but it keeps walking back into the bad channel (runs 5, 6)
4. Sensing avoids the bad channel in the first place (runs 8, 9)

Each step exists because the previous one failed in a specific,
measured way. That progression is the project.

---

## 8. Reading the results

Every run ends with a summary. The lines that matter:

```
Packets sent     : 100      <- always 100
Packets received : 97       <- unique sequence numbers accepted
Packets lost     : 3        <- 100 minus received
Packet loss      : 3.00 %   <- the headline metric
Denied drops     : 20       <- heard but discarded (emulated denial)
Resync events    : 4        <- times the receiver fell back to rendezvous
Average RSSI     : -42.8    <- signal strength, dBm (less negative = stronger)

Packets received per channel:
  433.05 MHz : 20
  433.45 MHz : 20
  433.85 MHz : 0   <- denied
  ...
```

**The per-channel table is the most convincing output in the project.**
In run 3 it shows roughly 20 per channel, proving the hop schedule really
is cycling evenly. In run 8 it should show **zero on the denied channel**,
proving the avoidance logic actually worked.

Two distinctions worth being precise about:

- **Lost** vs **denied drops**: a denied drop was *heard and discarded*.
  A loss is any packet not accepted, whether heard or not. Denied drops
  are a subset of losses, which is why the two numbers rarely match.
- **Received** counts *unique* sequence numbers. A duplicate cannot
  inflate it.

---

## 9. Known limitations - state these before you are asked

1. **Denial is emulated in firmware, not transmitted.** Validates logic,
   not the RF sensing front end.
2. **Five channels is a small hop set.** Real systems use dozens. With
   five, denying two removes 40 % of the spectrum.
3. **The hop sequence is a fixed, predictable order.** Anyone observing
   it could follow. A real system would derive it from a shared secret.
   Listed as future work.
4. **The rendezvous channel is a single point of weakness.** If 433.05
   were denied, recovery would never complete.
5. **Sensing costs time.** Each hop adds roughly 5-30 ms of sensing, so
   the adaptive runs are slower. That is a real trade-off, and it is
   reported rather than hidden.
6. **Short range, benchtop conditions.** No mobility, no multipath, no
   real interference environment.

---

## 10. Questions to expect

**"Why is FHSS worse than fixed when nothing is denied?"**
Because hopping costs overhead - retuning takes time and each hop is a
chance to lose sync. Hopping is not free; it buys resilience by giving up
a little reliability. The denied-channel runs are where it pays off.

**"What happens if the receiver misses the NEXT instruction?"**
It is stranded. We measured it: run 4, one packet out of a hundred.
Rendezvous recovery is our fix, and runs 5 and 6 measure how well it
works.

**"Is this really anti-jamming if you never jammed anything?"**
We emulate channel denial in firmware rather than transmit interference,
because operating a jammer needs authorisation and we have only two
radios. It validates the decision logic. Real RF validation needs a third
radio and a conducted setup - that is stated as future work.

**"Why 400 kHz spacing?"**
Our signal is about 195 kHz wide by Carson's rule. At the original 200 kHz
spacing with an 812.5 kHz receive filter, the filter was wider than the
whole hop span - we measured a stranded receiver still hearing half the
traffic. 400 kHz spacing with a 270.83 kHz filter makes the channels
genuinely independent.

**"What is novel here?"**
Sense-before-hop with blacklisting is established prior art
(US 6,169,761 claims RSSI-versus-threshold channel assessment with busy-channel
skipping and a rendezvous mechanism). What this project contributes is a
working low-cost implementation plus the measured finding that in-band hop
scheduling fails catastrophically rather than gracefully under channel
denial, and that sensing avoids that failure mode entirely.

**"Could this go on a real drone?"**
It would sit where a SiK telemetry radio sits, between the flight
controller and the ground station, carrying MAVLink. Sensing overhead is
fine for telemetry but too slow for primary flight control, so we scope
it as the telemetry and failsafe link.

---

## 11. The files

```
firmware/
  shared/rf_config.h      every radio setting + the channel plan
  01_fixed_tx/            fixed transmitter       (runs 1-2)
  02_fixed_rx/            fixed receiver          (runs 1-2)
  03_fhss_tx/             basic FHSS transmitter  (runs 3-6)
  04_fhss_rx/             FHSS receiver           (runs 3-9, shared)
  05_adaptive_tx/         adaptive transmitter    (runs 7-9)
  RUN_GUIDE.md            manual procedure

analysis/
  run_matrix.py           automated: compile, upload, capture, record
  dual_monitor.py         watch both boards on one timeline
  plot_results.py         build the figures

results/
  results.csv             one row per run
  run<N>_<timestamp>.log  full serial capture per run
  fig1..3*.png            the figures
```

`DENY_MASK` is a bitmask - bit *i* denies channel *i*:
`0x01` denies 433.05, `0x04` denies 433.85, `0x14` denies both 433.85 and
434.65.
