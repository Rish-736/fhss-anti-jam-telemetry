"""
Build the figures used in the IEEE paper from the measured logs and the
run matrix. Every number plotted here is read back out of files in
results/ - nothing is entered by hand.

    python paper/make_paper_figures.py

Outputs land in paper/figures/ at 600 dpi. All figures are laid out for
a single IEEE column (3.5 in) so they drop straight into the two-column
body without section tricks.
"""

import os
import re
import csv
import statistics
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")
OUT = os.path.join(HERE, "figures")
os.makedirs(OUT, exist_ok=True)

COL = 3.45          # IEEE single column, inches
DPI = 600

NAVY = "#12263F"
BLUE = "#1B4965"
CYAN = "#1282A2"
RED = "#B23A48"
GREY = "#9AA5B1"
LIGHT = "#E4E9EE"
PINK = "#F7E3E6"

CHANNELS = [433.05, 433.45, 433.85, 434.25, 434.65]

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 7,
    "axes.labelsize": 7,
    "axes.titlesize": 7,
    "legend.fontsize": 6.3,
    "xtick.labelsize": 6.3,
    "ytick.labelsize": 6.3,
    "axes.linewidth": 0.6,
    "lines.linewidth": 1.1,
})


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(NAVY)
    ax.tick_params(colors=NAVY, width=0.6, length=2.5)
    ax.yaxis.grid(True, color=LIGHT, linewidth=0.5)
    ax.set_axisbelow(True)


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=DPI, bbox_inches="tight", pad_inches=0.02,
                facecolor="white")
    plt.close(fig)
    print("wrote", os.path.relpath(path, ROOT))


# ---------------------------------------------------------------------
# data loading
# ---------------------------------------------------------------------

