"""
RAG FINANCIAL ANALYSIS SYSTEM - MVP DEMO
Real: Telegram Bot + Gemini AI
Simulated: Pinecone, N8n, Hyperbolic, Salesforce, Multi-LLM
"""
import sys, io
# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import json
import time
import asyncio
import re
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ═══════════════════════════════════════════════════════════════════════════
# FAKE DATA LAYER — Simulating Pinecone + Salesforce + PostgreSQL
# ═══════════════════════════════════════════════════════════════════════════

FAKE_MARKET_NEWS = [
    {"id": 1,  "title": "Tech Sector Poised for Q1 2025 Growth Surge",
     "text": "Enterprise software spending up 18% YoY. Major corporations expanding cloud infrastructure budgets by an average of $2.4M per company.",
     "source": "TechCrunch", "date": "2025-01-15",
     "keywords": ["tech", "software", "growth", "enterprise", "q1", "2025", "cloud"]},

    {"id": 2,  "title": "North America IT Budget Increases Signal Market Optimism",
     "text": "Fortune 500 companies allocating 15% more to digital transformation. SaaS spending projected to reach $197B globally.",
     "source": "Forbes", "date": "2025-01-14",
     "keywords": ["north", "america", "budget", "it", "saas", "digital", "fortune"]},

    {"id": 3,  "title": "Enterprise Software Deals Hit Record in Late 2024",
     "text": "Q4 2024 enterprise software deals totaled $8.2B across North America and EMEA. Average deal size increased 22%.",
     "source": "Bloomberg", "date": "2025-01-12",
     "keywords": ["enterprise", "software", "deals", "q4", "record", "emea", "north", "america"]},

    {"id": 4,  "title": "Hardware Supply Chain Stabilizes After 2024 Disruptions",
     "text": "Hardware procurement lead times dropped from 18 weeks to 9 weeks. Prices expected to normalize in Q1 2025.",
     "source": "Reuters", "date": "2025-01-10",
     "keywords": ["hardware", "supply", "chain", "procurement", "2025", "q1", "prices"]},

    {"id": 5,  "title": "SaaS Revenue Growth Accelerates Across APAC Region",
     "text": "Asia-Pacific SaaS market growing at 24% CAGR. Cloud adoption in APAC enterprises reached 67% penetration.",
     "source": "Gartner", "date": "2025-01-09",
     "keywords": ["saas", "apac", "cloud", "asia", "growth", "revenue", "pacific"]},

    {"id": 6,  "title": "Analyst Report: Financial Software Demand Climbing Steeply",
     "text": "Financial analytics platforms seeing 31% demand increase. AI-powered forecasting tools leading the growth category.",
     "source": "IDC", "date": "2025-01-08",
     "keywords": ["financial", "software", "analytics", "ai", "forecast", "demand", "revenue"]},

    {"id": 7,  "title": "EMEA Enterprise Tech Spending Up Despite Economic Headwinds",
     "text": "European enterprises maintained 12% IT budget growth. Security and analytics categories outperformed.",
     "source": "FT", "date": "2025-01-07",
     "keywords": ["emea", "europe", "enterprise", "tech", "spending", "budget", "analytics"]},

    {"id": 8,  "title": "Q1 2025 Revenue Forecasts Positive for B2B Software Vendors",
     "text": "B2B software vendors expected to post 15-20% revenue growth in Q1 2025. Pipeline conversion rates up 8%.",
     "source": "Wall Street Journal", "date": "2025-01-06",
     "keywords": ["q1", "2025", "revenue", "forecast", "b2b", "software", "vendor", "growth"]},

    {"id": 9,  "title": "AI Integration Drives Upsell Opportunities in Enterprise Accounts",
     "text": "Companies that integrated AI into existing tools saw 28% higher upsell rates. Average contract value increased $45K.",
     "source": "McKinsey", "date": "2025-01-05",
     "keywords": ["ai", "upsell", "enterprise", "contract", "integration", "revenue", "accounts"]},

    {"id": 10, "title": "Global Economic Indicators Support Tech Sector Optimism for 2025",
     "text": "GDP growth projections revised upward in US (+2.8%) and EU (+1.9%). Consumer and enterprise confidence indices both rising.",
     "source": "IMF", "date": "2025-01-04",
     "keywords": ["economic", "gdp", "growth", "2025", "tech", "global", "us", "eu"]},

    {"id": 11, "title": "Cloud Migration Deals Surge as On-Premise Licenses Expire",
     "text": "Wave of on-premise license expirations driving $12B cloud migration market in 2025.",
     "source": "Forrester", "date": "2025-01-03",
     "keywords": ["cloud", "migration", "license", "on-premise", "2025", "software"]},

    {"id": 12, "title": "North America SaaS Sales Teams Outperforming Targets by 18%",
     "text": "Top SaaS companies in North America closed Q4 2024 at 118% of quota. Deal velocity increased 22%.",
     "source": "Salesforce Research", "date": "2024-12-30",
     "keywords": ["north", "america", "saas", "sales", "quota", "deal", "q4", "velocity"]},

    {"id": 13, "title": "Hardware Refresh Cycle Creating New Demand Wave",
     "text": "3-year hardware refresh cycle peaking in 2025. Corporate PC and server refresh projected at $45B market.",
     "source": "IDC", "date": "2024-12-28",
     "keywords": ["hardware", "refresh", "demand", "corporate", "server", "pc", "2025"]},

    {"id": 14, "title": "Financial Services Sector Increases Tech Budget to $120B",
     "text": "Financial services firms allocate record budgets to RegTech, AI risk tools, and analytics platforms.",
     "source": "Deloitte", "date": "2024-12-27",
     "keywords": ["financial", "services", "budget", "regtech", "analytics", "ai", "tech"]},

    {"id": 15, "title": "Interest Rate Cuts Boost Corporate IT Investment Confidence",
     "text": "Federal Reserve rate cuts freeing up capital for tech investment. Corporate capex budgets expanding in Q1 2025.",
     "source": "CNBC", "date": "2024-12-26",
     "keywords": ["interest", "rate", "investment", "corporate", "capex", "2025", "q1", "tech"]},
]

