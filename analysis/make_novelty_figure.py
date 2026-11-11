"""
The one slide that carries the novelty claim.

Left:  the intuition everybody has (deny 1 of 5 channels -> lose 20%)
       against what was actually measured (98%).
Right: the closed-form saturation model against the measured counts for
       runs 4, 5 and 6.

Every measured number is read out of results/results.csv. Nothing here
is typed in by hand except the model, which is the point.

    python analysis/make_novelty_figure.py
"""

import os
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")

NAVY = "#12263F"
BLUE = "#1B4965"
CYAN = "#1282A2"
RED = "#B23A48"
GREY = "#9AA5B1"
AMBER = "#C77D28"

N = 5          # channels in the hopping set
M = 100        # packets per run
D = 2          # hops from the rendezvous channel to the denied one
               # (rendezvous = hop 0 = 433.05, denied = hop 2 = 433.85)


def load():
    rows = {}
    with open(os.path.join(RESULTS, "results.csv"), newline="") as f:
        for r in csv.DictReader(f):
            rows[int(r["run_id"])] = r
    return rows


def main():
    rows = load()
    r4, r5, r6 = (int(rows[i]["received"]) for i in (4, 5, 6))

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.edgecolor": NAVY,
        "axes.labelcolor": NAVY,
        "text.color": NAVY,
        "xtick.color": NAVY,
        "ytick.color": NAVY,
    })

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.6))

    # ---------------------------------------------------------------- left
    naive = 100.0 / N                      # "one channel of five is gone"
    actual = float(rows[4]["loss_pct"])

    bars = ax1.bar([0, 1], [naive, actual], width=0.55,
                   color=[GREY, RED], zorder=3)
    for x, v, lab in ((0, naive, "what everyone\nassumes"),
                      (1, actual, "what we\nmeasured")):
        ax1.text(x, v + 3, f"{v:.0f}%", ha="center", va="bottom",
                 fontsize=24, fontweight="bold",
                 color=GREY if x == 0 else RED)
        ax1.text(x, -7, lab, ha="center", va="top", fontsize=11)

    ax1.set_ylim(0, 118)
    ax1.set_xlim(-0.6, 1.6)
    ax1.set_xticks([])
    ax1.set_ylabel("packet loss")
    ax1.set_yticks([0, 20, 40, 60, 80, 100])
    ax1.set_yticklabels(["0%", "20%", "40%", "60%", "80%", "100%"])
    ax1.grid(axis="y", color="#E4E9EE", zorder=0)
    ax1.set_axisbelow(True)
    for s in ("top", "right"):
        ax1.spines[s].set_visible(False)
    ax1.set_title("Deny 1 of 5 hopping channels\n(no recovery, no sensing)",
                  fontsize=13, fontweight="bold", pad=14)
    ax1.annotate("the lost packet was carrying the\n"
                 "next-channel instruction with it,\n"
                 "so the link never finds its way back",
                 xy=(0.74, 52), xytext=(0.02, 88), fontsize=11, color=NAVY,
                 ha="center", va="top",
                 arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.4,
                                 connectionstyle="arc3,rad=-0.25"))

    # --------------------------------------------------------------- right
    labels = ["Run 4\nno recovery\n1 denied",
              "Run 5\n+ recovery\n1 denied",
              "Run 6\n+ recovery\n2 denied"]
    measured = [r4, r5, r6]
    model = [D, round(D * M / N), round(D * M / N)]

    x = range(3)
    w = 0.36
    ax2.bar([i - w / 2 for i in x], model, width=w, label="model",
            color="white", edgecolor=BLUE, linewidth=2.0, hatch="///",
            zorder=3)
    ax2.bar([i + w / 2 for i in x], measured, width=w, label="measured",
            color=CYAN, zorder=3)

    for i, (m, meas) in enumerate(zip(model, measured)):
        ax2.text(i - w / 2, m + 1.2, str(m), ha="center", va="bottom",
                 fontsize=13, fontweight="bold", color=BLUE)
        ax2.text(i + w / 2, meas + 1.2, str(meas), ha="center", va="bottom",
                 fontsize=13, fontweight="bold", color=CYAN)

    ax2.set_xticks(list(x))
    ax2.set_xticklabels(labels, fontsize=10)
    ax2.set_ylabel("packets delivered out of 100")
    ax2.set_ylim(0, 54)
    ax2.grid(axis="y", color="#E4E9EE", zorder=0)
    ax2.set_axisbelow(True)
    for s in ("top", "right"):
        ax2.spines[s].set_visible(False)
    ax2.legend(frameon=False, loc="upper left", fontsize=11)
    ax2.set_title("Closed-form prediction vs. measurement",
                  fontsize=13, fontweight="bold", pad=14)

    fig.text(0.590, 0.120, "R (no recovery)  =  d",
             ha="center", va="center", fontsize=15, color=NAVY,
             fontstyle="italic")
    fig.text(0.840, 0.120, "R (with recovery)  ≈  d · M / N",
             ha="center", va="center", fontsize=15, color=NAVY,
             fontstyle="italic")
    fig.text(0.715, 0.048,
             f"d = {D} hops from rendezvous to the denied channel   |   "
             f"N = {N} channels   |   M = {M} packets",
             ha="center", va="center", fontsize=10.5, color=GREY)

    fig.suptitle("In-band hop scheduling fails catastrophically, "
                 "and it fails predictably",
                 fontsize=16, fontweight="bold", color=NAVY, y=0.97)

    fig.subplots_adjust(left=0.07, right=0.965, top=0.80, bottom=0.24,
                        wspace=0.28)
    out = os.path.join(RESULTS, "fig_novelty_model.png")
    fig.savefig(out, dpi=200, facecolor="white")
    print("wrote", out)

    # sanity: the claim in the caption must hold
    assert model == measured, f"model {model} != measured {measured}"
    print("model reproduces all three runs exactly:", measured)


if __name__ == "__main__":
    main()
