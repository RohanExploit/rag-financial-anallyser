"""
RAG Financial Analysis — Desktop GUI Dashboard

Dark-themed Tkinter app with embedded charts, live pipeline logs,
KPI cards, CSV/Excel file loading, and PDF export.
"""
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk, scrolledtext, filedialog, messagebox

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ── Import from core modules ─────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from core.pipeline import run_pipeline
from core.analyzer import DataAnalyzer, analyze_from_demo
from core.formatters import build_sparkline
from core.pdf_report import generate_pdf_report
from data.sample_data import DEMO_SALES_DATA

# ══════════════════════════════════════════════════════════════════════════════
# THEME CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
BG = "#0d1117"
BG2 = "#161b22"
BG3 = "#21262d"
BORDER = "#30363d"
TEXT = "#e6edf3"
TEXT_DIM = "#8b949e"
ACCENT = "#4A90D9"
GREEN = "#2ECC71"
YELLOW = "#F0E68C"
RED = "#f85149"
FONT_MAIN = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 14, "bold")
FONT_H2 = ("Segoe UI", 11, "bold")
FONT_MONO = ("Consolas", 9)
FONT_SMALL = ("Segoe UI", 8)

# ══════════════════════════════════════════════════════════════════════════════
# LOG QUEUE — bridges forecast thread → GUI thread safely
# ══════════════════════════════════════════════════════════════════════════════
log_queue = queue.Queue()
result_queue = queue.Queue()

# Patch pipeline._log to also push to GUI queue
import core.pipeline as _pipeline

_orig_log = _pipeline._log


def _gui_log(msg: str, delay: float = 0.0) -> None:
    _orig_log(msg, delay)
    log_queue.put(("LOG", msg))