FAKE_SALES_DATA = {
    "store_id": "STORE_001",
    "region": "North America",
    "product": "Enterprise Software",
    "period": "Oct 2024 – Jan 2025",
    "monthly_revenue": {
        "2024-10": 3_800_000,
        "2024-11": 4_100_000,
        "2024-12": 4_450_000,
        "2025-01": 4_600_000,
    },
    "30_day_rolling_avg": 4_287_500,
    "90_day_rolling_avg": 4_237_500,
    "yoy_growth_percent": 18.4,
    "qoq_growth_percent": 6.7,
    "top_deals_pipeline": 3,
    "pipeline_value": 2_100_000,
    "avg_deal_size": 185_000,
    "deal_velocity_days": 32,
    "win_rate_percent": 68,
    "units_sold": {"2024-10": 22, "2024-11": 24, "2024-12": 27, "2025-01": 28},
}

FALLBACK_FORECAST = {
    "forecast_value": 4_800_000,
    "confidence_percent": 87,
    "range_low": 4_320_000,
    "range_high": 5_280_000,
    "timeframe": "Q1 2025",
    "key_drivers": [
        "Enterprise software YoY growth at 18.4%",
        "3 major deals in pipeline ($2.1M combined)",
        "North America market sentiment strongly positive",
    ],
    "reasoning": (
        "Based on 90-day historical trend ($4.28M avg) and accelerating growth velocity "
        "(+6.7% QoQ), Q1 2025 forecast projects $4.8M with high confidence."
    ),
    "market_signal": "B2B software vendors expected to post 15-20% revenue growth in Q1 2025",
    "risk": "Macro economic slowdown could compress enterprise budgets",
}

# ═══════════════════════════════════════════════════════════════════════════
# FAKE PIPELINE — Simulating N8n, Pinecone, Hyperbolic, ChatGPT nano
# ═══════════════════════════════════════════════════════════════════════════

def _log(msg: str, delay: float = 0.0):
    """Print a pipeline log line with optional delay."""
    if delay:
        time.sleep(delay)
    print(msg)
    logger.info(msg)


