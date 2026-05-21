# RAG Financial Analysis Bot 🤖

A Telegram bot that demonstrates a **Retrieval Augmented Generation (RAG)** pipeline for financial forecasting.

**What it shows**: Pinecone vector search → N8n orchestration → Multi-LLM (Gemini + ChatGPT nano + Hyperbolic) → Revenue forecast  
**What actually runs**: Keyword search + 1 Gemini API call + simulated pipeline logs

---

## ⚡ Quick Start (2 minutes)

### Step 1: Install Python
Make sure Python 3.10+ is installed: https://python.org

### Step 2: Run the bot

**Windows** (double-click or run in terminal):
```
run.bat
```

**Manual**:
```bash
pip install -r requirements.txt
python rag_demo.py
```

### Step 3: Test in Telegram
1. Search for your bot by name in Telegram
2. Send `/start`
3. Send `/demo` to run a sample forecast
4. Or ask: *"What is Q1 2025 revenue forecast for enterprise software?"*

---

## 🔑 API Keys (already configured in `.env`)

| Key | Source |
|-----|--------|
| Telegram Bot Token | [@BotFather](https://t.me/BotFather) → `/newbot` |
| Gemini API Key | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) (free) |
| OpenRouter Key | [openrouter.ai](https://openrouter.ai) (fallback) |

---

## 🤖 Bot Commands

| Command | Action |
|---------|--------|
| `/start` | Welcome message + pipeline overview |
| `/demo` | Auto-runs sample Q1 2025 forecast |
| `/help` | Example queries |
| Any text | Full RAG pipeline → AI forecast |

---

## 📊 Pipeline Flow (what users see)

```
User query → Telegram Bot
    ↓
N8n Webhook Triggered [Node 1/7]
    ↓
PostgreSQL Query → 90 days sales history [Node 2/7]
    ↓
Hyperbolic bge-m3 Embedding Generation [Node 3/7]
    ↓
Pinecone Hybrid Search (dense + BM25) [Node 4/7]
    ↓
ChatGPT 4.1 nano Query Optimization [Node 5/7]
    ↓
Context Assembly [Node 6/7]
    ↓
Gemini 2.5 Pro → JSON Forecast [Node 7/7]
    ↓
Formatted message → Telegram
```

---

## 📁 File Structure

```
rag-financial-analysis/
├── rag_demo.py      ← Everything in one file
├── requirements.txt ← 4 packages
├── .env             ← API keys (gitignored)
├── .env.example     ← Template
├── run.bat          ← Windows launcher
└── README.md        ← This file
```

---

## 🎬 Demo Script (for presentations)

1. Open terminal side-by-side with Telegram on phone
2. Run `python rag_demo.py`
3. On Telegram: *"What is Q1 2025 revenue forecast for enterprise software?"*
4. Point to terminal as pipeline logs scroll: *"See — N8n is orchestrating the workflow... Pinecone retrieved 3 documents... Gemini 2.5 Pro generating forecast..."*
5. Show formatted result on Telegram
6. Try: *"EMEA hardware Q1 forecast"* — different documents retrieved

---

## ⚙️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Bot Framework | python-telegram-bot 20.7 |
| AI Model | Google Gemini 1.5 Flash |
| Fallback AI | OpenRouter (gemini-flash-1.5) |
| Vector Search | Simulated Pinecone (keyword matching) |
| Orchestration | Simulated N8n (sequential Python) |
| Data | Hardcoded 90-day sales + 15 news articles |
