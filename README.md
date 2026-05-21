# RAG Financial Analysis System 🤖📊

A **real** Retrieval-Augmented Generation (RAG) pipeline for financial forecasting — powered by Pinecone vector search, live NewsData.io market intelligence, Gemini AI, and pandas data analysis.

**Upload your own CSV/Excel data** → get AI-powered revenue forecasts with interactive charts and PDF reports.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📂 **CSV/Excel Upload** | Upload your own financial data via Telegram or the desktop GUI |
| 🔍 **Real Pinecone Search** | Semantic vector search with Gemini text-embedding-004 |
| 📰 **Live News** | Real-time financial news from NewsData.io |
| 🧠 **AI Forecasting** | Gemini 2.0 Flash-Lite with chain-of-thought reasoning |
| 📊 **Charts** | Dark-themed Matplotlib revenue charts with confidence intervals |
| 📄 **PDF Reports** | Professional multi-page executive report export |
| 🖥️ **Desktop GUI** | Tkinter dashboard with live pipeline logs and data preview |

---

## ⚡ Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

| Key | Source | Required |
|-----|--------|----------|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) | ✅ Yes |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com/app/apikey) | ✅ Yes |
| `PINECONE_API_KEY` | [app.pinecone.io](https://app.pinecone.io) | Optional |
| `NEWSDATA_API_KEY` | [newsdata.io](https://newsdata.io) | Optional |
| `OPENROUTER_API_KEY` | [openrouter.ai](https://openrouter.ai) | Optional (fallback) |

### 3. Run

**Telegram Bot only:**
```bash
python rag_demo.py
```

**Desktop GUI only:**
```bash
python gui_app.py
```

**Both together:**
```bash
python launch_all.py
```

---

## 🤖 Bot Commands

| Command | Action |
|---------|--------|
| `/start` | Welcome message |
| `/demo` | Run sample forecast with built-in demo data |
| `/report` | Generate PDF executive report of last forecast |
| `/help` | Commands and example queries |
| **Send CSV/Excel** | Upload and auto-analyze your data |
| **Any text** | Run RAG pipeline → AI forecast |

---

## 📊 How It Works

```
User uploads CSV/Excel or sends query
    ↓
[Node 1/7] pandas data analysis (real statistics)
    ↓
[Node 2/7] NewsData.io live financial news
    ↓
[Node 3/7] Pinecone vector search (768-dim embeddings)
    ↓
[Node 4/7] Gemini text-embedding-004 generation
    ↓
[Node 5/7] Context assembly (data + news + docs)
    ↓
[Node 6/7] Gemini 2.0 Flash-Lite AI forecast
    ↓
[Node 7/7] Format response + chart + PDF
```

---

## 📁 Project Structure

```
rag-financial-analysis/
├── rag_demo.py              ← Telegram bot (slim handler-only entry point)
├── gui_app.py               ← Desktop GUI dashboard
├── launch_all.py            ← Dual launcher (bot + GUI)
├── core/
│   ├── __init__.py
│   ├── analyzer.py          ← Real pandas data analysis engine
│   ├── ai_engine.py         ← Gemini AI + embeddings + fallback chain
│   ├── chart_engine.py      ← Dark-themed Matplotlib charts
│   ├── pipeline.py          ← RAG pipeline orchestrator
│   ├── formatters.py        ← Telegram HTML message formatters
│   └── pdf_report.py        ← Executive PDF report generator
├── data/
│   ├── __init__.py
│   ├── sample_data.py       ← Demo datasets + fallback constants
│   └── samples/
│       └── demo_sales.csv   ← 12-month sample dataset
├── requirements.txt
├── .env.example
├── .gitignore
├── Procfile
└── run.bat
```

---

## ⚙️ Tech Stack

| Component | Technology |
|-----------|------------|
| Bot Framework | python-telegram-bot 21+ |
| AI Model | Google Gemini 2.0 Flash-Lite |
| Embeddings | Gemini text-embedding-004 (768-dim) |
| Vector DB | Pinecone (serverless) |
| Live News | NewsData.io API |
| Data Analysis | pandas + numpy |
| Charts | Matplotlib |
| PDF Export | ReportLab |
| Desktop GUI | Tkinter |
| Fallback AI | OpenRouter |

---

## 📄 License

MIT
