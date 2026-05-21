"""
RAG Financial Analysis — PDF Executive Report Generator
Professional multi-page PDF reports using ReportLab.
"""
import io
import logging
from datetime import datetime
from typing import Optional

from core.analyzer import AnalysisResult

logger = logging.getLogger(__name__)

# ─── Color Palette ──────────────────────────────────────────────────────────
_DARK_NAVY = (13 / 255, 17 / 255, 23 / 255)         # #0d1117
_SLATE = (22 / 255, 27 / 255, 34 / 255)              # #161b22
_ACCENT_BLUE = (74 / 255, 144 / 255, 217 / 255)      # #4A90D9
_GREEN = (46 / 255, 204 / 255, 113 / 255)             # #2ECC71
_GOLD = (240 / 255, 230 / 255, 140 / 255)             # #F0E68C
_WHITE = (1, 1, 1)
_LIGHT_GRAY = (0.93, 0.93, 0.95)
_MID_GRAY = (0.6, 0.6, 0.65)
_TABLE_HEADER_BG = (0.12, 0.14, 0.18)
_TABLE_ROW_ALT = (0.96, 0.96, 0.98)


def _fmt_currency(val: float) -> str:
    """Format a numeric value as a currency string ($X.XXM or $X,XXX)."""
    if abs(val) >= 1_000_000:
        return f"${val / 1_000_000:,.2f}M"
    if abs(val) >= 1_000:
        return f"${val / 1_000:,.1f}K"
    return f"${val:,.0f}"


