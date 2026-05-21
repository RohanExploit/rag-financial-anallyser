"""
RAG Financial Analysis — Desktop GUI
Dark-themed Tkinter app with embedded charts, live pipeline logs, KPI cards.
Runs independently from the Telegram bot.
"""
import sys, io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import tkinter as tk
from tkinter import ttk, scrolledtext, font as tkfont
import threading
import queue
import time
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Import forecast logic from bot ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from rag_demo import (
    run_full_forecast, FAKE_SALES_DATA, FALLBACK_FORECAST,
    build_sparkline, fake_pinecone_search
)

# ══════════════════════════════════════════════════════════════════════════════
# THEME CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
BG          = "#0d1117"
BG2         = "#161b22"
BG3         = "#21262d"
BORDER      = "#30363d"
TEXT        = "#e6edf3"
TEXT_DIM    = "#8b949e"
ACCENT      = "#4A90D9"
GREEN       = "#2ECC71"
YELLOW      = "#F0E68C"
RED         = "#f85149"
PURPLE      = "#a371f7"
FONT_MAIN   = ("Segoe UI", 10)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_TITLE  = ("Segoe UI", 14, "bold")
FONT_H2     = ("Segoe UI", 11, "bold")
FONT_MONO   = ("Consolas", 9)
FONT_SMALL  = ("Segoe UI", 8)

# ══════════════════════════════════════════════════════════════════════════════
# LOG QUEUE — bridges forecast thread → GUI thread safely
# ══════════════════════════════════════════════════════════════════════════════
log_queue     = queue.Queue()
result_queue  = queue.Queue()

# Patch _log in rag_demo to also push to GUI queue
import rag_demo as _rd
_orig_log = _rd._log
def _gui_log(msg: str, delay: float = 0.0):
    _orig_log(msg, delay)
    log_queue.put(("LOG", msg))