def load_matrix():
    rows = []
    with open(os.path.join(RESULTS, "results.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("loss_pct"):
                rows.append(r)
    return rows


def latest_log(run):
    cands = sorted(f for f in os.listdir(RESULTS)
                   if f.startswith(f"run{run}_") and f.endswith(".log"))
    return os.path.join(RESULTS, cands[-1]) if cands else None


def per_channel(run):
    """Read the per-channel tally straight out of the receiver summary."""
    path = latest_log(run)
    counts, denied = {}, set()
    if not path:
        return counts, denied
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.search(r"\|\s+(4\d\d\.\d\d) MHz : (\d+)(\s+<- denied)?", line)
        if m:
            counts[float(m.group(1))] = int(m.group(2))
            if m.group(3):
                denied.add(float(m.group(1)))
    return counts, denied


def sense_readings(run):
    """Every RSSI value the adaptive transmitter printed while sensing."""
    path = latest_log(run)
    out = defaultdict(list)
    if not path:
        return out
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.search(r"sensed ([\d.]+) MHz -> RSSI (-?\d+)", line)
        if m:
            out[float(m.group(1))].append(int(m.group(2)))
    return out


# ---------------------------------------------------------------------
# Fig. 1  system architecture
# ---------------------------------------------------------------------

def fig_architecture():
    fig, ax = plt.subplots(figsize=(COL, 3.05))
    ax.set_xlim(0, 101)
    ax.set_ylim(-3, 98.5)
    ax.axis("off")

    def box(x, y, w, h, label, fc="white", ec=NAVY, fs=6.6, bold=False):
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.6",
            linewidth=0.8, edgecolor=ec, facecolor=fc))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
                fontsize=fs, color=NAVY,
                fontweight="bold" if bold else "normal", linespacing=1.45)

    def arrow(x1, y1, x2, y2, ls="-", c=NAVY, st="-|>"):
        ax.add_patch(FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle=st, linestyle=ls,
            mutation_scale=7, linewidth=0.8, color=c, shrinkA=1, shrinkB=1))

    # ---- transmit node ----
    ax.add_patch(Rectangle((2, 64), 92, 33, linewidth=0.6, edgecolor=GREY,
                           facecolor="#F7F9FB", zorder=0))
    ax.text(48, 93.4, "TRANSMIT NODE  (airborne side)", ha="center",
            fontsize=6.3, color=BLUE, fontweight="bold")
    box(5, 79, 33, 11, "ESP32 DevKit v1", bold=True)
    box(54, 79, 33, 11, "CC1101 433 MHz", bold=True)
    arrow(38, 84.5, 54, 84.5)
    ax.text(46, 86.0, "SPI", ha="center", fontsize=5.6, color=BLUE)
    box(5, 66, 82, 10,
        "sense before hop  |  blacklist + cooldown\nannounce chosen channel in NEXT",
        fc="#EEF3F7", ec=BLUE, fs=5.8)

    # ---- air interface ----
    ax.add_patch(FancyBboxPatch(
        (14, 37), 66, 21, boxstyle="round,pad=0.6,rounding_size=1.6",
        linewidth=0.9, edgecolor=CYAN, facecolor="#E8F4F8"))
    ax.text(47, 54.0, "5-CHANNEL FHSS AIR INTERFACE", ha="center",
            fontsize=6.3, color=BLUE, fontweight="bold")
    ax.text(47, 45.0,
            "433.05 - 434.65 MHz, 400 kHz spacing\n"
            "2-FSK, 99.97 kb/s, 47.60 kHz deviation\n"
            "payload   SEQ:<n>,NEXT:<hop>",
            ha="center", va="center", fontsize=5.9, color=NAVY,
            linespacing=1.6)
    arrow(70, 64, 70, 58)
    arrow(24, 37, 24, 31)

    # ---- receive node ----
    ax.add_patch(Rectangle((2, -2), 92, 33, linewidth=0.6, edgecolor=GREY,
                           facecolor="#F7F9FB", zorder=0))
    ax.text(48, 27.4, "RECEIVE NODE  (ground side)", ha="center",
            fontsize=6.3, color=BLUE, fontweight="bold")
    box(5, 13, 33, 11, "CC1101 433 MHz", bold=True)
    box(54, 13, 33, 11, "ESP32 DevKit v1", bold=True)
    arrow(38, 18.5, 54, 18.5)
    ax.text(46, 20.0, "SPI", ha="center", fontsize=5.6, color=BLUE)
    box(5, 0, 82, 10,
        "follow NEXT  |  CRC + unique-sequence tally\nrendezvous recovery on timeout",
        fc="#EEF3F7", ec=BLUE, fs=5.8)

    # ---- host link ----
    ax.annotate("", xy=(92, 18.5), xytext=(92, 84.5),
                arrowprops=dict(arrowstyle="-", linewidth=0.7,
                                color=GREY, linestyle=":"))
    ax.text(96.5, 51, "USB serial to ground-station dashboard",
            rotation=90, va="center", ha="center", fontsize=5.5,
            color=GREY)

    save(fig, "fig1_architecture.png")


# ---------------------------------------------------------------------
# Fig. 2  channel plan
# ---------------------------------------------------------------------