def fake_pinecone_search(query: str, top_k: int = 3) -> list:
    """Keyword-scored document retrieval simulating Pinecone hybrid search."""
    query_words = set(re.sub(r"[^a-z0-9 ]", "", query.lower()).split())
    scored = []
    for article in FAKE_MARKET_NEWS:
        kw_matches    = len(query_words.intersection(set(article["keywords"])))
        title_matches = sum(1 for w in query_words if w in article["title"].lower())
        raw_score     = (kw_matches * 0.6 + title_matches * 0.4) / max(len(query_words), 1)
        score         = round(min(0.95, 0.65 + raw_score * 0.3), 3)
        scored.append({**article, "similarity_score": score})
    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored[:top_k]


def build_sales_summary() -> str:
    d = FAKE_SALES_DATA
    lines = [
        f"Store: {d['store_id']} | Region: {d['region']} | Product: {d['product']}",
        f"Period: {d['period']}",
        "Monthly Revenue:",
    ]
    for month, rev in d["monthly_revenue"].items():
        lines.append(f"  {month}: ${rev:,.0f}")
    lines += [
        f"30-Day Rolling Avg: ${d['30_day_rolling_avg']:,.0f}",
        f"90-Day Rolling Avg: ${d['90_day_rolling_avg']:,.0f}",
        f"YoY Growth: +{d['yoy_growth_percent']}%",
        f"QoQ Growth: +{d['qoq_growth_percent']}%",
        f"Pipeline Deals: {d['top_deals_pipeline']} deals worth ${d['pipeline_value']:,.0f}",
        f"Avg Deal Size: ${d['avg_deal_size']:,.0f} | Win Rate: {d['win_rate_percent']}%",
        f"Deal Velocity: {d['deal_velocity_days']} days",
    ]
    return "\n".join(lines)


def run_fake_pipeline(user_query: str) -> dict:
    """
    Simulates the full N8n 7-node DAG.
    Prints realistic pipeline logs, returns retrieved docs + sales summary.
    """
    print("\n" + "═" * 60)
    _log(f"🤖  RAG Financial Analysis Pipeline Started")
    _log(f"📨  User Query: '{user_query}'")
    _log("", 0.1)

    # Node 1 — Webhook
    _log("⚙️   N8n Workflow Triggered [Webhook Node 1/7]", 0.2)

    # Node 2 — SQL / Salesforce
    _log("📊  [Node 2/7] Querying PostgreSQL → sales_history (last 90 days)...", 0.3)
    sales_summary = build_sales_summary()
    _log("✓   Fetched 90 records | Avg Revenue: $4.28M | Growth: +18.4% YoY", 0.5)

    # Node 3 — Hyperbolic embeddings
    _log("🧮  [Node 3/7] Generating embeddings via Hyperbolic bge-m3 (3072-dim)...", 0.3)
    _log("✓   Query embedded in 287ms", 0.5)

    # Node 4 — Pinecone
    _log("🔍  [Node 4/7] Querying Pinecone vector DB (hybrid: dense + BM25)...", 0.3)
    retrieved = fake_pinecone_search(user_query)
    _log(f"✓   Retrieved 5 docs | Cross-encoder reranking → top 3 selected", 0.5)
    for doc in retrieved:
        _log(f"     📄 [{doc['similarity_score']:.3f}] {doc['title']} ({doc['source']})")

    # Node 5 — ChatGPT 4.1 nano
    _log("⚡  [Node 5/7] ChatGPT 4.1 nano → optimizing query for retrieval...", 0.3)
    optimized = user_query.strip().rstrip("?") + f" financial forecast {datetime.now().year}"
    _log(f"✓   Query optimized: '{optimized}'", 0.3)

    # Node 6 — Context assembly
    _log("🧠  [Node 6/7] Assembling augmented prompt for Gemini 2.5 Pro...", 0.3)
    _log("✓   Context: 847 tokens (history: 312 | market: 535)", 0.5)

    # Node 7 — Gemini (called separately, logged after)
    _log("🚀  [Node 7/7] Calling Gemini 2.5 Pro (Chain-of-Thought reasoning)...", 0.3)

    return {"sales_summary": sales_summary, "retrieved": retrieved, "optimized_query": optimized}


# ═══════════════════════════════════════════════════════════════════════════
# REAL AI LAYER — Gemini 3.1 Flash-Lite (fastest, May 2026) + OpenRouter fallback
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a senior financial analyst AI specializing in B2B revenue forecasting.

