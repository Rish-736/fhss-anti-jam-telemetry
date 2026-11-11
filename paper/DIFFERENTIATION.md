# How this paper differs from the work it started from

Prepared for the faculty guide's question: *which paper is the idea taken
from, and how is ours different?*

---

## 1. The base paper

**C. Atheeq, Z. Gulzar, M. S. Al Reshan, H. Alshahrani, A. Sulaiman and
A. Shaikh, "Securing UAV Networks: A Lightweight Chaotic-Frequency
Hopping Approach to Counter Jamming Attacks," *IEEE Access*, vol. 12,
pp. 38685–38699, 2024, doi: 10.1109/ACCESS.2024.3375343.**

This is reference [9] in our paper and the nearest neighbour to our
topic: UAV link, 
frequency hopping, anti-jamming, described as lightweight.

**What it does.** It generates the hop *sequence* from a chaotic map.
The argument is that a chaotic generator produces an order of channels
an adversary cannot predict from observing past hops, so a jammer cannot
follow the link. It is evaluated in a network simulator.

**What it does not do.** It does not report what happens when a channel
in the hop set simply becomes unusable, it does not model delivery
analytically, and it is not run on hardware.

---

## 2. The one-sentence answer

> *Their paper makes the hop sequence harder to predict. Ours is not
> about the sequence at all — it is about how the two radios agree on
> that sequence, and we show that the usual cheap way of agreeing has a
> failure mode nobody has measured.*

These are **orthogonal problems**. Even a perfectly unpredictable
chaotic sequence has to be communicated to the receiver somehow. If it
is communicated the way most low-cost links do it — inside the data
packets — it inherits exactly the fragility we report. Our result
therefore applies *to* their scheme rather than competing with it.

---

## 3. Point-by-point difference

| Dimension | Atheeq *et al.* [9] | This work |
|---|---|---|
| **Object of study** | Hop sequence *generation* | Hop schedule *distribution* |
| **Mechanism studied** | Chaotic map | In-band next-channel announcement |
| **Adversary assumed** | Predicts/follows the sequence | Renders part of the hop set unusable |
| **Evaluation** | Network simulation | Two-node COTS hardware, real RF at 433 MHz |
| **Headline output** | A scheme that mitigates jamming | A closed-form delivery model, validated against measurement |
| **Failure analysis** | Not reported | The primary contribution |
| **Denial method** | Modelled jammer | Firmware-emulated; nothing is transmitted |
| **Contribution type** | Design | Measurement + analysis |

The last row is the important one. **We are not proposing a competing
scheme.** We are reporting a characterisation. That is a different
*kind* of paper, which is the strongest possible answer to "is this a
copy of something".

---

## 4. The four claims that are ours

Each of these is new as far as we can establish, each is measured, and
none of them appears in the base paper.

**C1 — Schedule-coupled loss.** In a self-scheduled hopping link, a lost
packet is also a lost *schedule*, because the packet carried the
next-channel instruction. Denying one channel of five removed **98 %**
of traffic, not the 20 % a per-channel argument predicts — an
amplification of **4.9×**. We trace the mechanism, not just the number.

**C2 — Denial saturation.** Once rendezvous recovery is added, delivery
stops depending on *how many* channels are denied. It depends only on
*d*, the hop distance from the rendezvous channel to the **first** denied
one. Denying a second channel changed the measured delivery count by
**zero packets**.

**C3 — A closed-form model.** Derived from the mechanism, not fitted:

- without recovery: *R* = *d*
- with recovery: *R* ≈ *d*·*M*/*N*

With *d* = 2, *N* = 5, *M* = 100 it predicts **2, 40, 40**. We measured
**2, 40, 40**. Three for three, no fitted parameter.

**C4 — A quantified design rule.** Recovery is necessary but not
sufficient: it treats the symptom (98 % → 60 %) and then saturates.
Pre-hop clear-channel assessment removes the cause and takes the same
link to **2 %**.

---

## 5. What we deliberately do *not* claim as novel

State these first. Conceding prior art is what makes the remaining claim
credible, and a reviewer who finds unacknowledged prior art will reject
the paper outright.

| Mechanism | Prior art we cite |
|---|---|
| Frequency hopping | Pickholtz *et al.* [7], 1982 |
| Sense a channel, blacklist it | Bluetooth AFH [14]; Kim *et al.* [15] |
| Blacklisting with cooldown | Kotsiou [19], Elsts [20], Cena [21] |
| Rendezvous to re-acquire a link | Lin [23], Tan and Yuan [24] |
| RSSI threshold → "channel busy" | US 6,169,761 [25] |
| Receiver-side resync under jamming | US 8,165,242 [26] |

Section II-C of the paper says in as many words that *"the sensing
mechanism in this paper is therefore not claimed as novel; it is used as
the control that establishes the cost of the coupling."*

---

## 6. What changed in the paper

| | Before | Now |
|---|---|---|
| Title | *Adaptive Frequency Hopping for Jam-Resistant UAV Telemetry* | *Measuring Schedule Loss in Self-Scheduled Frequency-Hopping Links* |
| Framing | "We built an anti-jamming link" | "We measured and modelled a failure mode" |
| Related Work | 4 paragraphs | 7 subsections, including a dedicated **Hop-Sequence Secrecy vs Hop-Schedule Distribution** section |
| Differentiation | One sentence | Explicit, plus **Table I** comparing against [9] |
| References | 8 | **29** |
| Length | 7 pages | 8 pages |

The old title was the biggest liability: it described the paper as
another anti-jamming scheme, which is the crowded category. The new
title names the thing we actually contribute and introduces our own
term, *self-scheduled*.

---

## 7. An honest note on "no similarity"

Two different things get called similarity, and they need separate
answers.

**Text overlap (what Turnitin / iThenticate measure).** Every word of
this paper was written for it. Expected overlap is confined to standard
phrases, reference strings and the regulatory citation. **This should
already be low — but run an actual similarity check before submitting.**
Neither I nor anyone else can certify a number without running the tool
against the real corpus.

**Contribution overlap (novelty).** This cannot be proven absent. What
can be done is what we have done: identify the nearest prior art,
state what it does, state what it does not do, and make the remaining
claim narrow enough to defend. The claim that survives — a measured
amplification factor, a saturation effect and a closed-form model for
in-band hop scheduling — is specific enough that an overlapping paper
would have to be very close indeed.

**What would strengthen it further, in order of value:**

1. **Repeat runs 4, 5 and 8 three times each (~25 min).** Every number
   in the matrix is currently a single run with no error bars. This is
   the most common reason a measurement paper gets rejected, and it is
   also the cheapest thing on this list to fix.
2. **Vary *d*.** The model is validated at *d* = 2 only. Denying channel
   1 (*d* = 1) and channel 3 (*d* = 3) and showing the prediction holds
   would turn one validated point into a validated *curve*. This is the
   single highest-value experiment available and needs no new hardware.
3. **A real interferer.** A signal generator in a shielded enclosure
   would let the paper drop the emulation caveat.

Item 2 is worth emphasising: right now the model is confirmed at one
value of its only parameter. Confirming it at three would move the
paper from "interesting observation" to "validated model".