def fig_channel_plan():
    fig, ax = plt.subplots(figsize=(COL, 1.75))

    band_lo, band_hi = 433.05, 434.79
    sig_bw = 0.195
    rx_bw = 0.27083

    for i, f in enumerate(CHANNELS):
        ax.add_patch(Rectangle((f - rx_bw / 2, 0), rx_bw, 1.22,
                               facecolor="#DCE8EF", edgecolor=CYAN,
                               linewidth=0.5, zorder=1))
        ax.add_patch(Rectangle((f - sig_bw / 2, 0), sig_bw, 1.0,
                               facecolor=BLUE, edgecolor="none", zorder=2))
        ax.text(f, 1.30, f"CH{i}", ha="center", fontsize=5.8, color=NAVY)

    g1 = CHANNELS[1] + sig_bw / 2
    g2 = CHANNELS[2] - sig_bw / 2
    ax.annotate("", xy=(g1, 1.66), xytext=(g2, 1.66),
                arrowprops=dict(arrowstyle="<|-|>", linewidth=0.7,
                                color=RED, mutation_scale=5))
    ax.text((g1 + g2) / 2, 1.74, "205 kHz guard", ha="center",
            fontsize=5.8, color=RED)
    ax.text(432.99, 1.74, "400 kHz spacing", ha="left", fontsize=5.8,
            color=NAVY)

    ax.text((band_lo + band_hi) / 2, -0.52,
            "433.05 - 434.79 MHz licence-exempt band",
            ha="center", fontsize=5.8, color=NAVY)

    ax.set_xlim(432.93, 434.91)
    ax.set_ylim(-0.72, 1.98)
    ax.set_yticks([])
    ax.set_xticks([433.05, 433.45, 433.85, 434.25, 434.65])
    ax.set_xticklabels(["433.05", "433.45", "433.85", "434.25", "434.65"],
                       fontsize=5.6)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_position(("data", 0))
    ax.spines["bottom"].set_color(NAVY)
    ax.tick_params(colors=NAVY, width=0.6, length=2.5)

    ax.add_patch(Rectangle((0, 0), 0, 0, facecolor=BLUE,
                           label="occupied bandwidth, 195 kHz"))
    ax.add_patch(Rectangle((0, 0), 0, 0, facecolor="#DCE8EF",
                           edgecolor=CYAN, linewidth=0.5,
                           label="receiver passband, 270.83 kHz"))
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.50), ncol=1,
              frameon=False, handlelength=1.3, fontsize=5.8,
              labelspacing=0.25)

    save(fig, "fig2_channel_plan.png")


# ---------------------------------------------------------------------
# Fig. 3  in-band hop scheduling and its failure mode
# ---------------------------------------------------------------------

def fig_protocol():
    fig, axes = plt.subplots(2, 1, figsize=(COL, 3.2))

    for ax, denied, title in zip(
            axes, [None, 2],
            ["(a) nominal operation",
             "(b) denied channel, no recovery"]):
        ax.set_xlim(-0.75, 5.8)
        ax.set_ylim(-1.45, 5.45)
        ax.axis("off")
        ax.text(-0.75, 5.1, title, ha="left", fontsize=6.6, color=NAVY,
                fontweight="bold")

        for i in range(5):
            ax.text(-0.70, i, f"CH{i}", fontsize=5.8, color=NAVY,
                    va="center", ha="left")
            ax.plot([0.15, 5.7], [i, i], color=LIGHT, linewidth=0.5,
                    zorder=0)

        tx = [0, 1, 2, 3, 4]
        for k, ch in enumerate(tx):
            x = 0.55 + k * 1.08
            bad = denied is not None and ch == denied
            ax.scatter([x], [ch], s=24, marker="s", zorder=3,
                       color=RED if bad else BLUE,
                       edgecolor="white", linewidth=0.4)
            ax.text(x, ch + 0.24, f"SEQ:{20 + k}\nNEXT:{(ch + 1) % 5}",
                    ha="center", va="bottom", fontsize=5.0, color=NAVY,
                    linespacing=1.25)

        rx = tx if denied is None else [0, 1, 2, 2, 2]
        for k in range(4):
            x1, x2 = 0.55 + k * 1.08, 0.55 + (k + 1) * 1.08
            moved = rx[k] != rx[k + 1]
            ax.add_patch(FancyArrowPatch(
                (x1, rx[k] - 0.2), (x2, rx[k + 1] - 0.2),
                arrowstyle="-|>", mutation_scale=5, linewidth=0.8,
                color=CYAN if moved else GREY,
                linestyle="-" if moved else ":"))

        if denied is None:
            ax.text(2.7, -1.25,
                    "each packet names the next channel, so no shared\n"
                    "clock and no separate control channel are needed",
                    ha="center", fontsize=5.7, color=BLUE, linespacing=1.45)
        else:
            ax.text(2.7, -1.25,
                    "the packet on CH2 is discarded and its NEXT field\n"
                    "goes with it, stranding the receiver on CH2",
                    ha="center", fontsize=5.7, color=RED, linespacing=1.45)

    fig.subplots_adjust(hspace=0.20)
    save(fig, "fig3_protocol.png")


# ---------------------------------------------------------------------
# Fig. 4  packet loss against denied channels
# ---------------------------------------------------------------------