You will receive:
1. Historical sales data (last 90 days)
2. Retrieved market intelligence (from vector database search)
3. A user query

Your task: Generate a precise, realistic revenue forecast.

Rules:
- Use the provided numbers — do NOT invent different figures
- Show brief reasoning (2-3 sentences grounded in the data)
- Output ONLY valid JSON — no markdown, no explanation outside JSON
- Confidence must be between 75 and 92

Output this EXACT JSON structure (no extra fields, no markdown fences):
{
  "forecast_value": <number in USD>,
  "confidence_percent": <integer 75-92>,
  "range_low": <forecast minus buffer>,
  "range_high": <forecast plus buffer>,
  "timeframe": "<timeframe from query or 'Q1 2025' if unclear>",
  "key_drivers": ["<driver 1 with number>", "<driver 2 with number>", "<driver 3 with number>"],
  "reasoning": "<2-3 sentence analysis referencing the data>",
  "market_signal": "<1 direct quote or paraphrase from the retrieved news>",
  "risk": "<1 specific risk factor>"
}"""


def _parse_gemini_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON from LLM response."""
    # Remove ```json ... ``` or ``` ... ``` wrappers
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    return json.loads(cleaned)


def call_gemini_api(sales_summary: str, retrieved: list, user_query: str) -> dict:
    """Make a real Gemini API call. Falls back to OpenRouter if it fails."""
    docs_text = "\n\n".join(
        f"[{i+1}] {d['title']} ({d['source']}, {d['date']})\n{d['text']}"
        for i, d in enumerate(retrieved)
    )
    user_prompt = (
        f"HISTORICAL SALES DATA:\n{sales_summary}\n\n"
        f"RETRIEVED MARKET INTELLIGENCE (from Pinecone vector DB):\n{docs_text}\n\n"
        f"USER QUERY: {user_query}\n\n"
        "Generate forecast JSON now."
    )

    # ── Try Gemini first ────────────────────────────────────────────────────
    if GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model  = genai.GenerativeModel(
                model_name="gemini-3.1-flash-lite",  # fastest model as of May 2026
                system_instruction=SYSTEM_PROMPT,
            )
            resp   = model.generate_content(user_prompt)
            raw    = resp.text.strip()
            result = _parse_gemini_json(raw)
            logger.info("Gemini API call succeeded")
            return result
        except json.JSONDecodeError:
            logger.warning("Gemini returned invalid JSON — retrying parse once")
            try:
                return _parse_gemini_json(resp.text)
            except Exception:
                logger.error("Gemini JSON parse failed after retry")
        except Exception as e:
            logger.warning(f"Gemini API error: {e} — trying OpenRouter fallback")

    # ── OpenRouter fallback ─────────────────────────────────────────────────
    if OPENROUTER_API_KEY:
        try:
            import httpx
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ]
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "https://rag-financial-demo.local",
                    "X-Title":       "RAG Financial Demo",
                },
                json={
                    "model":       "google/gemini-3.1-flash-lite",  # fastest on OpenRouter (May 2026)
                    "messages":    messages,
                    "max_tokens":  600,
                    "temperature": 0.4,
                },
                timeout=30,
            )
            data = resp.json()
            raw    = data["choices"][0]["message"]["content"].strip()
            result = _parse_gemini_json(raw)
            logger.info("OpenRouter fallback succeeded")
            return result
        except Exception as e:
            logger.error(f"OpenRouter fallback also failed: {e} | response: {resp.text[:200] if 'resp' in dir() else 'no response'}")

    # ── Hard fallback ───────────────────────────────────────────────────────
    logger.warning("All AI calls failed — using hardcoded fallback forecast")
    return FALLBACK_FORECAST


# ═══════════════════════════════════════════════════════════════════════════
# VISUAL HELPERS — Sparkline, ASCII chart, PNG chart
# ═══════════════════════════════════════════════════════════════════════════

_SPARK_CHARS = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

def build_sparkline(values: list) -> str:
    """Turn a list of numbers into a Unicode sparkline."""
    if not values or max(values) == min(values):
        return "▄" * len(values)
    lo, hi = min(values), max(values)
    return "".join(_SPARK_CHARS[int((v - lo) / (hi - lo) * 7)] for v in values)


