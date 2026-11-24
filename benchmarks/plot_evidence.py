"""Render evidence charts from committed CSV files.

Every chart reads a CSV that is checked into the repo; this script never
invents numbers. Run it after regenerating the underlying benchmarks.
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

EVIDENCE = Path("data/evidence")
FIGURES = Path("docs/evidence/figures")
FIGURES.mkdir(parents=True, exist_ok=True)

ACCENT = "#2563eb"
ACCENT_2 = "#f97316"
GREEN = "#16a34a"
RED = "#dc2626"
GRID = "#e5e7eb"
TEXT = "#111827"


def style(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#9ca3af")
    ax.spines["bottom"].set_color("#9ca3af")
    ax.tick_params(colors=TEXT)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def read_csv(name):
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def plot_overhead():
    rows = {row["path"]: row for row in read_csv("gateway_overhead_benchmark.csv")}
    overhead = rows["overhead_delta"]
    direct = rows["direct_provider_call"]
    concurrent = rows["gateway_http_concurrent"]

    percentiles = ["p50", "p95", "p99"]
    values = [float(overhead[f"{p}_ms"]) for p in percentiles]

    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=160)
    bars = ax.bar(
        [p.upper() for p in percentiles],
        values,
        width=0.55,
        color=[ACCENT, "#3b82f6", "#93c5fd"],
        zorder=3,
    )
    for bar, value in zip(bars, values):
        ax.annotate(
            f"{value:.1f} ms",
            (bar.get_x() + bar.get_width() / 2, value),
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
            color=TEXT,
        )

    ax.set_ylabel("Gateway processing time (ms)", color=TEXT)
    ax.set_title(
        "Gateway overhead per request (in-process, 500 paired samples)",
        fontsize=13,
        fontweight="bold",
        color=TEXT,
        pad=12,
    )
    ax.set_ylim(0, max(values) * 1.25)
    style(ax)

    ax.text(
        0.99,
        0.97,
        f"Direct provider coroutine p50: {float(direct['p50_ms']):.3f} ms\n"
        f"Concurrent throughput (8): "
        f"{float(concurrent['requests_per_second']):.0f} req/s",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        color="#4b5563",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f9fafb", edgecolor=GRID),
    )

    fig.tight_layout()
    out = FIGURES / "gateway_overhead.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out)


def plot_semantic_tradeoff():
    rows = read_csv("semantic_threshold_sweep.csv")
    thresholds = [float(r["threshold"]) for r in rows]
    hit_rate = [float(r["hit_rate"]) * 100 for r in rows]
    hard_fpr = [float(r["hard_negative_false_positive_rate"]) * 100 for r in rows]
    unrelated_fpr = [
        float(r.get("unrelated_false_positives", 0))
        / max(int(r["unrelated_queries"]), 1)
        * 100
        for r in rows
    ]

    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=160)
    ax.plot(
        thresholds,
        hit_rate,
        marker="o",
        markersize=7,
        linewidth=2.4,
        color=ACCENT,
        label="Paraphrase hit rate",
        zorder=3,
    )
    ax.plot(
        thresholds,
        hard_fpr,
        marker="s",
        markersize=6,
        linewidth=2.0,
        color=RED,
        label="Hard-negative false positives",
        zorder=3,
    )
    ax.plot(
        thresholds,
        unrelated_fpr,
        marker="^",
        markersize=6,
        linewidth=1.6,
        linestyle="--",
        color=ACCENT_2,
        label="Unrelated false positives",
        zorder=3,
    )

    for x, y in zip(thresholds, hit_rate):
        ax.annotate(
            f"{y:.1f}%",
            (x, y),
            textcoords="offset points",
            xytext=(0, 9),
            ha="center",
            fontsize=9,
            color=ACCENT,
            fontweight="bold",
        )
    for x, y in zip(thresholds, hard_fpr):
        if y > 0:
            ax.annotate(
                f"{y:.1f}%",
                (x, y),
                textcoords="offset points",
                xytext=(0, -14),
                ha="center",
                fontsize=9,
                color=RED,
                fontweight="bold",
            )

    ax.set_xlabel("Semantic similarity threshold", color=TEXT)
    ax.set_ylabel("Rate (%)", color=TEXT)
    ax.set_xticks(thresholds)
    ax.set_xticklabels([f"{t:.2f}" for t in thresholds])
    ax.set_ylim(-2, max(hit_rate) * 1.3 + 4)
    ax.set_title(
        "Semantic cache threshold trade-off (24 paraphrases, 24 negatives)",
        fontsize=13,
        fontweight="bold",
        color=TEXT,
        pad=12,
    )
    style(ax)
    ax.legend(frameon=False, loc="upper right", fontsize=9)

    fig.tight_layout()
    out = FIGURES / "semantic_threshold_tradeoff.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out)


def plot_fallback_timeline():
    rows = [
        row
        for row in read_csv("fallback_timeline_events.csv")
        if row["scenario"] == "standard_recovery"
    ]
    state_value = {"CLOSED": 0, "OPEN": 1, "HALF_OPEN": 2}
    times = [float(r["relative_time_ms"]) for r in rows]
    states = [state_value[r["circuit_state"]] for r in rows]

    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=160)
    ax.step(times, states, where="post", color=ACCENT, linewidth=2.2, zorder=2)
    ax.fill_between(times, states, step="post", color=ACCENT, alpha=0.08)

    event_styles = {
        "request_failed": ("x", RED, "Provider failure"),
        "request_rejected": ("v", ACCENT_2, "Rejected while open"),
        "recovery_success": ("*", GREEN, "Recovery probe success"),
    }
    seen = set()
    for row in rows:
        event = row["event"]
        if event not in event_styles:
            continue
        marker, color, label = event_styles[event]
        ax.scatter(
            float(row["relative_time_ms"]),
            state_value[row["circuit_state"]],
            marker=marker,
            color=color,
            s=110 if event == "recovery_success" else 55,
            zorder=4,
            label=label if label not in seen else None,
        )
        seen.add(label)

    failures = [
        float(r["relative_time_ms"]) for r in rows if r["event"] == "request_failed"
    ]
    recovery = [
        float(r["relative_time_ms"]) for r in rows if r["event"] == "recovery_success"
    ]
    if failures:
        ax.axvline(
            failures[-1],
            color=RED,
            linestyle=":",
            linewidth=1.4,
            alpha=0.8,
        )
        ax.annotate(
            f"circuit opens\n{failures[-1]:.0f} ms",
            (failures[-1], 1.0),
            textcoords="offset points",
            xytext=(10, 18),
            fontsize=9,
            color=RED,
        )
    if recovery:
        ax.axvline(
            recovery[0],
            color=GREEN,
            linestyle=":",
            linewidth=1.4,
            alpha=0.8,
        )
        ax.annotate(
            f"recovered\n{recovery[0]:.0f} ms",
            (recovery[0], 1.0),
            textcoords="offset points",
            xytext=(-95, -42),
            fontsize=9,
            color=GREEN,
        )

    ax.set_yticks([0, 1, 2])
    ax.set_yticklabels(["CLOSED", "OPEN", "HALF_OPEN"])
    ax.set_xlabel("Time since scenario start (ms)", color=TEXT)
    ax.set_ylabel("Circuit state", color=TEXT)
    ax.set_title(
        "Circuit breaker failover and recovery (3 failures, 2 s timeout)",
        fontsize=13,
        fontweight="bold",
        color=TEXT,
        pad=12,
    )
    ax.set_xlim(left=0)
    ax.set_ylim(-0.3, 1.5)
    style(ax)
    ax.legend(
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=3,
        fontsize=9,
    )

    fig.tight_layout()
    out = FIGURES / "fallback_recovery_timeline.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    plot_overhead()
    plot_semantic_tradeoff()
    plot_fallback_timeline()
