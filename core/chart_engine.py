"""
RAG Financial Analysis — Chart Engine

Dark-themed Matplotlib revenue bar charts with confidence intervals.
Handles variable-length data from AnalysisResult.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def generate_forecast_chart(
    analysis,  # AnalysisResult — import avoided for circular safety
    forecast: dict,
) -> Optional[bytes]:
    """Generate dark-themed revenue bar chart with forecast + confidence interval.

    Works with variable-length monthly data from AnalysisResult.
    Returns PNG bytes or None on failure.

    Args:
        analysis: AnalysisResult with monthly_revenue data.
        forecast: Dict with forecast_value, range_low, range_high,
                  confidence_percent, timeframe.

    Returns:
        PNG image as bytes, or None if generation fails.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        monthly = analysis.monthly_revenue
        if not monthly:
            logger.warning("No monthly revenue data for chart")
            return None

        # ── Prepare data ─────────────────────────────────────────────────
        months = list(monthly.keys())
        revenues = [v / 1_000_000 for v in monthly.values()]

        # Build readable labels
        labels = []
        for m in months:
            try:
                if len(m) >= 7 and "-" in m:
                    dt = datetime.strptime(m[:7], "%Y-%m")
                    labels.append(dt.strftime("%b'%y"))
                else:
                    labels.append(m[-6:])
            except ValueError:
                labels.append(m[-6:])

        fv = forecast.get("forecast_value", analysis.forecast_value) / 1_000_000
        low = forecast.get("range_low", analysis.forecast_low) / 1_000_000
        high = forecast.get("range_high", analysis.forecast_high) / 1_000_000
        tf = forecast.get("timeframe", "Forecast")
        pct = forecast.get("confidence_percent", analysis.confidence_percent)

        all_labels = labels + [tf]
        all_values = revenues + [fv]
        colors = ["#4A90D9"] * len(revenues) + ["#2ECC71"]
        err_low = [0] * len(revenues) + [max(0, fv - low)]
        err_high = [0] * len(revenues) + [high - fv]

        # ── Dark theme figure ────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(10, 5.5))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#161b22")

        bars = ax.bar(
            all_labels, all_values, color=colors, width=0.6,
            edgecolor="#30363d", linewidth=0.8,
        )

        # Error bar on forecast only
        ax.errorbar(
            [tf], [fv],
            yerr=[[max(0, fv - low)], [high - fv]],
            fmt="none", color="#F0E68C", capsize=8, capthick=2, linewidth=2,
        )

        # Value labels on bars
        for bar, val in zip(bars, all_values):
            ax.text(
                bar.get_x() + bar.get_width() / 2, val + 0.03,
                f"${val:.2f}M", ha="center", va="bottom",
                color="#e6edf3", fontsize=8, fontweight="bold",
            )

        # Confidence band shading
        ax.axhspan(
            low, high, alpha=0.08, color="#2ECC71",
            label=f"Confidence range ({pct}%)",
        )

        # Trend line
        trend_x = list(range(len(all_values)))
        ax.plot(
            trend_x, all_values, color="#FFD700", linewidth=1.5,
            linestyle="--", alpha=0.7, marker="o", markersize=4,
        )

        # ── Styling ──────────────────────────────────────────────────────
        ax.set_title(
            f"Revenue Forecast — {tf}  │ Confidence: {pct}%",
            color="#e6edf3", fontsize=13, fontweight="bold", pad=15,
        )
        ax.set_ylabel("Revenue ($M)", color="#8b949e", fontsize=10)
        ax.tick_params(colors="#8b949e", labelsize=8)

        # Rotate labels if too many months
        if len(all_labels) > 8:
            plt.xticks(rotation=45, ha="right")

        for spine in ax.spines.values():
            spine.set_edgecolor("#30363d")
        ax.yaxis.grid(True, color="#21262d", linewidth=0.8, linestyle="--")
        ax.set_axisbelow(True)

        # Legend
        hist_patch = mpatches.Patch(color="#4A90D9", label="Historical Revenue")
        fcst_patch = mpatches.Patch(color="#2ECC71", label=f"Forecast ({tf})")
        conf_patch = mpatches.Patch(
            color="#2ECC71", alpha=0.2, label="Confidence Range",
        )
        ax.legend(
            handles=[hist_patch, fcst_patch, conf_patch],
            facecolor="#161b22", edgecolor="#30363d",
            labelcolor="#8b949e", fontsize=8, loc="upper left",
        )

        # Watermark
        fig.text(
            0.98, 0.02, "RAG Financial Analysis System",
            ha="right", va="bottom", color="#30363d", fontsize=7,
        )

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(
            buf, format="png", dpi=130, bbox_inches="tight",
            facecolor=fig.get_facecolor(),
        )
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    except Exception as e:
        logger.error("Chart generation failed: %s", e)
        return None
