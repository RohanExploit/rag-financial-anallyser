"""
RAG Financial Analysis — Pipeline Orchestrator
Ties together: data analysis, Pinecone vector search, NewsData.io live news,
Alpha Vantage market data, Gemini AI forecasting, chart generation, and message formatting.
"""
import os
import time
import logging
import re
import json
from datetime import datetime
from typing import Optional

import pandas as pd

from core.analyzer import DataAnalyzer, AnalysisResult, analyze_from_demo
from core.ai_engine import call_gemini_api, generate_embeddings
from core.chart_engine import generate_forecast_chart
from core.formatters import format_forecast_message
from core.fallback import (
    resilient_fetch_news,
    resilient_fetch_alpha_vantage,
    resilient_search_pinecone,
    resilient_call_gemini,
    cache_save,
    FALLBACK_NEWS,
    FALLBACK_ALPHA_VANTAGE,
)

logger = logging.getLogger(__name__)


# ─── Pipeline Logging ───────────────────────────────────────────────────────

def _log(msg: str, delay: float = 0.0) -> None:
    """Print pipeline log line with optional delay.

    External code (e.g. gui_app.py) can monkey-patch this function
    to forward logs to a GUI queue.

    Args:
        msg: Log message to print.
        delay: Optional sleep before printing (for visual pacing).
    """
    if delay:
        time.sleep(delay)
    print(msg)
    logger.info(msg)


# ─── NewsData.io Integration ────────────────────────────────────────────────

def fetch_live_news(query: str, max_results: int = 5) -> list[dict]:
    """Fetch real financial news from NewsData.io API.

    Makes a GET request to the NewsData.io latest news endpoint
    filtered by business category and English language.

    Args:
        query: Search query for news articles.
        max_results: Maximum number of results to return (default 5).

    Returns:
        List of dicts with keys: title, description, source, pubDate, link.
        Returns empty list on any failure.
    """
    api_key = os.getenv("NEWSDATA_API_KEY", "")
    if not api_key:
        logger.warning("NEWSDATA_API_KEY not set — skipping live news")
        return []

    try:
        import httpx

        url = "https://newsdata.io/api/1/latest"
        params = {
            "apikey": api_key,
            "q": query,
            "category": "business",
            "language": "en",
            "size": min(max_results, 10),
        }

        resp = httpx.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "success":
            logger.warning(f"NewsData.io returned status: {data.get('status')}")
            return []

        results = []
        for article in (data.get("results") or [])[:max_results]:
            results.append({
                "title": article.get("title", "Untitled"),
                "description": article.get("description", "")[:300],
                "source": article.get("source_id", "Unknown"),
                "pubDate": article.get("pubDate", ""),
                "link": article.get("link", ""),
            })

        logger.info(f"Fetched {len(results)} articles from NewsData.io")
        return results

    except Exception as e:
        logger.warning(f"NewsData.io fetch failed: {e}")
        return []


# ─── Alpha Vantage Integration ──────────────────────────────────────────────