_rd._log = _gui_log


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════
class RAGDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RAG Financial Analysis — Dashboard")
        self.configure(bg=BG)
        self.geometry("1280x820")
        self.minsize(1100, 700)

        # State
        self.forecast_count  = 0
        self.confidence_vals = []
        self.latency_vals    = []
        self.is_running      = False
        self.current_forecast= None

        self._setup_styles()
        self._build_ui()
        self._start_queue_poll()

    # ── Styles ────────────────────────────────────────────────────────────────
    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".",            background=BG,  foreground=TEXT,  font=FONT_MAIN)
        style.configure("TFrame",       background=BG)
        style.configure("Card.TFrame",  background=BG2, relief="flat")
        style.configure("TLabel",       background=BG,  foreground=TEXT,  font=FONT_MAIN)
        style.configure("Dim.TLabel",   background=BG2, foreground=TEXT_DIM, font=FONT_SMALL)
        style.configure("Title.TLabel", background=BG,  foreground=TEXT,  font=FONT_TITLE)
        style.configure("H2.TLabel",    background=BG2, foreground=TEXT,  font=FONT_H2)
        style.configure("KPI.TLabel",   background=BG2, foreground=ACCENT, font=("Segoe UI", 22, "bold"))
        style.configure("KPISub.TLabel",background=BG2, foreground=TEXT_DIM, font=FONT_SMALL)
        style.configure("Green.TLabel", background=BG2, foreground=GREEN, font=("Segoe UI", 22, "bold"))
        style.configure("Yellow.TLabel",background=BG2, foreground=YELLOW,font=("Segoe UI", 22, "bold"))
        style.configure("TButton",
            background=ACCENT, foreground="white", font=FONT_BOLD,
            borderwidth=0, focuscolor=ACCENT, padding=(12, 6))
        style.map("TButton",
            background=[("active", "#357ABD"), ("disabled", BG3)],
            foreground=[("disabled", TEXT_DIM)])
        style.configure("Run.TButton",
            background=GREEN, foreground="#0d1117", font=FONT_BOLD, padding=(16, 8))
        style.map("Run.TButton", background=[("active", "#27ae60"), ("disabled", BG3)])
        style.configure("Quick.TButton",
            background=BG3, foreground=TEXT, font=FONT_SMALL, padding=(8, 4))
        style.map("Quick.TButton", background=[("active", BORDER)])
        style.configure("TEntry",
            fieldbackground=BG3, foreground=TEXT, insertcolor=TEXT,
            bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, font=FONT_MAIN)
        style.configure("TNotebook",        background=BG,  bordercolor=BORDER)
        style.configure("TNotebook.Tab",    background=BG3, foreground=TEXT_DIM, padding=(12, 6))
        style.map("TNotebook.Tab",
            background=[("selected", BG2)],
            foreground=[("selected", TEXT)])

    # ── UI Build ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG2, height=56)
        hdr.pack(fill="x", padx=0, pady=0)
        hdr.pack_propagate(False)

        tk.Label(hdr, text="  RAG Financial Analysis System",
                 bg=BG2, fg=TEXT, font=FONT_TITLE).pack(side="left", padx=12, pady=10)

        # Status dot
        self.status_dot  = tk.Canvas(hdr, width=12, height=12, bg=BG2, highlightthickness=0)
        self.status_dot.pack(side="right", padx=(0, 6), pady=18)
        self._dot = self.status_dot.create_oval(1, 1, 11, 11, fill=GREEN, outline="")
        self.status_lbl  = tk.Label(hdr, text="Ready", bg=BG2, fg=GREEN, font=FONT_SMALL)
        self.status_lbl.pack(side="right", padx=(0, 4), pady=10)
        tk.Label(hdr, text="|", bg=BG2, fg=BORDER).pack(side="right", padx=6, pady=10)
        tk.Label(hdr, text=f"v1.0  |  Gemini 3.1 Flash-Lite  |  {datetime.now().strftime('%d %b %Y')}",
                 bg=BG2, fg=TEXT_DIM, font=FONT_SMALL).pack(side="right", padx=12, pady=10)

        # Thin accent line
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

        # ── KPI Row ──────────────────────────────────────────────────────────
        kpi_row = tk.Frame(self, bg=BG)
        kpi_row.pack(fill="x", padx=12, pady=(10, 0))
        self.kpi_count_var = tk.StringVar(value="0")
        self.kpi_conf_var  = tk.StringVar(value="—")
        self.kpi_lat_var   = tk.StringVar(value="—")
        self.kpi_cost_var  = tk.StringVar(value="$0.00")

        cards = [
            ("Total Forecasts",  self.kpi_count_var, "KPI.TLabel",    "Queries Run"),
            ("Avg Confidence",   self.kpi_conf_var,  "Green.TLabel",  "AI Prediction Quality"),
            ("Avg Latency",      self.kpi_lat_var,   "Yellow.TLabel", "End-to-End Speed"),
            ("Session Cost",     self.kpi_cost_var,  "KPI.TLabel",    "API Spend"),
        ]
        for title, var, style_name, subtitle in cards:
            self._make_kpi_card(kpi_row, title, var, style_name, subtitle)

        # ── Main body ────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        # Left panel
        self._build_left_panel(body)
        # Right panel
        self._build_right_panel(body)

    def _make_kpi_card(self, parent, title, var, style_name, subtitle):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        tk.Label(card, text=title, bg=BG2, fg=TEXT_DIM, font=FONT_SMALL).pack(anchor="w")
        ttk.Label(card, textvariable=var, style=style_name).pack(anchor="w", pady=(2, 0))
        ttk.Label(card, text=subtitle, style="Dim.TLabel").pack(anchor="w")

    # ── Left Panel ────────────────────────────────────────────────────────────
    def _build_left_panel(self, parent):
        left = ttk.Frame(parent, style="Card.TFrame", padding=16)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)

        # Query section
        ttk.Label(left, text="Query Forecast", style="H2.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8))

        self.query_var = tk.StringVar(value="What is Q1 2025 revenue forecast for enterprise software?")
        entry_frame = tk.Frame(left, bg=BG3, highlightbackground=BORDER,
                               highlightthickness=1)
        entry_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.query_entry = tk.Text(entry_frame, height=3, bg=BG3, fg=TEXT,
                                   insertbackground=TEXT, font=FONT_MAIN,
                                   bd=0, padx=8, pady=8, wrap="word",
                                   relief="flat")
        self.query_entry.insert("1.0", self.query_var.get())
        self.query_entry.pack(fill="both", expand=True)

        # Run button
        self.run_btn = ttk.Button(left, text="▶  Run Forecast",
                                  style="Run.TButton", command=self._on_run)
        self.run_btn.grid(row=2, column=0, sticky="ew", pady=(0, 14))

        # Quick query buttons
        ttk.Label(left, text="Quick Queries", style="H2.TLabel").grid(
            row=3, column=0, sticky="w", pady=(0, 6))
        quick_frame = tk.Frame(left, bg=BG2)
        quick_frame.grid(row=4, column=0, sticky="ew")

        quick_queries = [
            ("🇺🇸 North America Q1",  "North America enterprise software revenue forecast Q1 2025"),
            ("🌍 EMEA Enterprise",    "What is Q1 2025 revenue forecast for EMEA enterprise tech?"),
            ("🌏 APAC SaaS",          "Predict Q1 2025 APAC SaaS revenue growth"),
            ("💻 Hardware Q2",        "Q2 2025 hardware revenue forecast North America"),
            ("📊 B2B Software",       "Revenue outlook for B2B software deals next quarter"),
            ("🤖 AI Products",        "AI-powered product revenue forecast Q1 2025"),
        ]
        for i, (label, q) in enumerate(quick_queries):
            r, c = divmod(i, 2)
            btn = ttk.Button(quick_frame, text=label, style="Quick.TButton",
                             command=lambda qry=q: self._set_and_run(qry))
            btn.grid(row=r, column=c, sticky="ew", padx=(0 if c else 0, 4), pady=3)
        quick_frame.columnconfigure(0, weight=1)
        quick_frame.columnconfigure(1, weight=1)

        # Sparkline panel
        tk.Frame(left, bg=BORDER, height=1).grid(row=5, column=0, sticky="ew", pady=14)
        ttk.Label(left, text="Revenue Trend (90-day)", style="H2.TLabel").grid(
            row=6, column=0, sticky="w", pady=(0, 6))
        self.spark_lbl = tk.Label(left, text="▁▂▄▅▇█", bg=BG2, fg=ACCENT,
                                  font=("Consolas", 18))
        self.spark_lbl.grid(row=7, column=0, sticky="w", pady=(0, 2))
        self.trend_lbl = tk.Label(left, text="Oct'24 → Jan'25  |  +18.4% YoY",
                                  bg=BG2, fg=TEXT_DIM, font=FONT_SMALL)
        self.trend_lbl.grid(row=8, column=0, sticky="w")

        # Sales snapshot
        tk.Frame(left, bg=BORDER, height=1).grid(row=9, column=0, sticky="ew", pady=14)
        ttk.Label(left, text="Sales Snapshot", style="H2.TLabel").grid(
            row=10, column=0, sticky="w", pady=(0, 6))
        snap_data = [
            ("30-Day Avg Revenue", f"${FAKE_SALES_DATA['30_day_rolling_avg']/1e6:.2f}M"),
            ("YoY Growth",         f"+{FAKE_SALES_DATA['yoy_growth_percent']}%"),
            ("Pipeline Value",     f"${FAKE_SALES_DATA['pipeline_value']/1e6:.1f}M"),
            ("Win Rate",           f"{FAKE_SALES_DATA['win_rate_percent']}%"),
            ("Deal Velocity",      f"{FAKE_SALES_DATA['deal_velocity_days']} days"),
        ]
        snap_frame = tk.Frame(left, bg=BG2)
        snap_frame.grid(row=11, column=0, sticky="ew")
        for i, (k, v) in enumerate(snap_data):
            tk.Label(snap_frame, text=k, bg=BG2, fg=TEXT_DIM, font=FONT_SMALL,
                     anchor="w").grid(row=i, column=0, sticky="w", pady=1)
            tk.Label(snap_frame, text=v, bg=BG2, fg=TEXT, font=FONT_BOLD,
                     anchor="e").grid(row=i, column=1, sticky="e", padx=(20, 0), pady=1)
        snap_frame.columnconfigure(0, weight=1)

    # ── Right Panel ───────────────────────────────────────────────────────────
    def _build_right_panel(self, parent):
        right = ttk.Frame(parent, style="Card.TFrame", padding=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(right)
        notebook.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        right.rowconfigure(0, weight=1)

        # Tab 1: Forecast Result
        self._build_result_tab(notebook)
        # Tab 2: Pipeline Logs
        self._build_logs_tab(notebook)
        # Tab 3: Chart
        self._build_chart_tab(notebook)

    def _build_result_tab(self, notebook):
        frame = ttk.Frame(notebook, style="Card.TFrame", padding=16)
        notebook.add(frame, text="  📊 Forecast Result  ")
        frame.columnconfigure(0, weight=1)

        # Placeholder
        self.result_placeholder = tk.Label(
            frame,
            text="🎯\n\nRun a forecast query to see results here.\n\nUse the Quick Queries on the left\nor type your own question.",
            bg=BG2, fg=TEXT_DIM, font=("Segoe UI", 12), justify="center"
        )
        self.result_placeholder.pack(expand=True)

        # Result content (hidden until forecast runs)
        self.result_frame = tk.Frame(frame, bg=BG2)

        # Forecast header
        self.res_title = tk.Label(self.result_frame, text="", bg=BG2, fg=TEXT,
                                  font=("Segoe UI", 15, "bold"), anchor="w")
        self.res_title.pack(fill="x", pady=(0, 4))

        # Big metric row
        metric_row = tk.Frame(self.result_frame, bg=BG2)
        metric_row.pack(fill="x", pady=(0, 12))

        self.res_value = tk.Label(metric_row, text="", bg=BG2, fg=GREEN,
                                  font=("Segoe UI", 32, "bold"))
        self.res_value.pack(side="left")

        right_metrics = tk.Frame(metric_row, bg=BG2)
        right_metrics.pack(side="left", padx=20)
        self.res_conf  = tk.Label(right_metrics, text="", bg=BG2, fg=TEXT, font=FONT_BOLD)
        self.res_conf.pack(anchor="w")
        self.res_range = tk.Label(right_metrics, text="", bg=BG2, fg=TEXT_DIM, font=FONT_MAIN)
        self.res_range.pack(anchor="w")
        self.res_bar   = tk.Label(right_metrics, text="", bg=BG2, fg=ACCENT,
                                  font=("Consolas", 12))
        self.res_bar.pack(anchor="w")

        # Separator
        tk.Frame(self.result_frame, bg=BORDER, height=1).pack(fill="x", pady=8)

        # Drivers
        tk.Label(self.result_frame, text="📈 Key Drivers", bg=BG2, fg=TEXT,
                 font=FONT_H2).pack(anchor="w")
        self.res_drivers = tk.Label(self.result_frame, text="", bg=BG2, fg=TEXT,
                                    font=FONT_MAIN, anchor="w", justify="left",
                                    wraplength=550)
        self.res_drivers.pack(anchor="w", pady=(4, 12))

        # Analysis
        tk.Label(self.result_frame, text="💡 Analysis", bg=BG2, fg=TEXT,
                 font=FONT_H2).pack(anchor="w")
        self.res_analysis = tk.Label(self.result_frame, text="", bg=BG2, fg=TEXT_DIM,
                                     font=FONT_MAIN, anchor="w", justify="left",
                                     wraplength=550)
        self.res_analysis.pack(anchor="w", pady=(4, 12))

        # Market signal
        tk.Label(self.result_frame, text="📰 Market Signal", bg=BG2, fg=TEXT,
                 font=FONT_H2).pack(anchor="w")
        self.res_signal = tk.Label(self.result_frame, text="", bg=BG2, fg=YELLOW,
                                   font=FONT_MAIN, anchor="w", justify="left",
                                   wraplength=550)
        self.res_signal.pack(anchor="w", pady=(4, 12))

        # Risk
        tk.Label(self.result_frame, text="⚠️ Risk Factor", bg=BG2, fg=TEXT,
                 font=FONT_H2).pack(anchor="w")
        self.res_risk = tk.Label(self.result_frame, text="", bg=BG2, fg=RED,
                                  font=FONT_MAIN, anchor="w", wraplength=550)
        self.res_risk.pack(anchor="w", pady=(4, 0))

    def _build_logs_tab(self, notebook):
        frame = ttk.Frame(notebook, style="Card.TFrame", padding=8)
        notebook.add(frame, text="  🔧 Pipeline Logs  ")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            frame, bg=BG, fg=GREEN, insertbackground=GREEN,
            font=FONT_MONO, bd=0, relief="flat",
            state="disabled", wrap="word"
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        # Color tags
        self.log_text.tag_configure("green",  foreground=GREEN)
        self.log_text.tag_configure("yellow", foreground=YELLOW)
        self.log_text.tag_configure("blue",   foreground=ACCENT)
        self.log_text.tag_configure("red",    foreground=RED)
        self.log_text.tag_configure("dim",    foreground=TEXT_DIM)
        self.log_text.tag_configure("white",  foreground=TEXT)

        # Clear button
        ttk.Button(frame, text="Clear Logs", style="Quick.TButton",
                   command=self._clear_logs).grid(row=1, column=0, sticky="e", pady=(4, 0))

        self._append_log("RAG Financial Analysis Dashboard Ready", "blue")
        self._append_log("Type a query and click Run Forecast to begin.", "dim")

    def _build_chart_tab(self, notebook):
        frame = ttk.Frame(notebook, style="Card.TFrame", padding=8)
        notebook.add(frame, text="  📈 Revenue Chart  ")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.chart_placeholder = tk.Label(
            frame,
            text="📈\n\nRun a forecast to see the\nrevenue chart here.",
            bg=BG2, fg=TEXT_DIM, font=("Segoe UI", 12), justify="center"
        )
        self.chart_placeholder.pack(expand=True)

        self.chart_canvas_frame = tk.Frame(frame, bg=BG2)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _set_and_run(self, query: str):
        self.query_entry.delete("1.0", "end")
        self.query_entry.insert("1.0", query)
        self._on_run()

    def _on_run(self):
        if self.is_running:
            return
        query = self.query_entry.get("1.0", "end").strip()
        if not query:
            return
        self.is_running = True
        self.run_btn.config(state="disabled", text="⏳  Running...")
        self.status_dot.itemconfig(self._dot, fill=YELLOW)
        self.status_lbl.config(text="Processing...", fg=YELLOW)
        self._append_log("=" * 55, "dim")
        self._append_log(f"Query: {query}", "blue")
        threading.Thread(target=self._run_forecast_thread,
                         args=(query,), daemon=True).start()

    def _run_forecast_thread(self, query: str):
        try:
            msg, forecast, chart_png = run_full_forecast(query)
            result_queue.put(("OK", forecast, chart_png, query))
        except Exception as e:
            result_queue.put(("ERR", str(e), None, query))

    # ── Queue polling ─────────────────────────────────────────────────────────
    def _start_queue_poll(self):
        self._poll_queues()

    def _poll_queues(self):
        # Drain log queue
        while not log_queue.empty():
            try:
                kind, msg = log_queue.get_nowait()
                if kind == "LOG":
                    self._route_log(msg)
            except queue.Empty:
                break

        # Check result queue
        while not result_queue.empty():
            try:
                item = result_queue.get_nowait()
                if item[0] == "OK":
                    _, forecast, chart_png, query = item
                    self._on_forecast_done(forecast, chart_png)
                else:
                    _, err, _, query = item
                    self._append_log(f"ERROR: {err}", "red")
                    self._on_forecast_done(FALLBACK_FORECAST, None)
            except queue.Empty:
                break

        self.after(100, self._poll_queues)

    def _route_log(self, msg: str):
        """Color-code log lines by content."""
        if not msg.strip():
            return
        if any(k in msg for k in ["✓", "✅", "Gemini API call succeeded"]):
            tag = "green"
        elif any(k in msg for k in ["ERROR", "error", "failed", "✗"]):
            tag = "red"
        elif any(k in msg for k in ["🚀", "Calling Gemini", "Node 7"]):
            tag = "yellow"
        elif any(k in msg for k in ["[Node", "N8n", "Pinecone", "Hyperbolic"]):
            tag = "blue"
        elif msg.startswith("="*5) or msg.startswith("═"*5):
            tag = "dim"
        else:
            tag = "white"
        self._append_log(msg, tag)

    def _append_log(self, msg: str, tag: str = "white"):
        self.log_text.config(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    # ── Forecast Done ─────────────────────────────────────────────────────────
    def _on_forecast_done(self, forecast: dict, chart_png: bytes):
        self.is_running = False
        self.run_btn.config(state="normal", text="▶  Run Forecast")
        self.status_dot.itemconfig(self._dot, fill=GREEN)
        self.status_lbl.config(text="Ready", fg=GREEN)

        # Update KPIs
        self.forecast_count += 1
        pct = forecast.get("confidence_percent", 85)
        self.confidence_vals.append(pct)
        self.kpi_count_var.set(str(self.forecast_count))
        self.kpi_conf_var.set(f"{sum(self.confidence_vals)/len(self.confidence_vals):.1f}%")
        cost = self.forecast_count * 0.008
        self.kpi_cost_var.set(f"${cost:.3f}")
        self.kpi_lat_var.set("~3.2s")

        # Update sparkline
        revs = list(FAKE_SALES_DATA["monthly_revenue"].values()) + [forecast.get("forecast_value", 0)]
        self.spark_lbl.config(text=build_sparkline(revs))

        # Show result panel
        self._update_result_panel(forecast)

        # Embed chart
        if chart_png:
            self._embed_chart(chart_png)

    def _update_result_panel(self, forecast: dict):
        v    = forecast.get("forecast_value", 0)
        low  = forecast.get("range_low",  v * 0.9)
        high = forecast.get("range_high", v * 1.1)
        pct  = forecast.get("confidence_percent", 85)
        tf   = forecast.get("timeframe", "Q1 2025")
        kd   = forecast.get("key_drivers", [])
        rsn  = forecast.get("reasoning", "")
        ms   = forecast.get("market_signal", "")
        risk = forecast.get("risk", "")
        bar  = ("█" * round(pct/10)) + ("░" * (10 - round(pct/10)))

        self.res_title.config(text=f"🎯  Financial Forecast — {tf}")
        self.res_value.config(text=f"${v/1_000_000:.2f}M")
        self.res_conf.config(text=f"Confidence: {pct}%")
        self.res_range.config(text=f"Range: ${low/1_000_000:.2f}M — ${high/1_000_000:.2f}M")
        self.res_bar.config(text=bar)

        drivers = "\n".join(f"  {'①②③'[i]}  {d}" for i, d in enumerate(kd[:3]))
        self.res_drivers.config(text=drivers or "—")
        self.res_analysis.config(text=rsn or "—")
        self.res_signal.config(text=f'"{ms}"' if ms else "—")
        self.res_risk.config(text=risk or "—")

        self.result_placeholder.pack_forget()
        self.result_frame.pack(fill="both", expand=True)

    def _embed_chart(self, png_bytes: bytes):
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import matplotlib.pyplot as plt
            import io

            # Clear old chart
            for w in self.chart_canvas_frame.winfo_children():
                w.destroy()

            fig_buf = io.BytesIO(png_bytes)
            img = plt.imread(fig_buf)
            fig, ax = plt.subplots(figsize=(8, 4.5))
            fig.patch.set_facecolor("#0d1117")
            ax.set_facecolor("#0d1117")
            ax.imshow(img)
            ax.axis("off")
            plt.tight_layout(pad=0)

            canvas = FigureCanvasTkAgg(fig, master=self.chart_canvas_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            plt.close(fig)

            self.chart_placeholder.pack_forget()
            self.chart_canvas_frame.pack(fill="both", expand=True)
        except Exception as e:
            self._append_log(f"Chart embed error: {e}", "red")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = RAGDashboard()
    app.mainloop()