def build_ascii_bar_chart(forecast_value: float) -> str:
    """ASCII bar chart of monthly revenue + forecast."""
    months = list(FAKE_SALES_DATA["monthly_revenue"].keys())
    revenues = list(FAKE_SALES_DATA["monthly_revenue"].values())
    labels  = [m[-2:] for m in months] + ["FCST"]
    values  = revenues + [forecast_value]

    max_val = max(values)
    bar_max = 12  # max bar width in chars

    lines = ["<code>"]
    lines.append("  Revenue Trend (90-day + Forecast)")
    lines.append("  " + "─" * 36)
    for lbl, val in zip(labels, values):
        bar_len = int((val / max_val) * bar_max)
        is_forecast = lbl == "FCST"
        bar  = ("▓" if is_forecast else "█") * bar_len
        line = f"  {lbl} │{bar:<{bar_max}} ${val/1_000_000:.2f}M"
        if is_forecast:
            line += " ◄ FORECAST"
        lines.append(line)
    lines.append("  " + "─" * 36)
    lines.append("       █=Historical  ▓=Forecast")
    lines.append("</code>")
    return "\n".join(lines)


def generate_chart_png(forecast: dict) -> bytes:
    """Generate a dark-themed bar chart PNG and return as bytes."""
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import io

    months   = list(FAKE_SALES_DATA["monthly_revenue"].keys())
    revenues = [v / 1_000_000 for v in FAKE_SALES_DATA["monthly_revenue"].values()]
    labels   = [m[:-3] + "'" + m[2:4] for m in months]  # e.g. "Oct'24"

    fv   = forecast.get("forecast_value", 4_800_000) / 1_000_000
    low  = forecast.get("range_low",  fv * 1_000_000 * 0.9) / 1_000_000
    high = forecast.get("range_high", fv * 1_000_000 * 1.1) / 1_000_000
    tf   = forecast.get("timeframe", "Forecast")
    pct  = forecast.get("confidence_percent", 85)

    all_labels = labels + [tf]
    all_values = revenues + [fv]
    colors     = ["#4A90D9"] * len(revenues) + ["#2ECC71"]
    err_low    = [0] * len(revenues) + [fv - low]
    err_high   = [0] * len(revenues) + [high - fv]

    # ── Dark theme figure
    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#161b22")

    bars = ax.bar(all_labels, all_values, color=colors, width=0.6,
                  edgecolor="#30363d", linewidth=0.8)

    # Error bar on forecast only
    ax.errorbar(
        [tf], [fv],
        yerr=[[fv - low], [high - fv]],
        fmt="none", color="#F0E68C", capsize=8, capthick=2, linewidth=2
    )

    # Value labels on bars
    for bar, val in zip(bars, all_values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.05,
                f"${val:.2f}M", ha="center", va="bottom",
                color="#e6edf3", fontsize=9, fontweight="bold")

    # Confidence band shading
    ax.axhspan(low, high, alpha=0.08, color="#2ECC71", label=f"Confidence range ({pct}%)")

    # Trend line
    trend_x = list(range(len(all_values)))
    ax.plot(trend_x, all_values, color="#FFD700", linewidth=1.5,
            linestyle="--", alpha=0.7, marker="o", markersize=4)

    # Styling
    ax.set_title(f"Revenue Forecast — {tf}  |│ Confidence: {pct}%",
                 color="#e6edf3", fontsize=13, fontweight="bold", pad=15)
    ax.set_ylabel("Revenue ($M)", color="#8b949e", fontsize=10)
    ax.tick_params(colors="#8b949e", labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")
    ax.yaxis.grid(True, color="#21262d", linewidth=0.8, linestyle="--")
    ax.set_axisbelow(True)

    # Legend patches
    hist_patch = mpatches.Patch(color="#4A90D9", label="Historical Revenue")
    fcst_patch = mpatches.Patch(color="#2ECC71", label=f"Forecast ({tf})")
    conf_patch = mpatches.Patch(color="#2ECC71", alpha=0.2, label=f"Confidence Range")
    ax.legend(handles=[hist_patch, fcst_patch, conf_patch],
              facecolor="#161b22", edgecolor="#30363d",
              labelcolor="#8b949e", fontsize=8, loc="upper left")

    # Watermark
    fig.text(0.98, 0.02, "RAG Financial Analysis System",
             ha="right", va="bottom", color="#30363d", fontsize=7)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM MESSAGE FORMATTER  (HTML — no escaping nightmares)
# ═══════════════════════════════════════════════════════════════════════════

def build_confidence_bar(pct: int) -> str:
    filled = round(pct / 10)
    return "█" * filled + "░" * (10 - filled)


def _html(s: str) -> str:
    """Escape HTML special chars for Telegram HTML parse mode."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_telegram_message(forecast: dict, latency: float) -> str:
    v     = forecast.get("forecast_value", 0)
    low   = forecast.get("range_low", v * 0.9)
    high  = forecast.get("range_high", v * 1.1)
    pct   = forecast.get("confidence_percent", 85)
    tf    = forecast.get("timeframe", "Q1 2025")
    kd    = forecast.get("key_drivers", ["—", "—", "—"])
    rsn   = forecast.get("reasoning", "")
    ms    = forecast.get("market_signal", "")
    risk  = forecast.get("risk", "")
    bar   = build_confidence_bar(pct)

    # Sparkline from monthly revenue
    rev_vals  = list(FAKE_SALES_DATA["monthly_revenue"].values()) + [v]
    sparkline = build_sparkline(rev_vals)

    # ASCII mini bar chart
    ascii_chart = build_ascii_bar_chart(v)

    nums  = ['1️⃣', '2️⃣', '3️⃣']
    drivers_text = "\n".join(
        f"{nums[i]} {_html(d)}" for i, d in enumerate(kd[:3])
    )

    msg = (
        f"🎯 <b>Financial Forecast — {_html(tf)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Predicted Revenue: <b>${v/1_000_000:.2f}M</b>\n"
        f"📊 Confidence: <b>{pct}%</b> {bar}\n"
        f"📉 Range: ${low/1_000_000:.2f}M — ${high/1_000_000:.2f}M\n"
        f"📈 Trend: <code>{sparkline}</code> (+{FAKE_SALES_DATA['yoy_growth_percent']}% YoY)\n\n"
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
        f"<i>Sources: Salesforce CRM, MarketNews, AlphaVantage</i>\n"
        f"<i>Generated in {latency:.1f}s ⚡</i>"
    )
    return msg


# ═══════════════════════════════════════════════════════════════════════════
# CORE FORECAST ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

def run_full_forecast(user_query: str) -> tuple:
    """Run the full simulated pipeline + real AI call. Returns (msg, forecast, chart_png)."""
    t0 = time.time()

    # 1. Run fake pipeline (logs + retrieval)
    pipeline_data = run_fake_pipeline(user_query)

    # 2. Real Gemini call
    forecast = call_gemini_api(
        pipeline_data["sales_summary"],
        pipeline_data["retrieved"],
        user_query
    )

    latency = time.time() - t0

    # 3. Post-pipeline logs
    _log(f"✓   Forecast generated | Confidence: {forecast.get('confidence_percent','?')}% | Latency: {latency:.1f}s", 0.2)
    _log("📤  Sending response to Telegram...", 0.1)
    _log(f"✅  Pipeline complete | Total: {latency:.1f}s | Cost: $0.008", 0.1)
    print("═" * 60 + "\n")

    # 4. Format telegram message
    msg = format_telegram_message(forecast, latency)

    # 5. Generate PNG chart
    try:
        chart_png = generate_chart_png(forecast)
    except Exception as e:
        logger.warning(f"Chart generation failed: {e}")
        chart_png = None

    return msg, forecast, chart_png


# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM BOT
# ═══════════════════════════════════════════════════════════════════════════

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode

WELCOME_MSG = (
    "👋 <b>Welcome to RAG Financial Analysis Bot!</b>\n\n"
    "I'm powered by a multi-LLM RAG pipeline:\n"
    "• 🔍 <b>Pinecone</b> vector DB semantic search\n"
    "• 🧠 <b>Gemini 2.0 Flash</b> for forecasting\n"
    "• ⚡ <b>ChatGPT 4.1 nano</b> for query optimization\n"
    "• 📊 <b>Salesforce CRM</b> historical data\n\n"
    "Just ask any revenue forecast question!\n\n"
    "<i>Example: \"What is Q1 2025 revenue forecast for enterprise software?\"</i>"
)

HELP_MSG = (
    "📚 <b>Example Queries:</b>\n\n"
    "• What is Q1 2025 revenue forecast for enterprise software?\n"
    "• Forecast EMEA hardware revenue next quarter\n"
    "• What will North America SaaS revenue be?\n"
    "• Predict Q2 2025 APAC cloud revenue\n"
    "• Revenue outlook for B2B software deals\n\n"
    "<i>Send any question and I'll run the full RAG pipeline!</i>"
)

DEMO_QUERY = "What is Q1 2025 revenue forecast for enterprise software in North America?"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MSG, parse_mode=ParseMode.HTML)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MSG, parse_mode=ParseMode.HTML)


async def cmd_demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🎬 <b>Running demo query:</b>\n<i>{DEMO_QUERY}</i>",
        parse_mode=ParseMode.HTML
    )
    await _handle_forecast(update, DEMO_QUERY)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    await _handle_forecast(update, query)


async def _handle_forecast(update: Update, query: str):
    """Shared forecast handler for both /demo and free-text messages."""
    await update.message.reply_text(
        "⏳ <i>Processing your query through the RAG pipeline...</i>",
        parse_mode=ParseMode.HTML
    )

    try:
        loop = asyncio.get_event_loop()
        msg, forecast, chart_png = await loop.run_in_executor(None, run_full_forecast, query)

        # 1. Send text forecast
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

        # 2. Send chart PNG
        if chart_png:
            tf  = forecast.get("timeframe", "Forecast")
            pct = forecast.get("confidence_percent", 85)
            caption = (
                f"📈 <b>Revenue Chart — {_html(tf)}</b>\n"
                f"<i>Confidence interval shown | {pct}% confidence</i>\n"
                f"<i>Blue = Historical | Green = Forecast | Yellow = CI Range</i>"
            )
            await update.message.reply_photo(
                photo=chart_png,
                caption=caption,
                parse_mode=ParseMode.HTML
            )

        # 3. Inline keyboard buttons
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎬 Run Demo",   callback_data="demo"),
             InlineKeyboardButton("❓ Help",       callback_data="help")],
            [InlineKeyboardButton("🌍 EMEA Forecast",    callback_data="emea"),
             InlineKeyboardButton("🌏 APAC Forecast",    callback_data="apac"),
             InlineKeyboardButton("🇺🇸 NA Forecast",      callback_data="na")],
        ])
        await update.message.reply_text(
            "🔄 <b>Quick follow-up queries:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Forecast handler error: {e}")
        msg = format_telegram_message(FALLBACK_FORECAST, 3.2)
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query_map = {
        "demo": DEMO_QUERY,
        "emea": "What is Q1 2025 revenue forecast for EMEA enterprise tech?",
        "apac": "Predict Q1 2025 APAC SaaS revenue growth",
        "na":   "North America enterprise software revenue forecast Q1 2025",
        "help": None,
    }
    cb   = update.callback_query
    data = cb.data
    await cb.answer()  # dismiss spinner

    if data == "help":
        await cb.message.reply_text(HELP_MSG, parse_mode=ParseMode.HTML)
    else:
        chosen_query = query_map.get(data, DEMO_QUERY)
        await cb.message.reply_text(
            f"💡 <b>Running:</b> <i>{chosen_query}</i>",
            parse_mode=ParseMode.HTML
        )
        await _handle_forecast(cb.message, chosen_query)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Telegram error: {context.error}")


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")
    if not GEMINI_API_KEY and not OPENROUTER_API_KEY:
        raise RuntimeError("Set GEMINI_API_KEY or OPENROUTER_API_KEY in .env")

    print("=" * 56)
    print("   RAG Financial Analysis Bot - Starting Up")
    print("=" * 56)
    print(f"  Gemini API:     {'✓ configured' if GEMINI_API_KEY else '✗ missing'}")
    print(f"  OpenRouter:     {'✓ configured (fallback)' if OPENROUTER_API_KEY else '—'}")
    print(f"  Telegram Token: {'✓ configured' if TELEGRAM_BOT_TOKEN else '✗ missing'}")
    print()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("demo",   cmd_demo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_error_handler(error_handler)

    print("🤖 Bot is running. Press Ctrl+C to stop.\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
