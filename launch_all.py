"""
launch_all.py — Start Telegram Bot + GUI Dashboard simultaneously
"""
import sys, io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import threading
import subprocess
import time
import os

BASE = os.path.dirname(__file__)

def run_bot():
    """Run Telegram bot in subprocess."""
    print("[LAUNCHER] Starting Telegram bot...")
    subprocess.run([sys.executable, os.path.join(BASE, "rag_demo.py")])

def run_gui():
    """Run GUI dashboard in main thread."""
    print("[LAUNCHER] Starting GUI dashboard...")
    time.sleep(1)  # let bot start first
    import gui_app
    app = gui_app.RAGDashboard()
    app.mainloop()

if __name__ == "__main__":
    print("=" * 50)
    print("  RAG Financial Analysis - Full Launch")
    print("  Bot + Dashboard starting together...")
    print("=" * 50)

    # Bot runs in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # GUI runs in main thread (required for Tkinter)
    run_gui()
