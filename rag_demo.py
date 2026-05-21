"""
RAG Financial Analysis — Telegram Bot

Slim handler-only entry point. All business logic delegates to core/ modules.
Supports: text queries, CSV/Excel file uploads, PDF report export, inline buttons.
"""
import sys
import io
import os
import logging
import tempfile
from datetime import datetime

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import asyncio
import pandas as pd
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)
from telegram.constants import ParseMode

from core.pipeline import run_pipeline
from core.formatters import format_upload_confirmation, _html
from core.analyzer import DataAnalyzer
from core.pdf_report import generate_pdf_report

load_dotenv()

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

DEMO_QUERY = "What is Q1 2025 revenue forecast for enterprise software in North America?"


# ═══════════════════════════════════════════════════════════════════════════
# MESSAGES
# ═══════════════════════════════════════════════════════════════════════════

WELCOME_MSG = (
    "👋 <b>Welcome to RAG Financial Analysis Bot!</b>\n\n"
    "I analyze real financial data using AI:\n"
    "• 📂 <b>Upload CSV/Excel</b> — I'll analyze your data\n"
    "• 🔍 <b>Pinecone</b> vector DB semantic search\n"
    "• 🧠 <b>Gemini AI</b> for smart forecasting\n"
    "• 📰 <b>NewsData.io</b> live market news\n"
    "• 📊 <b>Charts + PDF Reports</b>\n\n"
    "Just ask any revenue forecast question!\n\n"
    "<i>💡 Send a CSV/Excel file first, then ask questions about it.\n"
    "Or type /demo for a sample forecast.</i>"
)

HELP_MSG = (
    "📚 <b>Commands:</b>\n\n"
    "• /start — Welcome message\n"
    "• /demo — Run sample forecast with demo data\n"
    "• /report — Generate PDF report of last forecast\n"
    "• /help — This help message\n\n"
    "📂 <b>File Upload:</b>\n"
    "Send any .csv or .xlsx file and I'll auto-analyze it!\n\n"
    "📊 <b>Example Queries:</b>\n"
    "• What is Q1 2025 revenue forecast for enterprise software?\n"
    "• Forecast EMEA hardware revenue next quarter\n"
    "• Predict Q2 2025 APAC cloud revenue\n\n"
    "<i>Upload data first for real analysis, or ask directly for demo-based forecasts!</i>"
)


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(WELCOME_MSG, parse_mode=ParseMode.HTML)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await update.message.reply_text(HELP_MSG, parse_mode=ParseMode.HTML)