_pipeline._log = _gui_log


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════
class RAGDashboard(tk.Tk):
    """Main desktop dashboard application."""

    def __init__(self) -> None:
        super().__init__()
        self.title("RAG Financial Analysis — Dashboard")
        self.configure(bg=BG)
        self.geometry("1300x860")
        self.minsize(1100, 700)

        # State
        self.forecast_count = 0
        self.confidence_vals: list[int] = []
        self.latency_vals: list[float] = []
        self.is_running = False
        self.current_forecast: dict = {}
        self.current_analysis = None
        self.current_chart: bytes = b""
        self.loaded_df: pd.DataFrame = None
        self.loaded_filename: str = ""

        self._setup_styles()
        self._build_ui()
        self._start_queue_poll()

    # ── Styles ────────────────────────────────────────────────────────────
    def _setup_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=FONT_MAIN)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=BG2, relief="flat")
        style.configure("TLabel", background=BG, foreground=TEXT, font=FONT_MAIN)
        style.configure("Dim.TLabel", background=BG2, foreground=TEXT_DIM, font=FONT_SMALL)
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=FONT_TITLE)
        style.configure("H2.TLabel", background=BG2, foreground=TEXT, font=FONT_H2)
        style.configure("KPI.TLabel", background=BG2, foreground=ACCENT, font=("Segoe UI", 22, "bold"))
        style.configure("KPISub.TLabel", background=BG2, foreground=TEXT_DIM, font=FONT_SMALL)
        style.configure("Green.TLabel", background=BG2, foreground=GREEN, font=("Segoe UI", 22, "bold"))
        style.configure("Yellow.TLabel", background=BG2, foreground=YELLOW, font=("Segoe UI", 22, "bold"))
        style.configure("TButton", background=ACCENT, foreground="white", font=FONT_BOLD,
                         borderwidth=0, focuscolor=ACCENT, padding=(12, 6))
        style.map("TButton", background=[("active", "#357ABD"), ("disabled", BG3)],
                  foreground=[("disabled", TEXT_DIM)])
        style.configure("Run.TButton", background=GREEN, foreground="#0d1117", font=FONT_BOLD, padding=(16, 8))
        style.map("Run.TButton", background=[("active", "#27ae60"), ("disabled", BG3)])
        style.configure("Quick.TButton", background=BG3, foreground=TEXT, font=FONT_SMALL, padding=(8, 4))
        style.map("Quick.TButton", background=[("active", BORDER)])
        style.configure("TNotebook", background=BG, bordercolor=BORDER)
        style.configure("TNotebook.Tab", background=BG3, foreground=TEXT_DIM, padding=(12, 6))
        style.map("TNotebook.Tab", background=[("selected", BG2)], foreground=[("selected", TEXT)])

    # ── UI Build ──────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        # ── Header ───────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG2, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="  RAG Financial Analysis System", bg=BG2, fg=TEXT, font=FONT_TITLE).pack(
            side="left", padx=12, pady=10)

        self.status_dot = tk.Canvas(hdr, width=12, height=12, bg=BG2, highlightthickness=0)
        self.status_dot.pack(side="right", padx=(0, 6), pady=18)
        self._dot = self.status_dot.create_oval(1, 1, 11, 11, fill=GREEN, outline="")
        self.status_lbl = tk.Label(hdr, text="Ready", bg=BG2, fg=GREEN, font=FONT_SMALL)
        self.status_lbl.pack(side="right", padx=(0, 4), pady=10)

        tk.Label(hdr, text="|", bg=BG2, fg=BORDER).pack(side="right", padx=6, pady=10)
        tk.Label(hdr, text=f"v2.0  |  Real Analysis Engine  |  {datetime.now().strftime('%d %b %Y')}",
                 bg=BG2, fg=TEXT_DIM, font=FONT_SMALL).pack(side="right", padx=12, pady=10)

        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

        # ── KPI Row ──────────────────────────────────────────────────────
        kpi_row = tk.Frame(self, bg=BG)
        kpi_row.pack(fill="x", padx=12, pady=(10, 0))
        self.kpi_count_var = tk.StringVar(value="0")
        self.kpi_conf_var = tk.StringVar(value="—")
        self.kpi_lat_var = tk.StringVar(value="—")
        self.kpi_data_var = tk.StringVar(value="No data")

        cards = [
            ("Total Forecasts", self.kpi_count_var, "KPI.TLabel", "Queries Run"),
            ("Avg Confidence", self.kpi_conf_var, "Green.TLabel", "AI Prediction Quality"),
            ("Avg Latency", self.kpi_lat_var, "Yellow.TLabel", "End-to-End Speed"),
            ("Dataset", self.kpi_data_var, "KPI.TLabel", "Loaded Data"),
        ]
        for title, var, style_name, subtitle in cards:
            self._make_kpi_card(kpi_row, title, var, style_name, subtitle)

        # ── Main body ────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        self._build_left_panel(body)
        self._build_right_panel(body)

    def _make_kpi_card(self, parent, title, var, style_name, subtitle) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        tk.Label(card, text=title, bg=BG2, fg=TEXT_DIM, font=FONT_SMALL).pack(anchor="w")
        ttk.Label(card, textvariable=var, style=style_name).pack(anchor="w", pady=(2, 0))
        ttk.Label(card, text=subtitle, style="Dim.TLabel").pack(anchor="w")

    # ── Left Panel ────────────────────────────────────────────────────────
    def _build_left_panel(self, parent) -> None:
        left = ttk.Frame(parent, style="Card.TFrame", padding=16)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)

        row = 0

        # ── File Upload Section ──────────────────────────────────────────
        ttk.Label(left, text="📂 Data Source", style="H2.TLabel").grid(row=row, column=0, sticky="w", pady=(0, 6))
        row += 1

        file_frame = tk.Frame(left, bg=BG2)
        file_frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        file_frame.columnconfigure(0, weight=1)
        row += 1

        self.file_lbl = tk.Label(file_frame, text="No file loaded (using demo data)", bg=BG2, fg=TEXT_DIM,
                                 font=FONT_SMALL, anchor="w")
        self.file_lbl.grid(row=0, column=0, sticky="w", padx=4)

        btn_frame = tk.Frame(file_frame, bg=BG2)
        btn_frame.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(btn_frame, text="📂 Load CSV/Excel", style="Quick.TButton",
                   command=self._on_load_file).pack(side="left", padx=(0, 4))
        ttk.Button(btn_frame, text="📄 Export PDF", style="Quick.TButton",
                   command=self._on_export_pdf).pack(side="left")

        tk.Frame(left, bg=BORDER, height=1).grid(row=row, column=0, sticky="ew", pady=10)
        row += 1

        # ── Query Section ────────────────────────────────────────────────
        ttk.Label(left, text="Query Forecast", style="H2.TLabel").grid(row=row, column=0, sticky="w", pady=(0, 8))
        row += 1

        entry_frame = tk.Frame(left, bg=BG3, highlightbackground=BORDER, highlightthickness=1)
        entry_frame.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        row += 1

        self.query_entry = tk.Text(entry_frame, height=3, bg=BG3, fg=TEXT,
                                   insertbackground=TEXT, font=FONT_MAIN,
                                   bd=0, padx=8, pady=8, wrap="word", relief="flat")
        self.query_entry.insert("1.0", "What is Q1 2025 revenue forecast for enterprise software?")
        self.query_entry.pack(fill="both", expand=True)

        self.run_btn = ttk.Button(left, text="▶  Run Forecast", style="Run.TButton", command=self._on_run)
        self.run_btn.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        row += 1

        # Quick query buttons
        ttk.Label(left, text="Quick Queries", style="H2.TLabel").grid(row=row, column=0, sticky="w", pady=(0, 6))
        row += 1

        quick_frame = tk.Frame(left, bg=BG2)
        quick_frame.grid(row=row, column=0, sticky="ew")
        row += 1

        quick_queries = [
            ("🇺🇸 North America Q1", "North America enterprise software revenue forecast Q1 2025"),
            ("🌍 EMEA Enterprise", "What is Q1 2025 revenue forecast for EMEA enterprise tech?"),
            ("🌏 APAC SaaS", "Predict Q1 2025 APAC SaaS revenue growth"),
            ("📊 B2B Software", "Revenue outlook for B2B software deals next quarter"),
        ]
        for i, (label, q) in enumerate(quick_queries):
            r, c = divmod(i, 2)
            btn = ttk.Button(quick_frame, text=label, style="Quick.TButton",
                             command=lambda qry=q: self._set_and_run(qry))
            btn.grid(row=r, column=c, sticky="ew", padx=(0 if c == 0 else 4, 0), pady=3)
        quick_frame.columnconfigure(0, weight=1)
        quick_frame.columnconfigure(1, weight=1)

        # Sparkline
        tk.Frame(left, bg=BORDER, height=1).grid(row=row, column=0, sticky="ew", pady=14)
        row += 1
        ttk.Label(left, text="Revenue Trend", style="H2.TLabel").grid(row=row, column=0, sticky="w", pady=(0, 6))
        row += 1
        self.spark_lbl = tk.Label(left, text="▁▂▄▅▇█", bg=BG2, fg=ACCENT, font=("Consolas", 18))
        self.spark_lbl.grid(row=row, column=0, sticky="w", pady=(0, 2))
        row += 1
        self.trend_lbl = tk.Label(left, text="Demo data  |  +18.4% YoY", bg=BG2, fg=TEXT_DIM, font=FONT_SMALL)
        self.trend_lbl.grid(row=row, column=0, sticky="w")

    # ── Right Panel ───────────────────────────────────────────────────────
    def _build_right_panel(self, parent) -> None:
        right = ttk.Frame(parent, style="Card.TFrame", padding=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(right)
        notebook.grid(row=0, column=0, sticky="nsew")

        self._build_result_tab(notebook)
        self._build_logs_tab(notebook)
        self._build_chart_tab(notebook)
        self._build_data_tab(notebook)

    def _build_result_tab(self, notebook) -> None:
        frame = ttk.Frame(notebook, style="Card.TFrame", padding=16)
        notebook.add(frame, text="  📊 Forecast Result  ")
        frame.columnconfigure(0, weight=1)

        self.result_placeholder = tk.Label(
            frame, text="🎯\n\nRun a forecast query to see results here.\n\nLoad a CSV/Excel file or use Quick Queries.",
            bg=BG2, fg=TEXT_DIM, font=("Segoe UI", 12), justify="center",
        )
        self.result_placeholder.pack(expand=True)

        self.result_frame = tk.Frame(frame, bg=BG2)
        self.res_title = tk.Label(self.result_frame, text="", bg=BG2, fg=TEXT, font=("Segoe UI", 15, "bold"), anchor="w")
        self.res_title.pack(fill="x", pady=(0, 4))

        metric_row = tk.Frame(self.result_frame, bg=BG2)
        metric_row.pack(fill="x", pady=(0, 12))
        self.res_value = tk.Label(metric_row, text="", bg=BG2, fg=GREEN, font=("Segoe UI", 32, "bold"))
        self.res_value.pack(side="left")

        right_m = tk.Frame(metric_row, bg=BG2)
        right_m.pack(side="left", padx=20)
        self.res_conf = tk.Label(right_m, text="", bg=BG2, fg=TEXT, font=FONT_BOLD)
        self.res_conf.pack(anchor="w")
        self.res_range = tk.Label(right_m, text="", bg=BG2, fg=TEXT_DIM, font=FONT_MAIN)
        self.res_range.pack(anchor="w")
        self.res_bar = tk.Label(right_m, text="", bg=BG2, fg=ACCENT, font=("Consolas", 12))
        self.res_bar.pack(anchor="w")

        tk.Frame(self.result_frame, bg=BORDER, height=1).pack(fill="x", pady=8)

        tk.Label(self.result_frame, text="📈 Key Drivers", bg=BG2, fg=TEXT, font=FONT_H2).pack(anchor="w")
        self.res_drivers = tk.Label(self.result_frame, text="", bg=BG2, fg=TEXT, font=FONT_MAIN, anchor="w",
                                    justify="left", wraplength=550)
        self.res_drivers.pack(anchor="w", pady=(4, 12))

        tk.Label(self.result_frame, text="💡 Analysis", bg=BG2, fg=TEXT, font=FONT_H2).pack(anchor="w")
        self.res_analysis = tk.Label(self.result_frame, text="", bg=BG2, fg=TEXT_DIM, font=FONT_MAIN, anchor="w",
                                     justify="left", wraplength=550)
        self.res_analysis.pack(anchor="w", pady=(4, 12))

        tk.Label(self.result_frame, text="📰 Market Signal", bg=BG2, fg=TEXT, font=FONT_H2).pack(anchor="w")
        self.res_signal = tk.Label(self.result_frame, text="", bg=BG2, fg=YELLOW, font=FONT_MAIN, anchor="w",
                                   justify="left", wraplength=550)
        self.res_signal.pack(anchor="w", pady=(4, 12))

        tk.Label(self.result_frame, text="⚠️ Risk Factor", bg=BG2, fg=TEXT, font=FONT_H2).pack(anchor="w")
        self.res_risk = tk.Label(self.result_frame, text="", bg=BG2, fg=RED, font=FONT_MAIN, anchor="w", wraplength=550)
        self.res_risk.pack(anchor="w")

    def _build_logs_tab(self, notebook) -> None:
        frame = ttk.Frame(notebook, style="Card.TFrame", padding=8)
        notebook.add(frame, text="  🔧 Pipeline Logs  ")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            frame, bg=BG, fg=GREEN, insertbackground=GREEN, font=FONT_MONO,
            bd=0, relief="flat", state="disabled", wrap="word",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        for tag, color in [("green", GREEN), ("yellow", YELLOW), ("blue", ACCENT),
                           ("red", RED), ("dim", TEXT_DIM), ("white", TEXT)]:
            self.log_text.tag_configure(tag, foreground=color)

        ttk.Button(frame, text="Clear Logs", style="Quick.TButton",
                   command=self._clear_logs).grid(row=1, column=0, sticky="e", pady=(4, 0))

        self._append_log("RAG Financial Analysis Dashboard v2.0 Ready", "blue")
        self._append_log("Load a CSV/Excel file or type a query to begin.", "dim")

    def _build_chart_tab(self, notebook) -> None:
        frame = ttk.Frame(notebook, style="Card.TFrame", padding=8)
        notebook.add(frame, text="  📈 Revenue Chart  ")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.chart_placeholder = tk.Label(
            frame, text="📈\n\nRun a forecast to see the\nrevenue chart here.",
            bg=BG2, fg=TEXT_DIM, font=("Segoe UI", 12), justify="center",
        )
        self.chart_placeholder.pack(expand=True)
        self.chart_canvas_frame = tk.Frame(frame, bg=BG2)

    def _build_data_tab(self, notebook) -> None:
        """Data Preview tab — shows loaded CSV/Excel data."""
        frame = ttk.Frame(notebook, style="Card.TFrame", padding=8)
        notebook.add(frame, text="  📋 Data Preview  ")
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        self.data_placeholder = tk.Label(
            frame, text="📋\n\nLoad a CSV/Excel file to preview data here.",
            bg=BG2, fg=TEXT_DIM, font=("Segoe UI", 12), justify="center",
        )
        self.data_placeholder.pack(expand=True)

        self.data_tree_frame = tk.Frame(frame, bg=BG2)

    # ── Actions ───────────────────────────────────────────────────────────
    def _set_and_run(self, query: str) -> None:
        self.query_entry.delete("1.0", "end")
        self.query_entry.insert("1.0", query)
        self._on_run()

    def _on_run(self) -> None:
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
        threading.Thread(target=self._run_forecast_thread, args=(query,), daemon=True).start()

    def _run_forecast_thread(self, query: str) -> None:
        try:
            t0 = time.time()
            msg, forecast, chart_png = run_pipeline(query, self.loaded_df)
            latency = time.time() - t0
            result_queue.put(("OK", forecast, chart_png, query, latency))
        except Exception as e:
            result_queue.put(("ERR", str(e), None, query, 0.0))

    def _on_load_file(self) -> None:
        """Open file dialog and load CSV/Excel."""
        filepath = filedialog.askopenfilename(
            title="Select Financial Data File",
            filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
        )
        if not filepath:
            return

        try:
            ext = filepath.rsplit(".", 1)[-1].lower()
            if ext == "csv":
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)

            if df.empty:
                messagebox.showwarning("Empty File", "The selected file is empty.")
                return

            self.loaded_df = df
            self.loaded_filename = os.path.basename(filepath)

            # Analyze and show preview
            analyzer = DataAnalyzer(df)
            analysis = analyzer.analyze()
            self.current_analysis = analysis

            # Update UI
            self.file_lbl.config(text=f"✅ {self.loaded_filename} ({len(df):,} rows)", fg=GREEN)
            self.kpi_data_var.set(f"{len(df):,} rows")

            # Update sparkline
            if analysis.monthly_revenue:
                revs = list(analysis.monthly_revenue.values())
                self.spark_lbl.config(text=build_sparkline(revs))
                self.trend_lbl.config(
                    text=f"{analysis.date_range}  |  {'+' if analysis.yoy_growth >= 0 else ''}{analysis.yoy_growth:.1f}% YoY")

            # Show data preview
            self._show_data_preview(df)

            self._append_log(f"📂 Loaded: {self.loaded_filename} ({len(df):,} rows)", "green")
            self._append_log(f"   Detected: date={analysis.column_info.get('date_col', '?')}, "
                             f"value={analysis.column_info.get('value_col', '?')}", "blue")

        except Exception as e:
            messagebox.showerror("File Error", f"Error loading file:\n{e}")
            self._append_log(f"❌ File load error: {e}", "red")

    def _show_data_preview(self, df: pd.DataFrame) -> None:
        """Show first 50 rows in the Data Preview tab."""
        self.data_placeholder.pack_forget()

        for w in self.data_tree_frame.winfo_children():
            w.destroy()

        cols = list(df.columns)
        tree = ttk.Treeview(self.data_tree_frame, columns=cols, show="headings", height=20)

        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=100, minwidth=60)

        for _, row_data in df.head(50).iterrows():
            vals = [str(v)[:30] for v in row_data.values]
            tree.insert("", "end", values=vals)

        h_scroll = ttk.Scrollbar(self.data_tree_frame, orient="horizontal", command=tree.xview)
        v_scroll = ttk.Scrollbar(self.data_tree_frame, orient="vertical", command=tree.yview)
        tree.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        self.data_tree_frame.rowconfigure(0, weight=1)
        self.data_tree_frame.columnconfigure(0, weight=1)

        self.data_tree_frame.pack(fill="both", expand=True)

    def _on_export_pdf(self) -> None:
        """Export current forecast as PDF."""
        if not self.current_forecast or not self.current_analysis:
            messagebox.showinfo("No Forecast", "Run a forecast first, then export PDF.")
            return

        filepath = filedialog.asksaveasfilename(
            title="Save PDF Report",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"forecast_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
        )
        if not filepath:
            return

        try:
            pdf_bytes = generate_pdf_report(
                self.current_analysis, self.current_forecast,
                self.current_chart, self.query_entry.get("1.0", "end").strip(),
            )
            if pdf_bytes:
                with open(filepath, "wb") as f:
                    f.write(pdf_bytes)
                messagebox.showinfo("PDF Saved", f"Report saved to:\n{filepath}")
                self._append_log(f"📄 PDF exported: {os.path.basename(filepath)}", "green")
            else:
                messagebox.showerror("PDF Error", "Failed to generate PDF.")
        except Exception as e:
            messagebox.showerror("PDF Error", f"Error generating PDF:\n{e}")

    # ── Queue polling ─────────────────────────────────────────────────────
    def _start_queue_poll(self) -> None:
        self._poll_queues()

    def _poll_queues(self) -> None:
        while not log_queue.empty():
            try:
                kind, msg = log_queue.get_nowait()
                if kind == "LOG":
                    self._route_log(msg)
            except queue.Empty:
                break

        while not result_queue.empty():
            try:
                item = result_queue.get_nowait()
                if item[0] == "OK":
                    _, forecast, chart_png, query, latency = item
                    self._on_forecast_done(forecast, chart_png, latency)
                else:
                    _, err, _, query, _ = item
                    self._append_log(f"ERROR: {err}", "red")
                    self._on_forecast_done({}, None, 0.0)
            except queue.Empty:
                break

        self.after(100, self._poll_queues)

    def _route_log(self, msg: str) -> None:
        if not msg.strip():
            return
        if any(k in msg for k in ["✓", "✅", "succeeded"]):
            tag = "green"
        elif any(k in msg for k in ["ERROR", "error", "failed", "✗", "❌"]):
            tag = "red"
        elif any(k in msg for k in ["🚀", "Calling Gemini", "Node 6"]):
            tag = "yellow"
        elif any(k in msg for k in ["[Node", "Pinecone", "NewsData", "Analyzing"]):
            tag = "blue"
        elif msg.startswith("=" * 5) or msg.startswith("═" * 5):
            tag = "dim"
        else:
            tag = "white"
        self._append_log(msg, tag)

    def _append_log(self, msg: str, tag: str = "white") -> None:
        self.log_text.config(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_logs(self) -> None:
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    # ── Forecast Done ─────────────────────────────────────────────────────
    def _on_forecast_done(self, forecast: dict, chart_png: bytes, latency: float) -> None:
        self.is_running = False
        self.run_btn.config(state="normal", text="▶  Run Forecast")
        self.status_dot.itemconfig(self._dot, fill=GREEN)
        self.status_lbl.config(text="Ready", fg=GREEN)

        if not forecast:
            return

        self.current_forecast = forecast
        self.current_chart = chart_png

        # Update analysis if not already set from file load
        if self.current_analysis is None:
            self.current_analysis = analyze_from_demo()

        # Update KPIs
        self.forecast_count += 1
        pct = forecast.get("confidence_percent", 85)
        self.confidence_vals.append(pct)
        if latency > 0:
            self.latency_vals.append(latency)

        self.kpi_count_var.set(str(self.forecast_count))
        avg_conf = sum(self.confidence_vals) / len(self.confidence_vals)
        self.kpi_conf_var.set(f"{avg_conf:.1f}%")
        if self.latency_vals:
            avg_lat = sum(self.latency_vals) / len(self.latency_vals)
            self.kpi_lat_var.set(f"{avg_lat:.1f}s")

        # Update sparkline
        analysis = self.current_analysis
        if analysis and analysis.monthly_revenue:
            revs = list(analysis.monthly_revenue.values()) + [forecast.get("forecast_value", 0)]
            self.spark_lbl.config(text=build_sparkline(revs))

        self._update_result_panel(forecast)

        if chart_png:
            self._embed_chart(chart_png)

    def _update_result_panel(self, forecast: dict) -> None:
        v = forecast.get("forecast_value", 0)
        low = forecast.get("range_low", v * 0.9)
        high = forecast.get("range_high", v * 1.1)
        pct = forecast.get("confidence_percent", 85)
        tf = forecast.get("timeframe", "Q1 2025")
        kd = forecast.get("key_drivers", [])
        rsn = forecast.get("reasoning", "")
        ms = forecast.get("market_signal", "")
        risk = forecast.get("risk", "")
        bar = ("█" * round(pct / 10)) + ("░" * (10 - round(pct / 10)))

        self.res_title.config(text=f"🎯  Financial Forecast — {tf}")
        self.res_value.config(text=f"${v / 1_000_000:.2f}M")
        self.res_conf.config(text=f"Confidence: {pct}%")
        self.res_range.config(text=f"Range: ${low / 1_000_000:.2f}M — ${high / 1_000_000:.2f}M")
        self.res_bar.config(text=bar)

        drivers = "\n".join(f"  {'①②③'[i]}  {d}" for i, d in enumerate(kd[:3]))
        self.res_drivers.config(text=drivers or "—")
        self.res_analysis.config(text=rsn or "—")
        self.res_signal.config(text=f'"{ms}"' if ms else "—")
        self.res_risk.config(text=risk or "—")

        self.result_placeholder.pack_forget()
        self.result_frame.pack(fill="both", expand=True)

    def _embed_chart(self, png_bytes: bytes) -> None:
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import matplotlib.pyplot as plt

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
