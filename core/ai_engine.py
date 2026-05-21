"""
RAG Financial Analysis — AI Engine

Gemini 3.1 Flash-Lite for forecasting + text-embedding-004 for embeddings.
Falls back to OpenRouter, then hardcoded fallback.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional, Union

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT — tells the LLM to use REAL analysis data
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a senior financial analyst AI specializing in B2B revenue forecasting.

You will receive:
1. REAL statistical analysis computed from the user's uploaded data
2. Retrieved market intelligence (from Pinecone vector DB and live news)
3. A user query

Your task: Generate a precise, data-driven revenue forecast.

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


# ═══════════════════════════════════════════════════════════════════════════
# JSON PARSING
# ═══════════════════════════════════════════════════════════════════════════

def _parse_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON from LLM response.

    Handles responses wrapped in ```json ... ``` or plain JSON.

    Args:
        raw: Raw LLM output string.

    Returns:
        Parsed dict.

    Raises:
        json.JSONDecodeError: If parsing fails after cleanup.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    return json.loads(cleaned)


# ═══════════════════════════════════════════════════════════════════════════
# EMBEDDINGS — Gemini text-embedding-004 (768-dim, free)
# ═══════════════════════════════════════════════════════════════════════════

def generate_embeddings(text: Union[str, list[str]]) -> Optional[list[float]]:
    """Generate real embeddings using Gemini text-embedding-004 model.

    Args:
        text: A single string or list of strings to embed.
              If a single string, returns a single 768-dim vector.

    Returns:
        A 768-dim float vector for a single input,
        or None on failure.
    """
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set — cannot generate embeddings")
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        content = text if isinstance(text, str) else text[0] if text else ""
        if not content:
            return None

        result = genai.embed_content(
            model="models/text-embedding-004",
            content=content,
            task_type="retrieval_document",
        )

        embedding = result.get("embedding")
        if embedding and isinstance(embedding, list):
            logger.info("Generated embedding (%d dims)", len(embedding))
            return embedding

        return None

    except Exception as e:
        logger.warning("Embedding generation failed: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# FORECAST — Gemini → OpenRouter → Fallback
# ═══════════════════════════════════════════════════════════════════════════

def call_gemini_api(
    sales_summary: str,
    retrieved: list[dict],
    user_query: str,
) -> dict:
    """Call Gemini 3.1 Flash-Lite with real analysis data.

    Falls back to OpenRouter, then to hardcoded FALLBACK_FORECAST.

    Args:
        sales_summary: Human-readable analysis summary text.
        retrieved: List of retrieved docs from Pinecone/keyword search.
        user_query: The user's original query.

    Returns:
        Forecast dict with keys: forecast_value, confidence_percent,
        range_low, range_high, timeframe, key_drivers, reasoning,
        market_signal, risk.
    """
    docs_text = "\n\n".join(
        f"[{i + 1}] {d.get('title', '')} ({d.get('source', '')}, "
        f"{d.get('date', '')})\n{d.get('text', '')}"
        for i, d in enumerate(retrieved)
    )
    user_prompt = (
        f"HISTORICAL SALES DATA:\n{sales_summary}\n\n"
        f"RETRIEVED MARKET INTELLIGENCE (from Pinecone vector DB):\n{docs_text}\n\n"
        f"USER QUERY: {user_query}\n\n"
        "Generate forecast JSON now."
    )

    # ── Try Gemini first ────────────────────────────────────────────────
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    if api_key:
        result = _call_gemini_direct(api_key, user_prompt)
        if result:
            return result

    # ── OpenRouter fallback ─────────────────────────────────────────────
    or_key = OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY", "")
    if or_key:
        result = _call_openrouter(or_key, user_prompt)
        if result:
            return result

    # ── Hard fallback ───────────────────────────────────────────────────
    logger.warning("All AI calls failed — using hardcoded fallback forecast")
    from data.sample_data import FALLBACK_FORECAST
    return FALLBACK_FORECAST.copy()


def _call_gemini_direct(api_key: str, user_prompt: str) -> Optional[dict]:
    """Direct Gemini API call via google-generativeai SDK."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-lite",
            system_instruction=SYSTEM_PROMPT,
        )
        resp = model.generate_content(user_prompt)
        raw = resp.text.strip()
        result = _parse_json(raw)
        logger.info("Gemini API call succeeded")
        return result

    except json.JSONDecodeError:
        logger.warning("Gemini returned invalid JSON — trying parse retry")
        try:
            return _parse_json(resp.text)
        except Exception:
            logger.error("Gemini JSON parse failed after retry")
            return None
    except Exception as e:
        logger.warning("Gemini API error: %s", e)
        return None


def _call_openrouter(api_key: str, user_prompt: str) -> Optional[dict]:
    """OpenRouter fallback API call."""
    try:
        import httpx

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://rag-financial-demo.local",
                "X-Title": "RAG Financial Demo",
            },
            json={
                "model": "google/gemini-2.0-flash-lite-001",
                "messages": messages,
                "max_tokens": 600,
                "temperature": 0.4,
            },
            timeout=30,
        )
        data = resp.json()
        raw = data["choices"][0]["message"]["content"].strip()
        result = _parse_json(raw)
        logger.info("OpenRouter fallback succeeded")
        return result

    except Exception as e:
        logger.error("OpenRouter fallback failed: %s", e)
        return None