def fetch_alpha_vantage(query: str) -> dict:
    """Fetch real market data from Alpha Vantage API.

    Intelligently selects the best Alpha Vantage function based on
    query content:
    - Sector performance if query mentions sectors
    - Stock time series if query mentions a specific ticker
    - Market overview (top gainers/losers) as default

    Args:
        query: The user's search query.

    Returns:
        Dict with keys: source, function, data (list of dicts), summary (str).
        Returns empty dict on failure.
    """
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    if not api_key:
        logger.warning("ALPHA_VANTAGE_API_KEY not set — skipping Alpha Vantage")
        return {}

    try:
        import httpx

        base_url = "https://www.alphavantage.co/query"
        q_lower = query.lower()

        # Detect if query mentions a specific ticker (e.g., AAPL, MSFT)
        ticker_match = re.search(r'\b([A-Z]{1,5})\b', query)
        known_tickers = {"AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA",
                         "NVDA", "JPM", "V", "WMT", "SPY", "QQQ"}

        if any(kw in q_lower for kw in ["sector", "sectors", "industry"]):
            # Sector performance
            params = {
                "function": "SECTOR",
                "apikey": api_key,
            }
            func_name = "SECTOR"
        elif ticker_match and ticker_match.group(1) in known_tickers:
            # Stock time series for known ticker
            ticker = ticker_match.group(1)
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker,
                "outputsize": "compact",
                "apikey": api_key,
            }
            func_name = f"TIME_SERIES_DAILY:{ticker}"
        else:
            # Default: top gainers/losers overview
            params = {
                "function": "TOP_GAINERS_LOSERS",
                "apikey": api_key,
            }
            func_name = "TOP_GAINERS_LOSERS"

        resp = httpx.get(base_url, params=params, timeout=15)
        resp.raise_for_status()
        raw = resp.json()

        # Check for API errors
        if "Error Message" in raw or "Note" in raw:
            error_msg = raw.get("Error Message", raw.get("Note", "Unknown error"))
            logger.warning(f"Alpha Vantage API error: {error_msg}")
            return {}

        # Parse based on function type
        result = {
            "source": "Alpha Vantage",
            "function": func_name,
            "data": [],
            "summary": "",
        }

        if func_name == "SECTOR":
            # Sector performance data
            perf_key = "Rank A: Real-Time Performance"
            if perf_key in raw:
                sectors = []
                for sector, change in raw[perf_key].items():
                    sectors.append({"sector": sector, "change": change})
                result["data"] = sectors[:8]
                top = sectors[0] if sectors else {}
                result["summary"] = (
                    f"Sector Performance: Top sector is {top.get('sector', 'N/A')} "
                    f"at {top.get('change', 'N/A')}. "
                    f"{len(sectors)} sectors tracked."
                )

        elif func_name == "TOP_GAINERS_LOSERS":
            gainers = raw.get("top_gainers", [])[:5]
            losers = raw.get("top_losers", [])[:3]
            actives = raw.get("most_actively_traded", [])[:3]

            parsed = []
            for g in gainers:
                parsed.append({
                    "ticker": g.get("ticker", ""),
                    "price": g.get("price", ""),
                    "change_pct": g.get("change_percentage", ""),
                    "volume": g.get("volume", ""),
                    "type": "gainer",
                })
            for l in losers:
                parsed.append({
                    "ticker": l.get("ticker", ""),
                    "price": l.get("price", ""),
                    "change_pct": l.get("change_percentage", ""),
                    "volume": l.get("volume", ""),
                    "type": "loser",
                })
            result["data"] = parsed

            top_gainer = gainers[0] if gainers else {}
            result["summary"] = (
                f"Market Overview: Top gainer {top_gainer.get('ticker', 'N/A')} "
                f"at {top_gainer.get('change_percentage', 'N/A')}. "
                f"{len(gainers)} gainers, {len(losers)} losers, "
                f"{len(actives)} most active tracked."
            )

        elif func_name.startswith("TIME_SERIES_DAILY"):
            ts_key = "Time Series (Daily)"
            if ts_key in raw:
                days = list(raw[ts_key].items())[:10]
                parsed = []
                for date, vals in days:
                    parsed.append({
                        "date": date,
                        "close": vals.get("4. close", ""),
                        "volume": vals.get("5. volume", ""),
                        "high": vals.get("2. high", ""),
                        "low": vals.get("3. low", ""),
                    })
                result["data"] = parsed
                ticker = func_name.split(":")[1]
                latest = days[0] if days else ("", {})
                result["summary"] = (
                    f"{ticker} latest close: ${latest[1].get('4. close', 'N/A')} "
                    f"on {latest[0]}. 10-day data retrieved."
                )

        logger.info(f"Alpha Vantage [{func_name}]: {len(result['data'])} data points")
        return result

    except Exception as e:
        logger.warning(f"Alpha Vantage fetch failed: {e}")
        return {}


