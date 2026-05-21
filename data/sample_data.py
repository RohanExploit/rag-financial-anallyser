"""
Sample data constants for RAG Financial Analysis System.

Provides demo datasets, market news fixtures, and fallback forecast
values that core modules can import without circular dependencies.
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════════════
# DEMO SALES DATA — used by DataAnalyzer.analyze_from_demo()
# ═══════════════════════════════════════════════════════════════════════════

DEMO_SALES_DATA: dict = {
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
    "units_sold": {
        "2024-10": 22,
        "2024-11": 24,
        "2024-12": 27,
        "2025-01": 28,
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# MARKET NEWS FIXTURES — used by fake Pinecone search and RAG context
# ═══════════════════════════════════════════════════════════════════════════

FAKE_MARKET_NEWS: list[dict] = [
    {
        "id": 1,
        "title": "Tech Sector Poised for Q1 2025 Growth Surge",
        "text": (
            "Enterprise software spending up 18% YoY. Major corporations "
            "expanding cloud infrastructure budgets by an average of $2.4M "
            "per company."
        ),
        "source": "TechCrunch",
        "date": "2025-01-15",
        "keywords": [
            "tech", "software", "growth", "enterprise", "q1", "2025", "cloud",
        ],
    },
    {
        "id": 2,
        "title": "North America IT Budget Increases Signal Market Optimism",
        "text": (
            "Fortune 500 companies allocating 15% more to digital "
            "transformation. SaaS spending projected to reach $197B globally."
        ),
        "source": "Forbes",
        "date": "2025-01-14",
        "keywords": [
            "north", "america", "budget", "it", "saas", "digital", "fortune",
        ],
    },
    {
        "id": 3,
        "title": "Enterprise Software Deals Hit Record in Late 2024",
        "text": (
            "Q4 2024 enterprise software deals totaled $8.2B across North "
            "America and EMEA. Average deal size increased 22%."
        ),
        "source": "Bloomberg",
        "date": "2025-01-12",
        "keywords": [
            "enterprise", "software", "deals", "q4", "record", "emea",
            "north", "america",
        ],
    },
    {
        "id": 4,
        "title": "Hardware Supply Chain Stabilizes After 2024 Disruptions",
        "text": (
            "Hardware procurement lead times dropped from 18 weeks to "
            "9 weeks. Prices expected to normalize in Q1 2025."
        ),
        "source": "Reuters",
        "date": "2025-01-10",
        "keywords": [
            "hardware", "supply", "chain", "procurement", "2025", "q1",
            "prices",
        ],
    },
    {
        "id": 5,
        "title": "SaaS Revenue Growth Accelerates Across APAC Region",
        "text": (
            "Asia-Pacific SaaS market growing at 24% CAGR. Cloud adoption "
            "in APAC enterprises reached 67% penetration."
        ),
        "source": "Gartner",
        "date": "2025-01-09",
        "keywords": [
            "saas", "apac", "cloud", "asia", "growth", "revenue", "pacific",
        ],
    },
    {
        "id": 6,
        "title": "Analyst Report: Financial Software Demand Climbing Steeply",
        "text": (
            "Financial analytics platforms seeing 31% demand increase. "
            "AI-powered forecasting tools leading the growth category."
        ),
        "source": "IDC",
        "date": "2025-01-08",
        "keywords": [
            "financial", "software", "analytics", "ai", "forecast", "demand",
            "revenue",
        ],
    },
    {
        "id": 7,
        "title": "EMEA Enterprise Tech Spending Up Despite Economic Headwinds",
        "text": (
            "European enterprises maintained 12% IT budget growth. Security "
            "and analytics categories outperformed."
        ),
        "source": "FT",
        "date": "2025-01-07",
        "keywords": [
            "emea", "europe", "enterprise", "tech", "spending", "budget",
            "analytics",
        ],
    },
    {
        "id": 8,
        "title": "Q1 2025 Revenue Forecasts Positive for B2B Software Vendors",
        "text": (
            "B2B software vendors expected to post 15-20% revenue growth in "
            "Q1 2025. Pipeline conversion rates up 8%."
        ),
        "source": "Wall Street Journal",
        "date": "2025-01-06",
        "keywords": [
            "q1", "2025", "revenue", "forecast", "b2b", "software", "vendor",
            "growth",
        ],
    },
    {
        "id": 9,
        "title": "AI Integration Drives Upsell Opportunities in Enterprise Accounts",
        "text": (
            "Companies that integrated AI into existing tools saw 28% higher "
            "upsell rates. Average contract value increased $45K."
        ),
        "source": "McKinsey",
        "date": "2025-01-05",
        "keywords": [
            "ai", "upsell", "enterprise", "contract", "integration",
            "revenue", "accounts",
        ],
    },
    {
        "id": 10,
        "title": "Global Economic Indicators Support Tech Sector Optimism for 2025",
        "text": (
            "GDP growth projections revised upward in US (+2.8%) and "
            "EU (+1.9%). Consumer and enterprise confidence indices both "
            "rising."
        ),
        "source": "IMF",
        "date": "2025-01-04",
        "keywords": [
            "economic", "gdp", "growth", "2025", "tech", "global", "us", "eu",
        ],
    },
    {
        "id": 11,
        "title": "Cloud Migration Deals Surge as On-Premise Licenses Expire",
        "text": (
            "Wave of on-premise license expirations driving $12B cloud "
            "migration market in 2025."
        ),
        "source": "Forrester",
        "date": "2025-01-03",
        "keywords": [
            "cloud", "migration", "license", "on-premise", "2025", "software",
        ],
    },
    {
        "id": 12,
        "title": "North America SaaS Sales Teams Outperforming Targets by 18%",
        "text": (
            "Top SaaS companies in North America closed Q4 2024 at 118% of "
            "quota. Deal velocity increased 22%."
        ),
        "source": "Salesforce Research",
        "date": "2024-12-30",
        "keywords": [
            "north", "america", "saas", "sales", "quota", "deal", "q4",
            "velocity",
        ],
    },
    {
        "id": 13,
        "title": "Hardware Refresh Cycle Creating New Demand Wave",
        "text": (
            "3-year hardware refresh cycle peaking in 2025. Corporate PC "
            "and server refresh projected at $45B market."
        ),
        "source": "IDC",
        "date": "2024-12-28",
        "keywords": [
            "hardware", "refresh", "demand", "corporate", "server", "pc",
            "2025",
        ],
    },
    {
        "id": 14,
        "title": "Financial Services Sector Increases Tech Budget to $120B",
        "text": (
            "Financial services firms allocate record budgets to RegTech, "
            "AI risk tools, and analytics platforms."
        ),
        "source": "Deloitte",
        "date": "2024-12-27",
        "keywords": [
            "financial", "services", "budget", "regtech", "analytics", "ai",
            "tech",
        ],
    },
    {
        "id": 15,
        "title": "Interest Rate Cuts Boost Corporate IT Investment Confidence",
        "text": (
            "Federal Reserve rate cuts freeing up capital for tech "
            "investment. Corporate capex budgets expanding in Q1 2025."
        ),
        "source": "CNBC",
        "date": "2024-12-26",
        "keywords": [
            "interest", "rate", "investment", "corporate", "capex", "2025",
            "q1", "tech",
        ],
    },
]

# ═══════════════════════════════════════════════════════════════════════════
# FALLBACK FORECAST — returned when all LLM API calls fail
# ═══════════════════════════════════════════════════════════════════════════

FALLBACK_FORECAST: dict = {
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
        "Based on 90-day historical trend ($4.28M avg) and accelerating "
        "growth velocity (+6.7% QoQ), Q1 2025 forecast projects $4.8M "
        "with high confidence."
    ),
    "market_signal": (
        "B2B software vendors expected to post 15-20% revenue growth "
        "in Q1 2025"
    ),
    "risk": "Macro economic slowdown could compress enterprise budgets",
}
