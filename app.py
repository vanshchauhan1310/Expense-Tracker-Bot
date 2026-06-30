"""
app.py
------
Flask web server for the expense tracker.

- Serves dashboard.html at "/" (useful for local dev / running everything
  on a single host; in production the dashboard is deployed separately on
  Vercel and talks to this API over HTTPS via fetch()).
- Exposes GET /api/data -> {transactions: [...], config: {...}}, live from
  Supabase Postgres. Never includes the Telegram token or DB credentials.
- Runs the Telegram bot's polling loop in a background thread so one
  process (and one Render service) serves both.

Run:  python app.py
"""

import os
import asyncio
import logging
import threading

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

import db
import bot as bot_module

logger = logging.getLogger("expense_app")

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)  # dashboard is hosted on a different origin (Vercel) in production


@app.route("/")
def index():
    return send_from_directory(".", "dashboard.html")


@app.route("/api/data")
def api_data():
    rows = db.all_rows()
    transactions = [
        {
            "id": r["id"],
            "date": r["date"].isoformat() if hasattr(r["date"], "isoformat") else str(r["date"]),
            "category": r["category"],
            "amount": float(r["amount"]),
            "note": r["note"] or "",
            "type": r["type"],
        }
        for r in rows
    ]

    cfg = bot_module.load_config()
    public_config = {
        "currency": cfg.get("currency", "₹"),
        "monthlyBudget": cfg.get("monthlyBudget", 0),
        "budgets": cfg.get("budgets", {}),
        "categories": list(cfg.get("budgets", {}).keys()),
    }

    return jsonify({"transactions": transactions, "config": public_config})


def _run_bot():
    # Each thread needs its own asyncio event loop for python-telegram-bot.
    asyncio.set_event_loop(asyncio.new_event_loop())
    try:
        bot_module.main(run_in_thread=True)
    except Exception:
        logger.exception("Telegram bot crashed")


if __name__ == "__main__":
    db.init_db()

    bot_thread = threading.Thread(target=_run_bot, daemon=True)
    bot_thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