def fig_loss():
    rows = load_matrix()

    def key(r):
        if r["mode"] == "FIXED":
            return "Fixed frequency"
        if r["mode"] == "ADAPTIVE":
            return "Adaptive FHSS"
        return ("Basic FHSS + rendezvous" if int(r["resync"])
                else "Basic FHSS (no recovery)")

    series = defaultdict(list)
    for r in rows:
        series[key(r)].append((int(r["denied_count"]), float(r["loss_pct"])))

    order = ["Fixed frequency", "Basic FHSS (no recovery)",
             "Basic FHSS + rendezvous", "Adaptive FHSS"]
    colour = dict(zip(order, [RED, GREY, BLUE, CYAN]))
    marker = dict(zip(order, ["s", "^", "D", "o"]))

    fig, ax = plt.subplots(figsize=(COL, 2.35))
    style(ax)
    for name in order:
        pts = sorted(series.get(name, []))
        if not pts:
            continue
        ax.plot([p[0] for p in pts], [p[1] for p in pts],
                marker=marker[name], markersize=3.6, color=colour[name],
                label=name, markeredgecolor="white", markeredgewidth=0.4)

    ax.set_xlabel("Denied channels (of 5)")
    ax.set_ylabel("Packet loss (%)")
    ax.set_xticks([0, 1, 2])
    ax.set_ylim(-5, 110)
    ax.legend(frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.27), ncol=2, handlelength=1.6,
              columnspacing=1.0, fontsize=6.0)
    save(fig, "fig4_loss_vs_denial.png")


# ---------------------------------------------------------------------
# Fig. 5  per-channel packet distribution
# ---------------------------------------------------------------------

def fig_per_channel():
    runs = [(3, "(a) basic FHSS, 0 denied"),
            (5, "(b) basic + rendezvous, 1 denied"),
            (8, "(c) adaptive, 1 denied"),
            (9, "(d) adaptive, 2 denied")]

    fig, axes = plt.subplots(2, 2, figsize=(COL, 2.9), sharey=True)
    for ax, (run, label) in zip(axes.ravel(), runs):
        counts, denied = per_channel(run)
        vals = [counts.get(f, 0) for f in CHANNELS]
        style(ax)
        # A denied channel reports zero, so shade its column: a
        # zero-height bar would otherwise be invisible.
        for i, f in enumerate(CHANNELS):
            if f in denied:
                ax.axvspan(i - 0.5, i + 0.5, color=PINK, zorder=0)
        ax.bar(range(5), vals, color=BLUE, width=0.64, edgecolor="none",
               zorder=2)
        ax.set_xticks(range(5))
        ax.set_xticklabels([str(i) for i in range(5)], fontsize=5.8)
        for i, f in enumerate(CHANNELS):
            if f in denied:
                ax.get_xticklabels()[i].set_color(RED)
        ax.set_title(label, fontsize=6.0, color=NAVY, pad=3)
        ax.set_xlim(-0.6, 4.6)
        ax.set_ylim(0, 42)
        for i, v in enumerate(vals):
            ax.text(i, v + 1.2, str(v), ha="center", fontsize=5.0,
                    color=NAVY, zorder=3)

    for ax in axes[1]:
        ax.set_xlabel("Channel index", fontsize=6.3)
    for ax in axes[:, 0]:
        ax.set_ylabel("Packets", fontsize=6.3)

    fig.subplots_adjust(wspace=0.14, hspace=0.70)
    handles = [plt.Rectangle((0, 0), 1, 1, color=BLUE),
               plt.Rectangle((0, 0), 1, 1, color=PINK)]
    fig.legend(handles, ["packets received", "denied channel"],
               loc="lower center", bbox_to_anchor=(0.5, -0.08),
               ncol=2, frameon=False, fontsize=6.0, handlelength=1.3)
    save(fig, "fig5_per_channel.png")


# ---------------------------------------------------------------------
# Fig. 6  measured noise floor against the decision threshold
# ---------------------------------------------------------------------