def _footer(canvas, doc):
    """Draw footer on every page: confidentiality line + page number."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColorRGB(*_MID_GRAY)
    canvas.drawString(
        doc.leftMargin,
        22,
        "RAG Financial Analysis System  |  Confidential  |  "
        f"Generated {datetime.now().strftime('%d %b %Y %H:%M')}"
    )
    canvas.drawRightString(
        doc.pagesize[0] - doc.rightMargin,
        22,
        f"Page {doc.page}"
    )
    # Thin accent line above footer
    canvas.setStrokeColorRGB(*_ACCENT_BLUE)
    canvas.setLineWidth(0.5)
    canvas.line(
        doc.leftMargin, 36,
        doc.pagesize[0] - doc.rightMargin, 36
    )
    canvas.restoreState()


def generate_pdf_report(
    analysis: AnalysisResult,
    forecast: dict,
    chart_png: Optional[bytes] = None,
    query: str = "",
) -> bytes:
    """Generate a professional multi-page PDF executive report.

    Pages:
        1. Cover page — title, branding, date, query context
        2. Executive summary — forecast table, key drivers, analysis
        3. Revenue chart (if chart_png provided)
        4. Data overview — methodology, column mapping, statistics

    Args:
        analysis: AnalysisResult from data analysis.
        forecast: Dict with forecast_value, confidence_percent, range_low,
                  range_high, timeframe, key_drivers, reasoning,
                  market_signal, risk.
        chart_png: Optional PNG bytes for the revenue chart.
        query: The original user query.

    Returns:
        Complete PDF file as bytes.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import inch, cm
        from reportlab.lib.colors import Color, HexColor
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph,
            Spacer, Image, PageBreak, HRFlowable,
        )
        from reportlab.lib import colors
    except ImportError as e:
        logger.error(f"reportlab not installed: {e}")
        raise RuntimeError("reportlab is required for PDF generation. Install with: pip install reportlab") from e

    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
        title="RAG Financial Analysis — Executive Report",
        author="RAG Financial Analysis System",
    )

    # ── Styles ───────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    s_cover_title = ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontSize=28,
        leading=34,
        textColor=HexColor("#0d1117"),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    s_cover_sub = ParagraphStyle(
        "CoverSub",
        parent=styles["Normal"],
        fontSize=13,
        leading=18,
        textColor=HexColor("#4A90D9"),
        alignment=TA_CENTER,
        fontName="Helvetica",
    )
    s_section = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=16,
        leading=22,
        textColor=HexColor("#0d1117"),
        spaceBefore=18,
        spaceAfter=8,
        fontName="Helvetica-Bold",
        borderWidth=0,
        borderPadding=0,
    )
    s_body = ParagraphStyle(
        "BodyText2",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=HexColor("#333333"),
        spaceAfter=6,
        fontName="Helvetica",
        alignment=TA_JUSTIFY,
    )
    s_body_bold = ParagraphStyle(
        "BodyBold",
        parent=s_body,
        fontName="Helvetica-Bold",
    )
    s_caption = ParagraphStyle(
        "Caption",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=HexColor("#8b949e"),
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    s_metric_big = ParagraphStyle(
        "MetricBig",
        parent=styles["Normal"],
        fontSize=22,
        leading=28,
        textColor=HexColor("#2ECC71"),
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )

    elements = []

    # ── Extract forecast values ──────────────────────────────────────────
    fv = forecast.get("forecast_value", analysis.forecast_value)
    conf = forecast.get("confidence_percent", analysis.confidence_percent)
    low = forecast.get("range_low", analysis.forecast_low)
    high = forecast.get("range_high", analysis.forecast_high)
    tf = forecast.get("timeframe", "Next Quarter")
    drivers = forecast.get("key_drivers", [])
    reasoning = forecast.get("reasoning", "")
    market_sig = forecast.get("market_signal", "")
    risk = forecast.get("risk", "")

    # ═════════════════════════════════════════════════════════════════════
    # PAGE 1 — COVER PAGE
    # ═════════════════════════════════════════════════════════════════════

    elements.append(Spacer(1, 2.5 * inch))

    # Accent bar
    elements.append(HRFlowable(
        width="80%", thickness=3,
        color=HexColor("#4A90D9"),
        spaceBefore=0, spaceAfter=20,
    ))

    elements.append(Paragraph(
        "RAG Financial Analysis",
        s_cover_title,
    ))
    elements.append(Paragraph(
        "Executive Report",
        ParagraphStyle(
            "CoverTitle2",
            parent=s_cover_title,
            fontSize=20,
            textColor=HexColor("#4A90D9"),
            spaceAfter=20,
        )
    ))

    elements.append(HRFlowable(
        width="80%", thickness=1,
        color=HexColor("#30363d"),
        spaceBefore=10, spaceAfter=30,
    ))

    elements.append(Paragraph(
        f"Forecast Period: {tf}",
        s_cover_sub,
    ))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        datetime.now().strftime("%d %B %Y  •  %H:%M UTC"),
        ParagraphStyle(
            "CoverDate",
            parent=s_cover_sub,
            fontSize=11,
            textColor=HexColor("#8b949e"),
        )
    ))

    if query:
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(
            f'Query: "{query}"',
            ParagraphStyle(
                "CoverQuery",
                parent=s_body,
                fontSize=10,
                alignment=TA_CENTER,
                textColor=HexColor("#8b949e"),
                fontName="Helvetica-Oblique",
            )
        ))

    elements.append(Spacer(1, 1.5 * inch))

    # Bottom branding
    elements.append(Paragraph(
        "Powered by Pinecone Vector DB  •  Gemini 3.1 Flash-Lite  •  NewsData.io  •  Alpha Vantage",
        ParagraphStyle(
            "CoverBranding",
            parent=s_caption,
            fontSize=8,
            textColor=HexColor("#8b949e"),
        )
    ))

    elements.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # PAGE 2 — EXECUTIVE SUMMARY
    # ═════════════════════════════════════════════════════════════════════

    elements.append(Paragraph("Executive Summary", s_section))
    elements.append(HRFlowable(
        width="100%", thickness=2,
        color=HexColor("#4A90D9"),
        spaceBefore=0, spaceAfter=14,
    ))

    # Big metric
    elements.append(Paragraph(
        f"Predicted Revenue: {_fmt_currency(fv)}",
        s_metric_big,
    ))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        f"Confidence: {conf}%  |  Range: {_fmt_currency(low)} — {_fmt_currency(high)}  |  Timeframe: {tf}",
        ParagraphStyle("MetricSub", parent=s_body, alignment=TA_CENTER, textColor=HexColor("#4A90D9")),
    ))
    elements.append(Spacer(1, 18))

    # Forecast Summary Table
    elements.append(Paragraph("Forecast Details", s_section))

    table_data = [
        ["Metric", "Value"],
        ["Predicted Revenue", _fmt_currency(fv)],
        ["Confidence Level", f"{conf}%"],
        ["Range (Low)", _fmt_currency(low)],
        ["Range (High)", _fmt_currency(high)],
        ["Forecast Period", str(tf)],
        ["90-Day Rolling Avg", _fmt_currency(analysis.rolling_avg_90)],
        ["YoY Growth", f"{'+' if analysis.yoy_growth >= 0 else ''}{analysis.yoy_growth:.1f}%"],
        ["QoQ Growth", f"{'+' if analysis.qoq_growth >= 0 else ''}{analysis.qoq_growth:.1f}%"],
        ["Trend Direction", analysis.trend_direction.title()],
        ["Data Rows", f"{analysis.row_count:,}"],
        ["Date Range", analysis.date_range],
    ]

    col_widths = [3.2 * inch, 3.5 * inch]
    tbl = Table(table_data, colWidths=col_widths)

    tbl_style = TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0d1117")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        # Body rows
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#d0d7de")),
        ("LINEBELOW", (0, 0), (-1, 0), 2, HexColor("#4A90D9")),
        # Alignment
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ])

    # Alternate row shading
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            tbl_style.add("BACKGROUND", (0, i), (-1, i), HexColor("#f6f8fa"))

    tbl.setStyle(tbl_style)
    elements.append(tbl)
    elements.append(Spacer(1, 18))

    # Key Drivers
    if drivers:
        elements.append(Paragraph("Key Drivers", s_section))
        for i, d in enumerate(drivers[:5], 1):
            elements.append(Paragraph(f"  {i}.  {d}", s_body))
        elements.append(Spacer(1, 10))

    # AI Analysis
    if reasoning:
        elements.append(Paragraph("AI Analysis", s_section))
        elements.append(Paragraph(reasoning, s_body))
        elements.append(Spacer(1, 10))

    # Market Signal
    if market_sig:
        elements.append(Paragraph("Market Signal", s_section))
        elements.append(Paragraph(f'"{market_sig}"', ParagraphStyle(
            "ItalicBody", parent=s_body, fontName="Helvetica-Oblique",
            textColor=HexColor("#4A90D9"),
        )))
        elements.append(Spacer(1, 10))

    # Risk Factor
    if risk:
        elements.append(Paragraph("Risk Factor", s_section))
        elements.append(Paragraph(risk, ParagraphStyle(
            "RiskBody", parent=s_body, textColor=HexColor("#d1242f"),
        )))

    elements.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # PAGE 3 — REVENUE CHART
    # ═════════════════════════════════════════════════════════════════════

    if chart_png:
        elements.append(Paragraph("Revenue Forecast Chart", s_section))
        elements.append(HRFlowable(
            width="100%", thickness=2,
            color=HexColor("#4A90D9"),
            spaceBefore=0, spaceAfter=14,
        ))

        try:
            chart_buf = io.BytesIO(chart_png)
            chart_img = Image(chart_buf, width=6.5 * inch, height=3.8 * inch)
            chart_img.hAlign = "CENTER"
            elements.append(Spacer(1, 10))
            elements.append(chart_img)
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(
                f"Figure 1: Revenue trend with {tf} forecast  |  "
                f"Blue = Historical  •  Green = Forecast  •  Yellow = Confidence Interval",
                s_caption,
            ))
        except Exception as e:
            logger.warning(f"Failed to embed chart in PDF: {e}")
            elements.append(Paragraph(
                "[Chart could not be embedded]", s_body
            ))

        # Monthly Revenue Table
        monthly = analysis.monthly_revenue
        if monthly:
            elements.append(Spacer(1, 20))
            elements.append(Paragraph("Monthly Revenue Breakdown", s_section))

            rev_table_data = [["Period", "Revenue", "Change"]]
            prev_val = None
            for period, val in monthly.items():
                change = ""
                if prev_val is not None and prev_val > 0:
                    pct_change = ((val - prev_val) / prev_val) * 100
                    sign = "+" if pct_change >= 0 else ""
                    change = f"{sign}{pct_change:.1f}%"
                rev_table_data.append([str(period), _fmt_currency(val), change])
                prev_val = val

            # Add forecast row
            if prev_val is not None and prev_val > 0:
                pct_change = ((fv - prev_val) / prev_val) * 100
                sign = "+" if pct_change >= 0 else ""
                change = f"{sign}{pct_change:.1f}%"
            else:
                change = ""
            rev_table_data.append([f"{tf} (Forecast)", _fmt_currency(fv), change])

            rev_col_widths = [2.5 * inch, 2.2 * inch, 2.0 * inch]
            rev_tbl = Table(rev_table_data, colWidths=rev_col_widths)

            rev_style = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0d1117")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("TOPPADDING", (0, 0), (-1, 0), 7),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                ("TOPPADDING", (0, 1), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#d0d7de")),
                ("LINEBELOW", (0, 0), (-1, 0), 2, HexColor("#4A90D9")),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                # Highlight forecast row
                ("BACKGROUND", (0, -1), (-1, -1), HexColor("#e6fff0")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ])
            for i in range(1, len(rev_table_data) - 1):
                if i % 2 == 0:
                    rev_style.add("BACKGROUND", (0, i), (-1, i), HexColor("#f6f8fa"))
            rev_tbl.setStyle(rev_style)
            elements.append(rev_tbl)

        elements.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # PAGE 4 — DATA OVERVIEW & METHODOLOGY
    # ═════════════════════════════════════════════════════════════════════

    elements.append(Paragraph("Data Overview &amp; Methodology", s_section))
    elements.append(HRFlowable(
        width="100%", thickness=2,
        color=HexColor("#4A90D9"),
        spaceBefore=0, spaceAfter=14,
    ))

    # Column mapping table
    elements.append(Paragraph("Detected Column Mapping", s_body_bold))
    elements.append(Spacer(1, 6))

    col_info = analysis.column_info
    col_table_data = [
        ["Role", "Detected Column"],
        ["Date / Time", col_info.get("date_col", "—")],
        ["Revenue / Value", col_info.get("value_col", "—")],
        ["Region / Segment", col_info.get("region_col", "—")],
        ["Product / Category", col_info.get("product_col", "—")],
    ]
    col_tbl = Table(col_table_data, colWidths=[3.0 * inch, 3.7 * inch])
    col_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0d1117")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#d0d7de")),
        ("LINEBELOW", (0, 0), (-1, 0), 2, HexColor("#4A90D9")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(col_tbl)
    elements.append(Spacer(1, 18))

    # Extra statistics
    extra = analysis.extra_stats
    if extra:
        elements.append(Paragraph("Statistical Summary", s_body_bold))
        elements.append(Spacer(1, 6))

        stat_data = [["Statistic", "Value"]]
        stat_keys = [
            ("mean", "Mean Revenue"),
            ("median", "Median Revenue"),
            ("std", "Standard Deviation"),
            ("min", "Minimum"),
            ("max", "Maximum"),
            ("count", "Record Count"),
        ]
        for key, label in stat_keys:
            val = extra.get(key)
            if val is not None:
                if key == "count":
                    stat_data.append([label, f"{int(val):,}"])
                else:
                    stat_data.append([label, _fmt_currency(float(val))])

        if len(stat_data) > 1:
            stat_tbl = Table(stat_data, colWidths=[3.0 * inch, 3.7 * inch])
            stat_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0d1117")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#d0d7de")),
                ("LINEBELOW", (0, 0), (-1, 0), 2, HexColor("#4A90D9")),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]))
            for i in range(1, len(stat_data)):
                if i % 2 == 0:
                    stat_tbl.setStyle(TableStyle([
                        ("BACKGROUND", (0, i), (-1, i), HexColor("#f6f8fa")),
                    ]))
            elements.append(stat_tbl)
            elements.append(Spacer(1, 18))

    # Categories
    if analysis.top_categories:
        elements.append(Paragraph("Detected Categories", s_body_bold))
        elements.append(Paragraph(
            ", ".join(analysis.top_categories[:10]),
            s_body,
        ))
        elements.append(Spacer(1, 18))

    # Methodology
    elements.append(Paragraph("Methodology", s_body_bold))
    elements.append(Spacer(1, 4))
    methodology_text = (
        "This report was generated by the RAG Financial Analysis System using "
        "a Retrieval-Augmented Generation (RAG) pipeline. The process includes: "
        "(1) Statistical analysis of historical revenue data using pandas and NumPy, "
        "including rolling averages, growth rates, and linear regression forecasting; "
        "(2) Semantic search of financial market intelligence via Pinecone vector database "
        "with Gemini text-embedding-004 embeddings (768 dimensions, cosine similarity); "
        "(3) Real-time news retrieval from NewsData.io and Alpha Vantage market data; "
        "(4) AI-powered forecast generation using Google Gemini 3.1 Flash-Lite "
        "with chain-of-thought reasoning, augmented by the retrieved context."
    )
    elements.append(Paragraph(methodology_text, s_body))
    elements.append(Spacer(1, 14))

    # Disclaimer
    elements.append(HRFlowable(
        width="100%", thickness=0.5,
        color=HexColor("#d0d7de"),
        spaceBefore=10, spaceAfter=10,
    ))
    elements.append(Paragraph(
        "<b>Disclaimer:</b> This report is generated by an AI system for informational "
        "purposes only. It should not be considered financial advice. All forecasts "
        "are probabilistic estimates based on historical data and market signals. "
        "Past performance does not guarantee future results.",
        ParagraphStyle(
            "Disclaimer", parent=s_body,
            fontSize=8, leading=10,
            textColor=HexColor("#8b949e"),
        )
    ))

    # ── Build PDF ────────────────────────────────────────────────────────
    try:
        doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
    except Exception as e:
        logger.error(f"PDF build failed: {e}")
        raise

    pdf_bytes = buf.getvalue()
    buf.close()

    logger.info(f"Generated PDF report: {len(pdf_bytes):,} bytes, ~{doc.page} pages")
    return pdf_bytes
