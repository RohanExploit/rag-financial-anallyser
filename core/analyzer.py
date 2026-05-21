"""
Financial data analysis engine.

Provides :class:`DataAnalyzer` for automated column detection,
aggregation, growth-rate computation, and linear-regression
forecasting from arbitrary pandas DataFrames.  Also exposes a
convenience function :func:`analyze_from_demo` that produces an
:class:`AnalysisResult` from built-in demo data.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# Structured analysis output
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class AnalysisResult:
    """Structured output from :meth:`DataAnalyzer.analyze`."""

    summary_text: str
    """Human-readable narrative suitable for inclusion in an LLM prompt."""

    monthly_revenue: dict
    """Mapping of ``YYYY-MM`` period keys to aggregated numeric values."""

    rolling_avg_30: float
    """Approximate 30-day (1-month) rolling average of the value column."""

    rolling_avg_90: float
    """Approximate 90-day (3-month) rolling average of the value column."""

    yoy_growth: float
    """Year-over-year growth expressed as a percentage."""

    qoq_growth: float
    """Quarter-over-quarter growth expressed as a percentage."""

    forecast_value: float
    """Next-period point forecast from linear regression."""

    forecast_low: float
    """Lower bound of the confidence interval."""

    forecast_high: float
    """Upper bound of the confidence interval."""

    confidence_percent: int
    """Confidence level for the forecast (typically 75–92)."""

    trend_direction: str
    """One of ``'increasing'``, ``'decreasing'``, or ``'stable'``."""

    column_info: dict
    """Metadata about detected columns (``date_col``, ``value_col``, etc.)."""

    row_count: int
    """Number of rows in the original DataFrame."""

    date_range: str
    """Human-readable date range, e.g. ``'Oct 2024 - Jan 2025'``."""

    top_categories: list = field(default_factory=list)
    """Detected categorical value groups (if any)."""

    extra_stats: dict = field(default_factory=dict)
    """Additional descriptive statistics (mean, median, std, min, max, …)."""


# ═══════════════════════════════════════════════════════════════════════════
# Column-name heuristic patterns
# ═══════════════════════════════════════════════════════════════════════════

_DATE_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)\b(date|time|period|day|month|year|timestamp|dt)\b"),
]

_VALUE_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"(?i)\b(revenue|sales|amount|value|price|total|income|profit|"
        r"cost|expense|earning|turnover|gross|net)\b"
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# DataAnalyzer
# ═══════════════════════════════════════════════════════════════════════════


class DataAnalyzer:
    """Analyse financial data from an arbitrary :class:`~pandas.DataFrame`.

    On construction the analyser copies the input frame and runs
    column-type detection heuristics.  Call :meth:`analyze` to produce
    a fully populated :class:`AnalysisResult`.
    """

    # Columns with fewer than this many unique values are treated as
    # categorical when their dtype is string / object.
    _CATEGORY_CARDINALITY_THRESHOLD = 30

    def __init__(self, df: pd.DataFrame) -> None:
        if df.empty:
            raise ValueError("Cannot analyse an empty DataFrame.")
        self.df: pd.DataFrame = df.copy()
        self.date_col: Optional[str] = None
        self.value_col: Optional[str] = None
        self.category_cols: list[str] = []
        self._auto_detect_columns()

    # ── Column auto-detection ─────────────────────────────────────────────

    def _auto_detect_columns(self) -> None:
        """Auto-detect date, numeric (revenue/value), and categorical columns.

        Strategy order:
        1. Column-name heuristics (regex patterns against column names).
        2. Dtype detection (datetime64, numeric, object/string).
        3. Parsing attempts (``pd.to_datetime`` probing for object cols).
        """
        # --- Date column -------------------------------------------------
        for col in self.df.columns:
            if pd.api.types.is_datetime64_any_dtype(self.df[col]):
                self.date_col = col
                break

        if self.date_col is None:
            for col in self.df.columns:
                if any(p.search(col) for p in _DATE_PATTERNS):
                    try:
                        self.df[col] = pd.to_datetime(
                            self.df[col], infer_datetime_format=True
                        )
                        self.date_col = col
                        break
                    except (ValueError, TypeError):
                        continue

        # Last resort: try parsing every object column
        if self.date_col is None:
            for col in self.df.select_dtypes(include=["object"]).columns:
                try:
                    parsed = pd.to_datetime(self.df[col], infer_datetime_format=True)
                    if parsed.notna().sum() > len(self.df) * 0.5:
                        self.df[col] = parsed
                        self.date_col = col
                        break
                except (ValueError, TypeError):
                    continue

        # --- Value (numeric) column ---------------------------------------
        numeric_cols = list(self.df.select_dtypes(include=[np.number]).columns)

        # Prefer a column whose name matches a value pattern
        for col in numeric_cols:
            if any(p.search(col) for p in _VALUE_PATTERNS):
                self.value_col = col
                break

        # Fall back to the numeric column with the largest mean
        if self.value_col is None and numeric_cols:
            self.value_col = max(
                numeric_cols, key=lambda c: self.df[c].mean(skipna=True)
            )

        # --- Category columns ---------------------------------------------
        for col in self.df.select_dtypes(include=["object", "category"]).columns:
            if col == self.date_col:
                continue
            nunique = self.df[col].nunique()
            if 1 < nunique <= self._CATEGORY_CARDINALITY_THRESHOLD:
                self.category_cols.append(col)

        logger.info(
            "Auto-detected columns — date=%s  value=%s  categories=%s",
            self.date_col,
            self.value_col,
            self.category_cols,
        )

    # ── Main analysis entry-point ─────────────────────────────────────────

    def analyze(self, query: str = "") -> AnalysisResult:
        """Run the full analysis pipeline.

        Steps:
        1. Parse & clean data (drop NaN in value column).
        2. Aggregate by calendar month when a date column is present.
        3. Compute rolling averages (30-day / 90-day approximations).
        4. Compute YoY and QoQ growth rates.
        5. Linear-regression forecast via ``numpy.polyfit``.
        6. Build a rich *summary_text* for LLM prompt injection.

        Args:
            query: Optional user query string — appended to the summary
                for additional LLM context.

        Returns:
            A fully populated :class:`AnalysisResult`.
        """
        df = self.df.copy()

        # ── 1. Clean ─────────────────────────────────────────────────────
        if self.value_col:
            df = df.dropna(subset=[self.value_col])

        row_count = len(df)

        # ── 2. Monthly aggregation ───────────────────────────────────────
        monthly_revenue: dict[str, float] = {}
        monthly_values: list[float] = []

        if self.date_col and self.value_col:
            df = df.sort_values(self.date_col)
            monthly = (
                df
                .set_index(self.date_col)
                .resample("ME")[self.value_col]
                .sum()
            )
            monthly = monthly[monthly > 0]
            for period, val in monthly.items():
                key = period.strftime("%Y-%m")
                monthly_revenue[key] = float(val)
                monthly_values.append(float(val))
        elif self.value_col:
            # No date column — treat each row value as-is
            monthly_values = df[self.value_col].dropna().tolist()
            for idx, val in enumerate(monthly_values):
                monthly_revenue[f"period-{idx + 1}"] = float(val)

        # ── 3. Rolling averages ──────────────────────────────────────────
        rolling_avg_30 = float(np.mean(monthly_values[-1:])) if monthly_values else 0.0
        rolling_avg_90 = float(np.mean(monthly_values[-3:])) if monthly_values else 0.0

        # ── 4. Growth rates ──────────────────────────────────────────────
        yoy_growth = self._compute_yoy(monthly_values)
        qoq_growth = self._compute_qoq(monthly_values)

        # ── 5. Linear-regression forecast ────────────────────────────────
        forecast_value, forecast_low, forecast_high, confidence = (
            self._linear_forecast(monthly_values)
        )

        # ── Trend direction ──────────────────────────────────────────────
        trend_direction = self._detect_trend(monthly_values)

        # ── Date range ───────────────────────────────────────────────────
        date_range = self._build_date_range(df)

        # ── Top categories ───────────────────────────────────────────────
        top_categories = self._extract_categories(df)

        # ── Extra stats ──────────────────────────────────────────────────
        extra_stats = self._compute_extra_stats(df)

        # ── Column info ──────────────────────────────────────────────────
        column_info = {
            "date_col": self.date_col,
            "value_col": self.value_col,
            "category_cols": self.category_cols,
            "total_columns": len(df.columns),
        }

        # ── 6. Summary text for LLM prompt ───────────────────────────────
        summary_text = self._build_summary(
            monthly_revenue=monthly_revenue,
            rolling_avg_30=rolling_avg_30,
            rolling_avg_90=rolling_avg_90,
            yoy_growth=yoy_growth,
            qoq_growth=qoq_growth,
            forecast_value=forecast_value,
            forecast_low=forecast_low,
            forecast_high=forecast_high,
            confidence=confidence,
            trend_direction=trend_direction,
            date_range=date_range,
            row_count=row_count,
            top_categories=top_categories,
            extra_stats=extra_stats,
            query=query,
        )

        return AnalysisResult(
            summary_text=summary_text,
            monthly_revenue=monthly_revenue,
            rolling_avg_30=rolling_avg_30,
            rolling_avg_90=rolling_avg_90,
            yoy_growth=yoy_growth,
            qoq_growth=qoq_growth,
            forecast_value=forecast_value,
            forecast_low=forecast_low,
            forecast_high=forecast_high,
            confidence_percent=confidence,
            trend_direction=trend_direction,
            column_info=column_info,
            row_count=row_count,
            date_range=date_range,
            top_categories=top_categories,
            extra_stats=extra_stats,
        )

    # ── Private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _compute_yoy(values: list[float]) -> float:
        """Year-over-year growth in percent.

        Compares the last 12 months' average against the preceding
        12 months.  Falls back to overall first-vs-last comparison
        when fewer than 24 data points are available.
        """
        if len(values) < 2:
            return 0.0
        if len(values) >= 24:
            recent = np.mean(values[-12:])
            prior = np.mean(values[-24:-12])
        else:
            prior = float(values[0])
            recent = float(values[-1])
        if prior == 0:
            return 0.0
        return round(((recent - prior) / abs(prior)) * 100, 1)

    @staticmethod
    def _compute_qoq(values: list[float]) -> float:
        """Quarter-over-quarter growth in percent.

        Compares the last 3 months' average against the preceding 3.
        Falls back to comparing the last two data points when fewer
        than 6 points exist.
        """
        if len(values) < 2:
            return 0.0
        if len(values) >= 6:
            recent = np.mean(values[-3:])
            prior = np.mean(values[-6:-3])
        else:
            prior = float(values[0])
            recent = float(values[-1])
        if prior == 0:
            return 0.0
        return round(((recent - prior) / abs(prior)) * 100, 1)

    @staticmethod
    def _linear_forecast(
        values: list[float],
    ) -> tuple[float, float, float, int]:
        """Linear-regression point forecast with confidence interval.

        Uses ``np.polyfit(x, y, 1)`` on the monthly values and
        extrapolates one period ahead.

        Returns:
            ``(forecast_value, forecast_low, forecast_high, confidence_percent)``
        """
        if not values:
            return 0.0, 0.0, 0.0, 75

        if len(values) == 1:
            v = values[0]
            return v, v * 0.9, v * 1.1, 75

        x = np.arange(len(values), dtype=float)
        y = np.array(values, dtype=float)

        coeffs = np.polyfit(x, y, 1)  # [slope, intercept]
        slope, intercept = coeffs

        forecast_value = float(slope * len(values) + intercept)

        # Ensure forecast is non-negative for financial data
        forecast_value = max(forecast_value, 0.0)

        # Confidence interval: forecast ± (std_dev * 0.5)
        std_dev = float(np.std(y, ddof=1)) if len(y) > 1 else 0.0
        half_band = std_dev * 0.5
        forecast_low = max(forecast_value - half_band, 0.0)
        forecast_high = forecast_value + half_band

        # Confidence heuristic: more data ⇒ higher confidence, capped 75–92
        r_squared = 1.0
        if len(y) > 1:
            y_pred = np.polyval(coeffs, x)
            ss_res = float(np.sum((y - y_pred) ** 2))
            ss_tot = float(np.sum((y - np.mean(y)) ** 2))
            r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0

        base_confidence = 75 + int(r_squared * 10)
        data_bonus = min(len(values), 7)
        confidence = min(max(base_confidence + data_bonus, 75), 92)

        return forecast_value, forecast_low, forecast_high, confidence

    @staticmethod
    def _detect_trend(values: list[float]) -> str:
        """Classify the trend as ``increasing``, ``decreasing``, or ``stable``."""
        if len(values) < 2:
            return "stable"
        x = np.arange(len(values), dtype=float)
        y = np.array(values, dtype=float)
        slope = np.polyfit(x, y, 1)[0]
        mean_val = np.mean(y)
        if mean_val == 0:
            return "stable"
        relative_slope = slope / mean_val
        if relative_slope > 0.02:
            return "increasing"
        if relative_slope < -0.02:
            return "decreasing"
        return "stable"

    def _build_date_range(self, df: pd.DataFrame) -> str:
        """Build a human-readable date range string."""
        if self.date_col and self.date_col in df.columns:
            try:
                dates = df[self.date_col].dropna()
                if dates.empty:
                    return "N/A"
                min_date = dates.min()
                max_date = dates.max()
                return f"{min_date.strftime('%b %Y')} - {max_date.strftime('%b %Y')}"
            except (AttributeError, TypeError):
                return "N/A"
        return "N/A"

    def _extract_categories(self, df: pd.DataFrame) -> list[str]:
        """Extract top category values from detected categorical columns."""
        categories: list[str] = []
        for col in self.category_cols[:3]:
            top_vals = df[col].value_counts().head(5).index.tolist()
            categories.extend(f"{col}:{v}" for v in top_vals)
        return categories[:15]

    def _compute_extra_stats(self, df: pd.DataFrame) -> dict:
        """Compute descriptive statistics for the value column."""
        if not self.value_col:
            return {}
        series = df[self.value_col].dropna()
        if series.empty:
            return {}
        return {
            "mean": round(float(series.mean()), 2),
            "median": round(float(series.median()), 2),
            "std": round(float(series.std()), 2),
            "min": round(float(series.min()), 2),
            "max": round(float(series.max()), 2),
            "sum": round(float(series.sum()), 2),
            "count": int(series.count()),
            "skewness": round(float(series.skew()), 3),
        }

    @staticmethod
    def _build_summary(
        *,
        monthly_revenue: dict,
        rolling_avg_30: float,
        rolling_avg_90: float,
        yoy_growth: float,
        qoq_growth: float,
        forecast_value: float,
        forecast_low: float,
        forecast_high: float,
        confidence: int,
        trend_direction: str,
        date_range: str,
        row_count: int,
        top_categories: list[str],
        extra_stats: dict,
        query: str,
    ) -> str:
        """Construct a rich human-readable summary for LLM prompt injection."""
        lines = [
            "═══ REAL DATA ANALYSIS RESULTS ═══",
            f"Dataset: {row_count} records | Period: {date_range}",
            "",
            "Monthly Aggregated Values:",
        ]
        for period, val in monthly_revenue.items():
            lines.append(f"  {period}: ${val:,.0f}")

        lines += [
            "",
            f"30-Day Rolling Avg: ${rolling_avg_30:,.0f}",
            f"90-Day Rolling Avg: ${rolling_avg_90:,.0f}",
            f"YoY Growth: {yoy_growth:+.1f}%",
            f"QoQ Growth: {qoq_growth:+.1f}%",
            f"Trend: {trend_direction}",
            "",
            "Forecast (linear regression):",
            f"  Point estimate: ${forecast_value:,.0f}",
            f"  Range: ${forecast_low:,.0f} – ${forecast_high:,.0f}",
            f"  Confidence: {confidence}%",
        ]

        if extra_stats:
            lines += [
                "",
                "Descriptive Statistics:",
                f"  Mean: ${extra_stats.get('mean', 0):,.2f}",
                f"  Median: ${extra_stats.get('median', 0):,.2f}",
                f"  Std Dev: ${extra_stats.get('std', 0):,.2f}",
                f"  Min: ${extra_stats.get('min', 0):,.2f}",
                f"  Max: ${extra_stats.get('max', 0):,.2f}",
            ]

        if top_categories:
            lines += ["", "Detected Categories:"]
            for cat in top_categories[:10]:
                lines.append(f"  • {cat}")

        if query:
            lines += ["", f"User Query: {query}"]

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Module-level convenience function
# ═══════════════════════════════════════════════════════════════════════════


def analyze_from_demo() -> AnalysisResult:
    """Create an :class:`AnalysisResult` from built-in demo data.

    Imports ``DEMO_SALES_DATA`` from :mod:`data.sample_data` and
    constructs an ``AnalysisResult`` directly (no CSV/upload needed).
    This powers the ``/demo`` command in the Telegram bot.
    """
    from data.sample_data import DEMO_SALES_DATA

    data = DEMO_SALES_DATA
    monthly = data["monthly_revenue"]

    values = list(monthly.values())

    # Forecast via linear regression on the monthly values
    forecast_value, forecast_low, forecast_high, confidence = (
        DataAnalyzer._linear_forecast(values)
    )

    trend = DataAnalyzer._detect_trend(values)

    # Build a summary that mirrors what DataAnalyzer.analyze() would produce
    summary_lines = [
        "═══ DEMO DATA ANALYSIS RESULTS ═══",
        f"Store: {data['store_id']} | Region: {data['region']} "
        f"| Product: {data['product']}",
        f"Period: {data['period']}",
        "",
        "Monthly Revenue:",
    ]
    for period, val in monthly.items():
        summary_lines.append(f"  {period}: ${val:,.0f}")
    summary_lines += [
        "",
        f"30-Day Rolling Avg: ${data['30_day_rolling_avg']:,.0f}",
        f"90-Day Rolling Avg: ${data['90_day_rolling_avg']:,.0f}",
        f"YoY Growth: +{data['yoy_growth_percent']}%",
        f"QoQ Growth: +{data['qoq_growth_percent']}%",
        f"Trend: {trend}",
        "",
        f"Pipeline: {data['top_deals_pipeline']} deals worth "
        f"${data['pipeline_value']:,.0f}",
        f"Avg Deal Size: ${data['avg_deal_size']:,.0f}",
        f"Win Rate: {data['win_rate_percent']}%",
        f"Deal Velocity: {data['deal_velocity_days']} days",
        "",
        "Forecast (linear regression):",
        f"  Point estimate: ${forecast_value:,.0f}",
        f"  Range: ${forecast_low:,.0f} – ${forecast_high:,.0f}",
        f"  Confidence: {confidence}%",
    ]

    extra_stats = {
        "mean": round(float(np.mean(values)), 2),
        "median": round(float(np.median(values)), 2),
        "std": round(float(np.std(values, ddof=1)), 2),
        "min": round(float(np.min(values)), 2),
        "max": round(float(np.max(values)), 2),
        "sum": round(float(np.sum(values)), 2),
        "count": len(values),
    }

    return AnalysisResult(
        summary_text="\n".join(summary_lines),
        monthly_revenue=monthly,
        rolling_avg_30=float(data["30_day_rolling_avg"]),
        rolling_avg_90=float(data["90_day_rolling_avg"]),
        yoy_growth=float(data["yoy_growth_percent"]),
        qoq_growth=float(data["qoq_growth_percent"]),
        forecast_value=forecast_value,
        forecast_low=forecast_low,
        forecast_high=forecast_high,
        confidence_percent=confidence,
        trend_direction=trend,
        column_info={
            "date_col": "month",
            "value_col": "revenue",
            "category_cols": ["region", "product"],
            "total_columns": 4,
        },
        row_count=len(values),
        date_range=data["period"],
        top_categories=["region:North America", "product:Enterprise Software"],
        extra_stats=extra_stats,
    )
