"""Two single-column diagrams showing how the implemented algorithms work.

  fig_rx_state.png    receiver schedule-tracking state machine (Alg. 2)
  fig_sense_flow.png  sense-before-hop channel selection (Alg. 1)

Both are drawn to the same column width, palette and type size as
make_paper_figures.py so the figure set reads as one.

    python paper/make_algo_figures.py
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures")
os.makedirs(OUT, exist_ok=True)

COL = 3.45
DPI = 600

NAVY = "#12263F"
CYAN = "#1282A2"
RED = "#B23A48"
GREY = "#9AA5B1"
LIGHT = "#E4E9EE"
PINK = "#F7E3E6"
ICE = "#DCEFF5"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 7,
    "text.color": NAVY,
})


def box(ax, x, y, w, h, text, fc="white", ec=NAVY, fs=6.6, lw=0.9):
    ax.add_patch(FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0,rounding_size=0.035",
        fc=fc, ec=ec, lw=lw, zorder=3))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs,
            color=NAVY, zorder=4, linespacing=1.35)


def diamond(ax, x, y, w, h, text, fc=LIGHT, ec=NAVY, fs=6.6):
    ax.add_patch(Polygon([[x, y + h / 2], [x + w / 2, y],
                          [x, y - h / 2], [x - w / 2, y]],
                         closed=True, fc=fc, ec=ec, lw=0.9, zorder=3))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs,
            color=NAVY, zorder=4, linespacing=1.3)


def arrow(ax, p, q, text=None, rad=0.0, fs=6.0, off=(0, 0), color=NAVY):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle="-|>", mutation_scale=7, lw=0.9, color=color,
        connectionstyle="arc3,rad=%s" % rad, zorder=2,
        shrinkA=1.5, shrinkB=1.5))
    if text:
        mx = (p[0] + q[0]) / 2 + off[0]
        my = (p[1] + q[1]) / 2 + off[1]
        ax.text(mx, my, text, ha="center", va="center", fontsize=fs,
                color=color, zorder=5, linespacing=1.25,
                bbox=dict(fc="white", ec="none", pad=0.8))


# ------------------------------------------------ receiver state machine
def rx_state():
    fig, ax = plt.subplots(figsize=(COL, 1.92))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.6, 6.0)
    ax.axis("off")

    box(ax, 2.55, 2.5, 3.5, 1.5, "TRACKING\n" r"listening on $c_{rx}$")
    box(ax, 7.6, 2.5, 3.4, 1.5, "RENDEZVOUS\n" r"listening on $c_0$",
        fc=PINK, ec=RED)

    arrow(ax, (1.7, 3.25), (3.4, 3.25), rad=-1.5)
    ax.text(2.55, 5.42, "valid packet:\n" r"$c_{rx} \leftarrow$ NEXT",
            ha="center", va="center", fontsize=6.0, color=NAVY,
            linespacing=1.25)

    arrow(ax, (8.5, 1.75), (6.8, 1.75), rad=-1.5, color=RED)
    ax.text(7.6, -0.30, "silence: keep waiting", ha="center", va="center",
            fontsize=6.0, color=RED)

    arrow(ax, (4.3, 2.95), (5.9, 2.95), rad=-0.30, color=RED,
          text=r"no packet for $T_r$", off=(0, 0.72), fs=6.0)
    arrow(ax, (5.9, 2.05), (4.3, 2.05), rad=-0.30, color=CYAN,
          text=r"packet heard on $c_0$", off=(0, -0.72), fs=6.0)

    fig.tight_layout(pad=0.15)
    p = os.path.join(OUT, "fig_rx_state.png")
    fig.savefig(p, dpi=DPI, facecolor="white")
    plt.close(fig)
    print("wrote", p)


# --------------------------------------------- sense-before-hop flowchart
def sense_flow():
    fig, ax = plt.subplots(figsize=(COL, 3.25))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 15.8)
    ax.axis("off")

    cx = 4.3           # main column
    rail = 8.8         # "try the next offset" rail, on the right
    lrail = 0.8        # "accepted" rail, on the left

    box(ax, cx, 14.3, 6.0, 1.15, r"$offset \leftarrow 1$", fc=LIGHT)
    box(ax, cx, 12.4, 6.6, 1.25,
        r"$c \leftarrow (current + offset)\,\mathrm{mod}\,N$")
    diamond(ax, cx, 10.2, 6.2, 2.1, "cooldown[$c$] > 0 ?")
    box(ax, cx, 7.9, 6.6, 1.5,
        "tune to $f_c$, settle 5 ms\n" r"read $P_{RSSI}(c)$")
    diamond(ax, cx, 5.55, 6.2, 2.1, r"$P_{RSSI}(c) < \Lambda$ ?")
    box(ax, cx, 3.35, 6.6, 1.3, r"cooldown[$c$] $\leftarrow$ 3",
        fc=PINK, ec=RED)
    box(ax, cx, 1.45, 6.0, 1.35, "accept $c$; announce\nin NEXT field",
        fc=ICE, ec=CYAN)

    # straight-through path
    arrow(ax, (cx, 13.72), (cx, 13.03))
    arrow(ax, (cx, 11.78), (cx, 11.25))
    arrow(ax, (cx, 9.15), (cx, 8.65), text="no", off=(0.42, 0.06))
    arrow(ax, (cx, 7.15), (cx, 6.60))
    arrow(ax, (cx, 4.50), (cx, 4.00), text="no", off=(0.42, 0.06),
          color=RED)

    # accepted: left rail down into the accept box
    arrow(ax, (cx - 3.1, 5.55), (lrail, 5.55), color=CYAN)
    arrow(ax, (lrail, 5.55), (lrail, 1.45), color=CYAN)
    arrow(ax, (lrail, 1.45), (cx - 3.0, 1.45), color=CYAN)
    ax.text(1.05, 5.85, "yes", ha="left", va="bottom", fontsize=6.0,
            color=CYAN)

    # already cooling down: straight to the next offset
    arrow(ax, (cx + 3.1, 10.2), (rail, 10.2), text="yes",
          off=(-0.28, 0.32))
    arrow(ax, (rail, 10.2), (rail, 13.3))
    arrow(ax, (rail, 13.3), (cx + 3.3, 13.3))

    # just blacklisted: also to the next offset
    arrow(ax, (cx + 3.3, 3.35), (rail, 3.35), color=RED)
    arrow(ax, (rail, 3.35), (rail, 9.60), color=RED)

    ax.text(8.2, 13.52, r"$offset \leftarrow offset + 1$",
            ha="center", va="center", fontsize=5.6, color=NAVY,
            bbox=dict(fc="white", ec="none", pad=0.6))
    ax.text(cx, 0.08,
            r"after $N$ refusals: fall back to "
            r"$(current+1)\,\mathrm{mod}\,N$",
            ha="center", va="bottom", fontsize=6.0, color=GREY,
            style="italic")

    fig.tight_layout(pad=0.15)
    p = os.path.join(OUT, "fig_sense_flow.png")
    fig.savefig(p, dpi=DPI, facecolor="white")
    plt.close(fig)
    print("wrote", p)


if __name__ == "__main__":
    rx_state()
    sense_flow()