def fig_noise_floor():
    d = sense_readings(7)
    allv = [v for vs in d.values() for v in vs]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(COL, 3.0))

    style(ax1)
    lo, hi = min(allv) - 1, max(allv) + 1
    ax1.hist(allv, bins=range(lo, hi + 2), color=BLUE, edgecolor="white",
             linewidth=0.4)
    ax1.axvline(-75, color=RED, linewidth=1.0, linestyle="--")
    ax1.text(-74, ax1.get_ylim()[1] * 0.95,
             "decision threshold\n$\\Lambda$ = -75 dBm",
             color=RED, fontsize=5.8, va="top", ha="left", linespacing=1.4)
    ax1.set_xlabel("Sensed RSSI (dBm)")
    ax1.set_ylabel("Observations")
    ax1.set_xlim(-112, -62)
    ax1.set_title(f"(a) genuine channel assessments, run 7 (n = {len(allv)})",
                  fontsize=6.4, color=NAVY, pad=3)

    style(ax2)
    means = [statistics.mean(d[f]) for f in CHANNELS]
    sds = [statistics.pstdev(d[f]) for f in CHANNELS]
    ax2.errorbar(range(5), means, yerr=sds, fmt="o", markersize=3.4,
                 color=BLUE, ecolor=GREY, capsize=2.2, elinewidth=0.8,
                 markeredgecolor="white", markeredgewidth=0.4)
    ax2.set_xticks(range(5))
    ax2.set_xticklabels([str(i) for i in range(5)])
    ax2.set_xlabel("Channel index")
    ax2.set_ylabel("Mean RSSI (dBm)")
    ax2.set_xlim(-0.5, 4.5)
    ax2.set_ylim(-110, -100)
    ax2.set_title("(b) per-channel noise floor, mean $\\pm$ s.d.",
                  fontsize=6.4, color=NAVY, pad=3)

    fig.subplots_adjust(hspace=0.80)
    save(fig, "fig6_noise_floor.png")
    print(f"   noise floor: mean {statistics.mean(allv):.1f} dBm, "
          f"sd {statistics.pstdev(allv):.1f}, "
          f"range {min(allv)}..{max(allv)}, "
          f"above threshold {sum(1 for v in allv if v >= -75)}/{len(allv)}")


# ---------------------------------------------------------------------
# Fig. 7  sensing effort
# ---------------------------------------------------------------------

def fig_sensing():
    fig, ax = plt.subplots(figsize=(COL, 2.0))
    style(ax)

    runs = [7, 8, 9]
    senses, occupied = [], []
    for r in runs:
        text = open(latest_log(r), encoding="utf-8",
                    errors="replace").read()
        senses.append(len(re.findall(r"sensed [\d.]+ MHz -> RSSI", text)))
        occupied.append(len(re.findall(r"MHz OCCUPIED", text)))

    x = range(len(runs))
    w = 0.36
    ax.bar([i - w / 2 for i in x], senses, w, color=BLUE,
           label="channel assessments")
    ax.bar([i + w / 2 for i in x], occupied, w, color=RED,
           label="occupied verdicts")
    for i, (s, o) in enumerate(zip(senses, occupied)):
        ax.text(i - w / 2, s + 4, str(s), ha="center", fontsize=5.8,
                color=NAVY)
        ax.text(i + w / 2, o + 4, str(o), ha="center", fontsize=5.8,
                color=NAVY)

    ax.set_xticks(list(x))
    ax.set_xticklabels([f"Run {r}\n{n} denied"
                        for r, n in zip(runs, [0, 1, 2])], fontsize=6.0)
    ax.set_ylabel("Events per 100 packets")
    ax.set_ylim(0, 210)
    ax.legend(frameon=False, loc="upper left", handlelength=1.4,
              fontsize=6.0)
    save(fig, "fig7_sensing.png")
    print("   senses:", dict(zip(runs, senses)),
          " occupied:", dict(zip(runs, occupied)))


if __name__ == "__main__":
    for f in os.listdir(OUT):
        if f.endswith(".png"):
            os.remove(os.path.join(OUT, f))
    fig_architecture()
    fig_channel_plan()
    fig_protocol()
    fig_loss()
    fig_per_channel()
    fig_noise_floor()
    fig_sensing()
