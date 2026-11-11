"""
Generate the result figures from results/results.csv.

Usage:
    python analysis/plot_results.py

Rows with a blank loss_pct are skipped, so this can be run while the
test matrix is still being filled in.
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CSV = os.path.join(ROOT, "results", "results.csv")
OUT = os.path.join(ROOT, "results")

NAVY = "#0B2545"
BLUE = "#134074"
CYAN = "#00B4D8"
RED = "#E63946"
GREY = "#8DA9C4"

MODE_LABEL = {
    "FIXED": "Fixed frequency",
    "BASIC_NORESYNC": "Basic FHSS (no resync)",
    "BASIC_RESYNC": "Basic FHSS + rendezvous",
    "ADAPTIVE": "Adaptive FHSS",
}
MODE_COLOR = {
    "FIXED": RED,
    "BASIC_NORESYNC": GREY,
    "BASIC_RESYNC": BLUE,
    "ADAPTIVE": CYAN,
}
MODE_ORDER = ["FIXED", "BASIC_NORESYNC", "BASIC_RESYNC", "ADAPTIVE"]


def style(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GREY)
    ax.spines["bottom"].set_color(GREY)
    ax.tick_params(colors=NAVY)
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8)
    ax.set_axisbelow(True)


def load():
    df = pd.read_csv(CSV)
    df = df.dropna(subset=["loss_pct"])
    if df.empty:
        return df

    def key(row):
        if row["mode"] == "FIXED":
            return "FIXED"
        if row["mode"] == "ADAPTIVE":
            return "ADAPTIVE"
        return "BASIC_RESYNC" if int(row["resync"]) == 1 else "BASIC_NORESYNC"

    df["mode_key"] = df.apply(key, axis=1)
    return df


def fig_loss_vs_denial(df):
    """The headline figure: packet loss against number of denied channels."""
    fig, ax = plt.subplots(figsize=(8, 5))

    for mk in MODE_ORDER:
        sub = df[df["mode_key"] == mk].sort_values("denied_count")
        if sub.empty:
            continue
        ax.plot(
            sub["denied_count"], sub["loss_pct"],
            marker="o", markersize=8, linewidth=2.5,
            color=MODE_COLOR[mk], label=MODE_LABEL[mk],
        )

    ax.set_xlabel("Number of denied channels (of 5)", color=NAVY, fontsize=11)
    ax.set_ylabel("Packet loss (%)", color=NAVY, fontsize=11)
    ax.set_title("Packet loss under emulated channel denial",
                 color=NAVY, fontsize=13, fontweight="bold", pad=15)
    ax.set_xticks(sorted(df["denied_count"].unique()))
    ax.set_ylim(-3, 105)
    ax.legend(frameon=False, fontsize=10)
    style(ax)

    fig.tight_layout()
    path = os.path.join(OUT, "fig1_loss_vs_denial.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def fig_mode_comparison(df):
    """Grouped bars comparing every mode at each denial level."""
    levels = sorted(df["denied_count"].unique())
    present = [mk for mk in MODE_ORDER if not df[df["mode_key"] == mk].empty]

    fig, ax = plt.subplots(figsize=(8, 5))
    width = 0.8 / max(len(present), 1)

    for i, mk in enumerate(present):
        sub = df[df["mode_key"] == mk]
        xs, ys = [], []
        for j, lvl in enumerate(levels):
            row = sub[sub["denied_count"] == lvl]
            if row.empty:
                continue
            xs.append(j + i * width - 0.4 + width / 2)
            ys.append(float(row["loss_pct"].iloc[0]))
        if not xs:
            continue
        bars = ax.bar(xs, ys, width * 0.9,
                      color=MODE_COLOR[mk], label=MODE_LABEL[mk])
        for b, y in zip(bars, ys):
            ax.text(b.get_x() + b.get_width() / 2, y + 1.5, f"{y:.0f}%",
                    ha="center", fontsize=9, color=NAVY)

    ax.set_xticks(range(len(levels)))
    ax.set_xticklabels([f"{l} denied" for l in levels], color=NAVY)
    ax.set_ylabel("Packet loss (%)", color=NAVY, fontsize=11)
    ax.set_title("Link performance by mode and denial level",
                 color=NAVY, fontsize=13, fontweight="bold", pad=15)
    ax.set_ylim(0, 110)
    ax.legend(frameon=False, fontsize=10)
    style(ax)

    fig.tight_layout()
    path = os.path.join(OUT, "fig2_mode_comparison.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def fig_rssi(df):
    sub = df.dropna(subset=["avg_rssi"])
    sub = sub[sub["avg_rssi"] != "NA"]
    if sub.empty:
        return None

    sub = sub.copy()
    sub["avg_rssi"] = sub["avg_rssi"].astype(float)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = [f"{MODE_LABEL[r.mode_key]}\n{int(r.denied_count)} denied"
              for r in sub.itertuples()]
    colors = [MODE_COLOR[r.mode_key] for r in sub.itertuples()]

    bars = ax.bar(range(len(sub)), sub["avg_rssi"], 0.6, color=colors)
    for b, y in zip(bars, sub["avg_rssi"]):
        ax.text(b.get_x() + b.get_width() / 2, y - 2.5, f"{y:.1f}",
                ha="center", fontsize=9, color="white", fontweight="bold")

    ax.set_xticks(range(len(sub)))
    ax.set_xticklabels(labels, fontsize=8, color=NAVY)
    ax.set_ylabel("Average RSSI (dBm)", color=NAVY, fontsize=11)
    ax.set_title("Received signal strength across runs",
                 color=NAVY, fontsize=13, fontweight="bold", pad=15)
    ax.set_ylim(min(sub["avg_rssi"]) - 10, 0)
    style(ax)

    fig.tight_layout()
    path = os.path.join(OUT, "fig3_rssi.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def main():
    df = load()
    if df.empty:
        print("No completed runs in results.csv yet - fill in loss_pct values.")
        return

    print(f"{len(df)} completed run(s) found.\n")
    for r in df.itertuples():
        print(f"  {MODE_LABEL[r.mode_key]:28s} "
              f"{int(r.denied_count)} denied -> {r.loss_pct:6.2f}% loss")
    print()

    for path in (fig_loss_vs_denial(df), fig_mode_comparison(df), fig_rssi(df)):
        if path:
            print("wrote", path)


if __name__ == "__main__":
    main()
