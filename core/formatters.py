"""
RAG Financial Analysis — Telegram HTML Formatters
Rich visual message formatting with sparklines, ASCII charts, confidence bars.
"""
from datetime import datetime
from typing import Optional

from core.analyzer import AnalysisResult

# ─── Sparkline Characters ───────────────────────────────────────────────────
_SPARK_CHARS = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


def _html(s: str) -> str:
    """Escape HTML special chars for Telegram HTML parse mode."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_sparkline(values: list) -> str:
    """Turn a list of numbers into a Unicode sparkline string.

    Args:
        values: Numeric values to visualize.

    Returns:
        A string of Unicode block characters representing the trend.
    """
    if not values:
        return ""
    # Filter out None/NaN
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return ""
    if max(clean) == min(clean):
        return "▄" * len(clean)
    lo, hi = min(clean), max(clean)
    return "".join(
        _SPARK_CHARS[min(7, int((v - lo) / (hi - lo) * 7))]
        for v in clean
    )


def build_confidence_bar(pct: int) -> str:
    """Build a 10-character Unicode confidence bar.

    Args:
        pct: Confidence percentage (0-100).

    Returns:
        A string like '████████░░' representing the confidence level.
    """
    pct = max(0, min(100, int(pct)))
    filled = round(pct / 10)
    return "█" * filled + "░" * (10 - filled)


def build_ascii_bar_chart(analysis: AnalysisResult, forecast_value: float) -> str:
    """ASCII bar chart from real analysis data with dynamic sizing.

    Builds a horizontal bar chart showing monthly revenue values plus
    the forecasted value. Automatically adapts to any number of months.

    Args:
        analysis: The AnalysisResult with monthly_revenue data.
        forecast_value: The predicted forecast value in raw dollars.

    Returns:
        HTML-wrapped ASCII bar chart string for Telegram.
    """
    monthly = analysis.monthly_revenue
    if not monthly:
        return "<code>  No revenue data available</code>"

    # Build labels and values
    months = list(monthly.keys())
    revenues = list(monthly.values())

    # Shorten month labels (last 5 chars or abbreviated)
    labels = []
    for m in months:
        if len(m) >= 7:
            # Format like "Oct'24" from "2024-10"
            try:
                dt = datetime.strptime(m, "%Y-%m")
                labels.append(dt.strftime("%b'%y"))
            except ValueError:
                labels.append(m[-5:])
        else:
            labels.append(m)

    labels.append("FCST")
    values = revenues + [forecast_value]

    max_val = max(values) if values else 1
    bar_max = 14  # max bar width in chars

    lines = ["<code>"]
    lines.append("  Revenue Trend + Forecast")
    lines.append("  " + "─" * 38)

    for lbl, val in zip(labels, values):
        bar_len = int((val / max_val) * bar_max) if max_val > 0 else 0
        is_forecast = lbl == "FCST"
        bar = ("▓" if is_forecast else "█") * bar_len
        # Format value — auto-scale to M or K
        if abs(val) >= 1_000_000:
            val_str = f"${val / 1_000_000:.2f}M"
        elif abs(val) >= 1_000:
            val_str = f"${val / 1_000:.0f}K"
        else:
            val_str = f"${val:,.0f}"

        line = f"  {lbl:>7} │{bar:<{bar_max}} {val_str}"
        if is_forecast:
            line += " ◄ FORECAST"
        lines.append(line)

    lines.append("  " + "─" * 38)
    lines.append("         █=Historical  ▓=Forecast")
    lines.append("</code>")
    return "\n".join(lines)


def format_forecast_message(
    analysis: AnalysisResult,
    forecast: dict,
    latency: float
) -> str:
    """Build the full HTML-formatted Telegram forecast message.

    Combines the AI forecast with analysis data into a rich
    Telegram-compatible HTML message with sparklines, ASCII charts,
    confidence bars, and key metrics.

    Args:
        analysis: The AnalysisResult from data analysis.
        forecast: Dict with forecast_value, confidence_percent, range_low,
                  range_high, timeframe, key_drivers, reasoning,
                  market_signal, risk.
        latency: Pipeline execution time in seconds.

    Returns:
        HTML-formatted message string for Telegram parse_mode=HTML.
    """
    v = forecast.get("forecast_value", analysis.forecast_value)
    low = forecast.get("range_low", analysis.forecast_low)
    high = forecast.get("range_high", analysis.forecast_high)
    pct = forecast.get("confidence_percent", analysis.confidence_percent)
    tf = forecast.get("timeframe", "Next Quarter")
    kd = forecast.get("key_drivers", ["—", "—", "—"])
    rsn = forecast.get("reasoning", "")
    ms = forecast.get("market_signal", "")
    risk = forecast.get("risk", "")

    bar = build_confidence_bar(pct)

    # Sparkline from monthly revenue + forecast
    rev_vals = list(analysis.monthly_revenue.values()) + [v]
    sparkline = build_sparkline(rev_vals)

    # Determine YoY growth display
    yoy = analysis.yoy_growth
    yoy_sign = "+" if yoy >= 0 else ""

    # ASCII mini bar chart
    ascii_chart = build_ascii_bar_chart(analysis, v)

    # Key drivers with numbered emojis
    nums = ["1️⃣", "2️⃣", "3️⃣"]
    drivers_text = "\n".join(
        f"{nums[i]} {_html(d)}" for i, d in enumerate(kd[:3])
    )

    # Data source line
    source_line = (
        f"Data: {analysis.row_count} rows | {_html(analysis.date_range)}"
        if analysis.row_count > 0
        else "Data: Demo dataset"
    )

    msg = (
        f"🎯 <b>Financial Forecast — {_html(tf)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Predicted Revenue: <b>${v / 1_000_000:.2f}M</b>\n"
        f"📊 Confidence: <b>{pct}%</b> {bar}\n"
        f"📉 Range: ${low / 1_000_000:.2f}M — ${high / 1_000_000:.2f}M\n"
        f"📈 Trend: <code>{sparkline}</code> ({yoy_sign}{yoy:.1f}% YoY)\n\n"
        f"{ascii_chart}\n\n"
        f"📈 <b>Key Drivers:</b>\n"
        f"{drivers_text}\n\n"
        f"💡 <b>Analysis:</b>\n"
        f"<i>{_html(rsn)}</i>\n\n"
        f"📰 <b>Market Signal:</b>\n"
        f"<i>{_html(ms)}</i>\n\n"
        f"⚠️ <b>Risk Factor:</b> {_html(risk)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Powered by RAG Pipeline | Pinecone + Gemini 3.1 Flash-Lite</i>\n"
        f"<i>Sources: NewsData.io, Alpha Vantage, Pinecone VectorDB</i>\n"
        f"<i>Generated in {latency:.1f}s ⚡</i>"
    )
    return msg


def format_upload_confirmation(analysis: AnalysisResult) -> str:
    """Message confirming CSV/Excel upload with detected columns and stats.

    Generates a rich Telegram HTML message showing what the system
    detected from the uploaded file: column mapping, row count,
    date range, and key financial stats.

    Args:
        analysis: The AnalysisResult from analyzing the uploaded file.

    Returns:
        HTML-formatted confirmation message string.
    """
    col = analysis.column_info
    date_col = col.get("date_col", "—")
    value_col = col.get("value_col", "—")
    region_col = col.get("region_col", "—")
    product_col = col.get("product_col", "—")

    # Sparkline from monthly revenue
    sparkline = build_sparkline(list(analysis.monthly_revenue.values()))

    # Trend indicator
    trend_emoji = {
        "increasing": "📈",
        "decreasing": "📉",
        "stable": "➡️",
    }.get(analysis.trend_direction, "📊")

    # Extra stats
    extra = analysis.extra_stats
    mean_val = extra.get("mean", 0)
    median_val = extra.get("median", 0)
    std_val = extra.get("std", 0)

    # Categories
    cats = ", ".join(analysis.top_categories[:5]) if analysis.top_categories else "—"

    msg = (
        f"✅ <b>Dataset Uploaded Successfully!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📁 <b>Data Overview:</b>\n"
        f"  • Rows: <b>{analysis.row_count:,}</b>\n"
        f"  • Date Range: <b>{_html(analysis.date_range)}</b>\n"
        f"  • Categories: {_html(cats)}\n\n"
        f"🔍 <b>Detected Columns:</b>\n"
        f"  📅 Date: <code>{_html(date_col)}</code>\n"
        f"  💰 Revenue: <code>{_html(value_col)}</code>\n"
        f"  🌍 Region: <code>{_html(region_col)}</code>\n"
        f"  📦 Product: <code>{_html(product_col)}</code>\n\n"
        f"{trend_emoji} <b>Key Statistics:</b>\n"
        f"  • 90-Day Avg: <b>${analysis.rolling_avg_90 / 1_000_000:.2f}M</b>\n"
        f"  • YoY Growth: <b>{'+' if analysis.yoy_growth >= 0 else ''}{analysis.yoy_growth:.1f}%</b>\n"
        f"  • Trend: <b>{analysis.trend_direction.title()}</b>\n"
        f"  • Mean: ${mean_val / 1_000_000:.2f}M\n"
        f"  • Median: ${median_val / 1_000_000:.2f}M\n"
        f"  • Std Dev: ${std_val / 1_000_000:.2f}M\n\n"
        f"📈 <b>Revenue Trend:</b> <code>{sparkline}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Ready for forecast queries! Ask me anything about this data.</i>"
    )
    return msg