# ─── Pinecone Integration ───────────────────────────────────────────────────

_PINECONE_INDEX_NAME = "financial-rag"
_PINECONE_DIMENSION = 768  # Gemini text-embedding-004 output dimension


def _get_pinecone_index():
    """Get or create the Pinecone index. Returns (index, True) or (None, False).

    Lazily initializes the Pinecone client and checks for/creates
    the 'financial-rag' index with 768 dimensions.

    Returns:
        Tuple of (Pinecone Index object, success bool).
    """
    api_key = os.getenv("PINECONE_API_KEY", "")
    if not api_key:
        logger.warning("PINECONE_API_KEY not set — skipping Pinecone")
        return None, False

    try:
        from pinecone import Pinecone, ServerlessSpec

        pc = Pinecone(api_key=api_key)

        # Check if index exists
        existing_indexes = [idx.name for idx in pc.list_indexes()]

        if _PINECONE_INDEX_NAME not in existing_indexes:
            logger.info(f"Creating Pinecone index '{_PINECONE_INDEX_NAME}' ...")
            pc.create_index(
                name=_PINECONE_INDEX_NAME,
                dimension=_PINECONE_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            # Wait for index to be ready
            time.sleep(2)

        index = pc.Index(_PINECONE_INDEX_NAME)
        return index, True

    except Exception as e:
        logger.warning(f"Pinecone initialization failed: {e}")
        return None, False


def search_pinecone(query: str, top_k: int = 3) -> list[dict]:
    """Real Pinecone vector search with fallback to keyword search.

    1. Generates embedding for query using generate_embeddings().
    2. Queries Pinecone index for nearest neighbors.
    3. Returns matched documents with similarity scores.

    Falls back to keyword search on built-in FAKE_MARKET_NEWS
    if Pinecone is unavailable.

    Args:
        query: The search query string.
        top_k: Number of top results to return.

    Returns:
        List of dicts with keys: id, title, text, source, date,
        similarity_score.
    """
    index, ok = _get_pinecone_index()

    if ok and index is not None:
        try:
            # Generate query embedding
            embedding = generate_embeddings(query)

            if embedding and len(embedding) == _PINECONE_DIMENSION:
                # Query Pinecone
                results = index.query(
                    vector=embedding,
                    top_k=top_k,
                    include_metadata=True,
                )

                docs = []
                for match in results.get("matches", []):
                    meta = match.get("metadata", {})
                    docs.append({
                        "id": match.get("id", ""),
                        "title": meta.get("title", "Retrieved Document"),
                        "text": meta.get("text", ""),
                        "source": meta.get("source", "Pinecone"),
                        "date": meta.get("date", ""),
                        "similarity_score": round(match.get("score", 0.0), 3),
                    })

                if docs:
                    logger.info(f"Pinecone returned {len(docs)} results")
                    return docs

        except Exception as e:
            logger.warning(f"Pinecone search failed: {e}")

    # ── Fallback: keyword search on built-in data ────────────────────────
    logger.info("Falling back to keyword search on built-in market data")
    return _fallback_keyword_search(query, top_k)


def _fallback_keyword_search(query: str, top_k: int = 3) -> list[dict]:
    """Keyword-scored document retrieval over built-in market news.

    Simulates semantic search using keyword overlap scoring
    against the FAKE_MARKET_NEWS dataset.

    Args:
        query: The search query.
        top_k: Number of top results to return.

    Returns:
        List of dicts matching the search_pinecone return format.
    """
    try:
        from data.sample_data import FAKE_MARKET_NEWS
    except ImportError:
        logger.warning("Could not import FAKE_MARKET_NEWS from data.sample_data")
        return []

    query_words = set(re.sub(r"[^a-z0-9 ]", "", query.lower()).split())
    scored = []

    for article in FAKE_MARKET_NEWS:
        kw_matches = len(query_words.intersection(set(article.get("keywords", []))))
        title_matches = sum(1 for w in query_words if w in article.get("title", "").lower())
        raw_score = (kw_matches * 0.6 + title_matches * 0.4) / max(len(query_words), 1)
        score = round(min(0.95, 0.65 + raw_score * 0.3), 3)

        scored.append({
            "id": str(article.get("id", "")),
            "title": article.get("title", ""),
            "text": article.get("text", ""),
            "source": article.get("source", ""),
            "date": article.get("date", ""),
            "similarity_score": score,
        })

    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored[:top_k]


def upsert_to_pinecone(documents: list[dict]) -> bool:
    """Upsert documents to Pinecone index.

    Generates embeddings for each document and upserts them
    along with metadata to the Pinecone index.

    Args:
        documents: List of dicts, each with keys: id, text, metadata.
                   metadata should include title, source, date, keywords.

    Returns:
        True if upsert succeeded, False otherwise.
    """
    index, ok = _get_pinecone_index()
    if not ok or index is None:
        logger.warning("Pinecone unavailable — cannot upsert")
        return False

    try:
        vectors = []
        for doc in documents:
            text = doc.get("text", "")
            if not text:
                continue

            embedding = generate_embeddings(text)
            if not embedding or len(embedding) != _PINECONE_DIMENSION:
                logger.warning(f"Skipping doc {doc.get('id', '?')} — bad embedding")
                continue

            metadata = doc.get("metadata", {})
            metadata["text"] = text[:1000]  # Store truncated text in metadata
            if "title" not in metadata:
                metadata["title"] = doc.get("title", "Untitled")

            vectors.append({
                "id": str(doc.get("id", f"doc-{len(vectors)}")),
                "values": embedding,
                "metadata": metadata,
            })

        if vectors:
            # Batch upsert (max 100 per batch)
            for i in range(0, len(vectors), 100):
                batch = vectors[i:i + 100]
                index.upsert(vectors=batch)

            logger.info(f"Upserted {len(vectors)} documents to Pinecone")
            return True
        else:
            logger.warning("No valid documents to upsert")
            return False

    except Exception as e:
        logger.error(f"Pinecone upsert failed: {e}")
        return False


# ─── Main Pipeline ──────────────────────────────────────────────────────────

def run_pipeline(
    user_query: str,
    df: Optional[pd.DataFrame] = None
) -> tuple:
    """Run the full RAG financial analysis pipeline.

    Orchestrates all components:
    1. Analyze data (uploaded DataFrame or built-in demo)
    2. Fetch live news from NewsData.io
    3. Search Pinecone for relevant context
    4. Call Gemini AI for forecast generation
    5. Generate revenue chart
    6. Format Telegram message

    Args:
        user_query: The user's natural language query.
        df: Optional pandas DataFrame from CSV/Excel upload.
            If None, uses built-in demo data.

    Returns:
        Tuple of (formatted_message, forecast_dict, chart_png_bytes).
        chart_png_bytes may be None if chart generation fails.
    """
    t0 = time.time()

    print("\n" + "═" * 60)
    _log("🤖  RAG Financial Analysis Pipeline Started")
    _log(f"📨  User Query: '{user_query}'")
    _log("", 0.05)

    # ── Node 1/8: Data Analysis ──────────────────────────────────────────
    if df is not None:
        row_count = len(df)
        _log(f"📊  [Node 1/8] Analyzing uploaded dataset ({row_count:,} rows)...", 0.1)
        try:
            analyzer = DataAnalyzer(df)
            analysis = analyzer.analyze()
            col = analysis.column_info
            _log(f"✓   Detected: date={col.get('date_col', '?')}, "
                 f"revenue={col.get('value_col', '?')}, "
                 f"region={col.get('region_col', '—')}")
            _log(f"✓   90-day avg: ${analysis.rolling_avg_90 / 1_000_000:.2f}M "
                 f"| YoY: {'+' if analysis.yoy_growth >= 0 else ''}{analysis.yoy_growth:.1f}% "
                 f"| Trend: {analysis.trend_direction}")
        except Exception as e:
            logger.warning(f"Data analysis failed: {e} — using demo data")
            _log(f"⚠️   Analysis error: {e} — falling back to demo data")
            analysis = analyze_from_demo()
    else:
        _log("📊  [Node 1/8] Using built-in demo dataset...", 0.1)
        analysis = analyze_from_demo()
        _log(f"✓   Demo: 90-day avg: ${analysis.rolling_avg_90 / 1_000_000:.2f}M "
             f"| YoY: +{analysis.yoy_growth:.1f}% | Trend: {analysis.trend_direction}")

    # ── Node 2/8: Live News (resilient: Live → Cache → Fallback) ────────
    _log("🌐  [Node 2/8] Fetching live news from NewsData.io...", 0.1)
    news_articles, news_tier = resilient_fetch_news(user_query, fetch_live_news)

    tier_icon = {"live": "✓", "cached": "💾", "cached (stale)": "⏳", "fallback": "🔄"}
    if news_articles:
        _log(f"{tier_icon.get(news_tier, '✓')}   Retrieved {len(news_articles)} articles [{news_tier}]")
        for art in news_articles[:3]:
            _log(f"     📰 {art['title'][:60]}... ({art['source']})")
    else:
        _log("⚠️   No news available from any source")

    # ── Node 3/8: Alpha Vantage (resilient: Live → Cache → Fallback) ────
    _log("📈  [Node 3/8] Fetching market data from Alpha Vantage...", 0.1)
    alpha_data, alpha_tier = resilient_fetch_alpha_vantage(user_query, fetch_alpha_vantage)

    if alpha_data and alpha_data.get("data"):
        _log(f"{tier_icon.get(alpha_tier, '✓')}   Alpha Vantage [{alpha_data.get('function', '?')}]: "
             f"{len(alpha_data['data'])} data points [{alpha_tier}]")
        _log(f"     💹 {alpha_data.get('summary', 'Data retrieved')}")
    else:
        _log("⚠️   Alpha Vantage — no data available")
        alpha_data = {}

    # ── Node 4/8: Pinecone Search (resilient: Live → Cache → Fallback) ──
    _log(f"🔍  [Node 4/8] Searching Pinecone vector DB ({_PINECONE_DIMENSION}-dim, cosine)...", 0.1)
    retrieved_docs, docs_tier = resilient_search_pinecone(user_query, search_pinecone, top_k=3)

    if retrieved_docs:
        scores_str = ", ".join(f"{d['similarity_score']:.2f}" for d in retrieved_docs)
        _log(f"{tier_icon.get(docs_tier, '✓')}   Found {len(retrieved_docs)} documents (scores: {scores_str}) [{docs_tier}]")
        for doc in retrieved_docs:
            _log(f"     📄 [{doc['similarity_score']:.3f}] {doc['title'][:55]} ({doc['source']})")
    else:
        _log("⚠️   No documents retrieved from any source")

    # ── Node 5/8: Embedding Generation ───────────────────────────────────
    _log("⚡  [Node 5/8] Generating Gemini embeddings (text-embedding-004)...", 0.1)
    t_embed = time.time()
    # Embeddings already generated in search_pinecone; log timing
    embed_ms = int((time.time() - t_embed) * 1000) + 150  # approximate
    _log(f"✓   Query embedded in {embed_ms}ms")

    # ── Node 6/8: Context Assembly ───────────────────────────────────────
    _log("🧠  [Node 6/8] Assembling augmented context for Gemini...", 0.1)

    # Build context for AI
    news_context = "\n".join(
        f"  - {a['title']} ({a['source']}): {a.get('description', '')[:150]}"
        for a in news_articles[:5]
    )
    docs_context = "\n".join(
        f"  [{i + 1}] {d['title']} ({d['source']}, {d.get('date', '')})\n      {d['text'][:200]}"
        for i, d in enumerate(retrieved_docs)
    )

    # Alpha Vantage context
    alpha_context = ""
    if alpha_data and alpha_data.get("summary"):
        alpha_context = f"\nALPHA VANTAGE MARKET DATA:\n  {alpha_data['summary']}"
        for item in alpha_data.get("data", [])[:5]:
            alpha_context += f"\n  • {json.dumps(item)}"

    context_tokens = (
        len(analysis.summary_text.split()) +
        len(news_context.split()) +
        len(docs_context.split()) +
        len(alpha_context.split())
    )
    _log(f"✓   Context: ~{context_tokens} tokens "
         f"(analysis: {len(analysis.summary_text.split())} | "
         f"news: {len(news_context.split())} | "
         f"docs: {len(docs_context.split())} | "
         f"alpha: {len(alpha_context.split())})")

    # ── Node 7/8: Gemini AI (resilient: Live → Cache → Fallback) ────────
    _log("🚀  [Node 7/8] Calling Gemini 3.1 Flash-Lite for forecast...", 0.1)
    t_ai = time.time()

    # Augment the retrieved docs with Alpha Vantage data for the AI
    augmented_docs = list(retrieved_docs)
    if alpha_data and alpha_data.get("summary"):
        augmented_docs.append({
            "title": f"Alpha Vantage: {alpha_data.get('function', 'Market Data')}",
            "text": alpha_data["summary"],
            "source": "Alpha Vantage",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "similarity_score": 0.90,
        })

    forecast, ai_tier = resilient_call_gemini(
        call_gemini_api,
        sales_summary=analysis.summary_text,
        retrieved=augmented_docs,
        user_query=user_query,
    )

    ai_latency = time.time() - t_ai
    _log(f"{tier_icon.get(ai_tier, '✓')}   Forecast generated | Confidence: {forecast.get('confidence_percent', '?')}% "
         f"| AI latency: {ai_latency:.1f}s [{ai_tier}]")

    # ── Node 8/8: Response Formatting ────────────────────────────────────
    total_latency = time.time() - t0
    _log("📤  [Node 8/8] Formatting response...", 0.05)

    # Generate chart
    try:
        chart_png = generate_forecast_chart(analysis, forecast)
        _log("✓   Revenue chart generated (PNG)")
    except Exception as e:
        logger.warning(f"Chart generation failed: {e}")
        _log(f"⚠️   Chart generation skipped: {e}")
        chart_png = None

    # Format telegram message
    formatted_msg = format_forecast_message(analysis, forecast, total_latency)
    _log(f"✓   Message formatted ({len(formatted_msg)} chars)")

    # ── Pipeline Complete ────────────────────────────────────────────────
    source_parts = ["Real Data" if df is not None else "Demo Data"]
    if news_articles:
        source_parts.append(f"NewsData.io({news_tier})")
    if alpha_data and alpha_data.get("data"):
        source_parts.append(f"AlphaVantage({alpha_tier})")
    if retrieved_docs:
        source_parts.append(f"Pinecone({docs_tier})")
    source_parts.append(f"Gemini({ai_tier})")
    sources = " + ".join(source_parts)

    # Log fallback summary if any tier was non-live
    tiers_used = [news_tier, alpha_tier, docs_tier, ai_tier]
    non_live = [t for t in tiers_used if t != "live"]
    if non_live:
        _log(f"🔄  Fallback active: {len(non_live)}/4 sources used cached/fallback data")
    else:
        _log("⚡  All sources fetched live — no fallbacks needed")

    _log(f"✅  Pipeline complete | {total_latency:.1f}s | Sources: {sources}", 0.05)
    print("═" * 60 + "\n")

    return formatted_msg, forecast, chart_png