async def cmd_demo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /demo command — run forecast with built-in demo data."""
    await update.message.reply_text(
        f"🎬 <b>Running demo query:</b>\n<i>{DEMO_QUERY}</i>",
        parse_mode=ParseMode.HTML,
    )
    await _handle_forecast(update, context, DEMO_QUERY, df=None)


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /report command — generate PDF of last forecast."""
    last = context.user_data.get("last_forecast")
    last_analysis = context.user_data.get("last_analysis")
    last_chart = context.user_data.get("last_chart")
    last_query = context.user_data.get("last_query", "")

    if not last or not last_analysis:
        await update.message.reply_text(
            "⚠️ No forecast available yet. Run a forecast first, then use /report.",
            parse_mode=ParseMode.HTML,
        )
        return

    await update.message.reply_text(
        "📄 <i>Generating PDF executive report...</i>",
        parse_mode=ParseMode.HTML,
    )

    try:
        loop = asyncio.get_event_loop()
        pdf_bytes = await loop.run_in_executor(
            None, generate_pdf_report, last_analysis, last, last_chart, last_query,
        )

        if pdf_bytes:
            filename = f"forecast_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            await update.message.reply_document(
                document=pdf_bytes,
                filename=filename,
                caption="📄 <b>Executive Forecast Report</b>\n<i>Generated by RAG Financial Analysis System</i>",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text("❌ PDF generation failed. Try again.")
    except Exception as e:
        logger.error("Report generation error: %s", e)
        await update.message.reply_text(f"❌ Report error: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# FILE UPLOAD HANDLER
# ═══════════════════════════════════════════════════════════════════════════

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle CSV/Excel file uploads."""
    doc = update.message.document
    filename = doc.file_name or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ("csv", "xlsx", "xls"):
        await update.message.reply_text(
            "⚠️ Please upload a <b>.csv</b> or <b>.xlsx</b> file.",
            parse_mode=ParseMode.HTML,
        )
        return

    await update.message.reply_text(
        f"📂 <i>Downloading and analyzing {_html(filename)}...</i>",
        parse_mode=ParseMode.HTML,
    )

    try:
        tg_file = await doc.get_file()

        # Download to temp file
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp_path = tmp.name
            await tg_file.download_to_drive(tmp_path)

        # Parse with pandas
        if ext == "csv":
            df = pd.read_csv(tmp_path)
        else:
            df = pd.read_excel(tmp_path)

        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

        if df.empty:
            await update.message.reply_text("⚠️ The uploaded file is empty.")
            return

        # Analyze
        analyzer = DataAnalyzer(df)
        analysis = analyzer.analyze()

        # Store in user session
        context.user_data["uploaded_df"] = df
        context.user_data["uploaded_analysis"] = analysis
        context.user_data["uploaded_filename"] = filename

        # Send confirmation
        confirm_msg = format_upload_confirmation(analysis)
        await update.message.reply_text(confirm_msg, parse_mode=ParseMode.HTML)

        # Inline keyboard for quick actions
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Run Forecast", callback_data="forecast_uploaded"),
             InlineKeyboardButton("📄 Generate Report", callback_data="report")],
        ])
        await update.message.reply_text(
            "💡 <b>What next?</b> Ask a question about your data, or:",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error("File upload error: %s", e)
        await update.message.reply_text(
            f"❌ Error processing file: {_html(str(e))}",
            parse_mode=ParseMode.HTML,
        )


# ═══════════════════════════════════════════════════════════════════════════
# MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-text messages as forecast queries."""
    query = update.message.text.strip()
    df = context.user_data.get("uploaded_df")
    await _handle_forecast(update, context, query, df)


# ═══════════════════════════════════════════════════════════════════════════
# CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses."""
    cb = update.callback_query
    data = cb.data
    await cb.answer()

    query_map = {
        "demo": DEMO_QUERY,
        "emea": "What is Q1 2025 revenue forecast for EMEA enterprise tech?",
        "apac": "Predict Q1 2025 APAC SaaS revenue growth",
        "na": "North America enterprise software revenue forecast Q1 2025",
        "forecast_uploaded": "Forecast revenue for next quarter based on uploaded data",
    }

    if data == "help":
        await cb.message.reply_text(HELP_MSG, parse_mode=ParseMode.HTML)
    elif data == "report":
        # Simulate a /report command
        update_proxy = type("U", (), {"message": cb.message})()
        await cmd_report(update_proxy, context)
    else:
        chosen_query = query_map.get(data, DEMO_QUERY)
        df = context.user_data.get("uploaded_df") if data == "forecast_uploaded" else None
        await cb.message.reply_text(
            f"💡 <b>Running:</b> <i>{chosen_query}</i>",
            parse_mode=ParseMode.HTML,
        )
        # Create a wrapper that mimics update structure for _handle_forecast
        await _handle_forecast_from_callback(cb.message, context, chosen_query, df)


# ═══════════════════════════════════════════════════════════════════════════
# SHARED FORECAST LOGIC
# ═══════════════════════════════════════════════════════════════════════════

async def _handle_forecast(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query: str,
    df=None,
) -> None:
    """Shared forecast handler for commands and free-text messages."""
    msg = update.message
    await msg.reply_text(
        "⏳ <i>Processing your query through the RAG pipeline...</i>",
        parse_mode=ParseMode.HTML,
    )

    try:
        loop = asyncio.get_event_loop()
        formatted_msg, forecast, chart_png = await loop.run_in_executor(
            None, run_pipeline, query, df,
        )

        # Store for /report command
        from core.analyzer import analyze_from_demo, DataAnalyzer
        if df is not None:
            analysis = DataAnalyzer(df).analyze()
        else:
            analysis = analyze_from_demo()

        context.user_data["last_forecast"] = forecast
        context.user_data["last_analysis"] = analysis
        context.user_data["last_chart"] = chart_png
        context.user_data["last_query"] = query

        # Send text forecast
        await msg.reply_text(formatted_msg, parse_mode=ParseMode.HTML)

        # Send chart PNG
        if chart_png:
            tf = forecast.get("timeframe", "Forecast")
            pct = forecast.get("confidence_percent", 85)
            caption = (
                f"📈 <b>Revenue Chart — {_html(tf)}</b>\n"
                f"<i>Confidence interval shown | {pct}% confidence</i>\n"
                f"<i>Blue = Historical | Green = Forecast | Yellow = CI Range</i>"
            )
            await msg.reply_photo(
                photo=chart_png, caption=caption, parse_mode=ParseMode.HTML,
            )

        # Inline keyboard buttons
        has_data = df is not None
        buttons = [
            [InlineKeyboardButton("🎬 Run Demo", callback_data="demo"),
             InlineKeyboardButton("❓ Help", callback_data="help")],
            [InlineKeyboardButton("🌍 EMEA", callback_data="emea"),
             InlineKeyboardButton("🌏 APAC", callback_data="apac"),
             InlineKeyboardButton("🇺🇸 NA", callback_data="na")],
            [InlineKeyboardButton("📄 PDF Report", callback_data="report")],
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        await msg.reply_text(
            "🔄 <b>Quick actions:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error("Forecast handler error: %s", e)
        from data.sample_data import FALLBACK_FORECAST
        from core.formatters import format_forecast_message
        from core.analyzer import analyze_from_demo
        analysis = analyze_from_demo()
        fallback_msg = format_forecast_message(analysis, FALLBACK_FORECAST, 3.2)
        await msg.reply_text(fallback_msg, parse_mode=ParseMode.HTML)


async def _handle_forecast_from_callback(message, context, query, df=None):
    """Handle forecast from callback query (inline button press)."""
    await message.reply_text(
        "⏳ <i>Processing your query through the RAG pipeline...</i>",
        parse_mode=ParseMode.HTML,
    )

    try:
        loop = asyncio.get_event_loop()
        formatted_msg, forecast, chart_png = await loop.run_in_executor(
            None, run_pipeline, query, df,
        )

        from core.analyzer import analyze_from_demo, DataAnalyzer
        if df is not None:
            analysis = DataAnalyzer(df).analyze()
        else:
            analysis = analyze_from_demo()

        context.user_data["last_forecast"] = forecast
        context.user_data["last_analysis"] = analysis
        context.user_data["last_chart"] = chart_png
        context.user_data["last_query"] = query

        await message.reply_text(formatted_msg, parse_mode=ParseMode.HTML)

        if chart_png:
            tf = forecast.get("timeframe", "Forecast")
            pct = forecast.get("confidence_percent", 85)
            caption = (
                f"📈 <b>Revenue Chart — {_html(tf)}</b>\n"
                f"<i>{pct}% confidence</i>"
            )
            await message.reply_photo(
                photo=chart_png, caption=caption, parse_mode=ParseMode.HTML,
            )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 PDF Report", callback_data="report"),
             InlineKeyboardButton("❓ Help", callback_data="help")],
        ])
        await message.reply_text(
            "🔄 <b>Quick actions:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error("Callback forecast error: %s", e)
        await message.reply_text(f"❌ Forecast error: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle uncaught errors."""
    logger.error("Telegram error: %s", context.error)


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Start the Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")
    if not GEMINI_API_KEY and not OPENROUTER_API_KEY:
        raise RuntimeError("Set GEMINI_API_KEY or OPENROUTER_API_KEY in .env")

    print("=" * 56)
    print("   RAG Financial Analysis Bot — Starting Up")
    print("=" * 56)
    print(f"  Gemini API:     {'✓ configured' if GEMINI_API_KEY else '✗ missing'}")
    print(f"  OpenRouter:     {'✓ configured (fallback)' if OPENROUTER_API_KEY else '—'}")
    print(f"  Pinecone:       {'✓ configured' if os.getenv('PINECONE_API_KEY') else '—'}")
    print(f"  NewsData.io:    {'✓ configured' if os.getenv('NEWSDATA_API_KEY') else '—'}")
    print(f"  Telegram Token: {'✓ configured' if TELEGRAM_BOT_TOKEN else '✗ missing'}")
    print()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("demo", cmd_demo))
    app.add_handler(CommandHandler("report", cmd_report))

    # File upload handler (CSV/Excel)
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Free-text message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Inline button callback handler
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.add_error_handler(error_handler)

    print("🤖 Bot is running. Press Ctrl+C to stop.\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
