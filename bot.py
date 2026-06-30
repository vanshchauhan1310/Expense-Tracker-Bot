"""
bot.py
------
The Telegram bot. Every plain-text message is parsed and stored in Postgres
(Supabase). The dashboard reads transactions live via app.py's /api/data
endpoint, so there's nothing to regenerate after each message.

Commands:
    /start    - welcome + quick examples
    /help     - how to log expenses, list of commands
    /total    - this month's spend vs budget, with a text progress bar
    /undo     - delete the last entry you logged
    /budget   - show per-category budget caps

Requires: pip install python-telegram-bot psycopg2-binary
Run:      python bot.py   (or import main() from app.py to run in a thread)
"""

import os
import json
import logging
import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import db
import parser as msg_parser

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("expense_bot")

CONFIG_PATH = "config.json"


def load_config():
    """Local settings from config.json, with env vars overriding for deploys."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {}

    if os.environ.get("TELEGRAM_TOKEN"):
        cfg["telegram_token"] = os.environ["TELEGRAM_TOKEN"]
    if os.environ.get("MONTHLY_BUDGET"):
        cfg["monthlyBudget"] = float(os.environ["MONTHLY_BUDGET"])

    cfg.setdefault("currency", "₹")
    cfg.setdefault("monthlyBudget", 0)
    cfg.setdefault("budgets", {})
    return cfg


def fmt_money(amount, currency="₹"):
    """Indian-style grouping: ₹12,34,567 (last 3 digits, then groups of 2)."""
    amount = round(amount)
    s = str(abs(int(amount)))
    if len(s) <= 3:
        grouped = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        grouped = ",".join(parts) + "," + last3
    sign = "-" if amount < 0 else ""
    return f"{sign}{currency}{grouped}"


def progress_bar(spent, budget, width=14):
    if budget <= 0:
        return "[no budget set]"
    frac = min(spent / budget, 1.5)
    filled = min(int(round(frac * width)), width)
    bar = "█" * filled + "░" * (width - filled)
    pct = round((spent / budget) * 100) if budget else 0
    marker = " ⚠️ OVER BUDGET" if spent > budget else ""
    return f"[{bar}] {pct}%{marker}"


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Welcome to your personal expense tracker.*\n\n"
        "Just text me what you spent, in plain English:\n"
        "  • `spent 500 on ola`\n"
        "  • `swiggy 420 dinner`\n"
        "  • `1.5k myntra shirt`\n"
        "  • `got salary 75000`\n\n"
        "I'll figure out the amount + category and save it locally — "
        "nothing leaves this machine.\n\n"
        "Commands: /total  /undo  /budget  /help"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*How to log spending*\n"
        "Just send a normal sentence. Examples:\n"
        "  • `500 ola`\n"
        "  • `rs 1,250 electricity bill`\n"
        "  • `2l investment in stocks`\n"
        "  • `received cashback 45`\n\n"
        "Amounts understood: `500`, `1,250`, `1.5k` (=1500), `2l` (=2,00,000), "
        "`rs 500`, `₹500`, `500rs`.\n\n"
        "*Commands*\n"
        "/total — this month's spend vs budget\n"
        "/undo — remove the last entry\n"
        "/budget — show category budget caps\n\n"
        "Open `dashboard.html` any time (double-click it) for the full picture."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def total_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    currency = cfg.get("currency", "₹")
    month = datetime.date.today().strftime("%Y-%m")
    spent = db.month_total(month, "expense")
    budget = cfg.get("monthlyBudget", 0)

    bar = progress_bar(spent, budget)
    remaining = budget - spent
    remaining_txt = (
        f"{fmt_money(remaining, currency)} left" if remaining >= 0
        else f"{fmt_money(-remaining, currency)} over"
    )

    text = (
        f"📊 *{datetime.date.today().strftime('%B %Y')}*\n"
        f"Spent: {fmt_money(spent, currency)} / {fmt_money(budget, currency)}\n"
        f"{bar}\n"
        f"{remaining_txt}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def undo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    deleted = db.undo_last(chat_id)

    if not deleted:
        await update.message.reply_text("Nothing to undo — no entries logged yet.")
        return

    cfg = load_config()
    currency = cfg.get("currency", "₹")
    await update.message.reply_text(
        f"🗑️ Removed: {deleted['note']} — {fmt_money(float(deleted['amount']), currency)} "
        f"({deleted['category']})"
    )


async def budget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    currency = cfg.get("currency", "₹")
    budgets = cfg.get("budgets", {})
    month = datetime.date.today().strftime("%Y-%m")
    cat_totals = db.category_totals(month)

    lines = [f"💰 *Budget caps — {datetime.date.today().strftime('%B %Y')}*\n"]
    for cat, cap in budgets.items():
        spent = cat_totals.get(cat, 0.0)
        flag = " ⚠️" if spent > cap else ""
        lines.append(f"{cat:<12} {fmt_money(spent, currency)} / {fmt_money(cap, currency)}{flag}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Plain text -> parse -> store -> export -> reply
# ---------------------------------------------------------------------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    parsed = msg_parser.parse_message(text)
    if parsed is None:
        await update.message.reply_text(
            "I couldn't find an amount in that message. Try something like "
            "`spent 500 on ola` or `1.5k myntra shirt`.",
            parse_mode="Markdown",
        )
        return

    db.add(
        category=parsed["category"],
        amount=parsed["amount"],
        note=parsed["note"],
        txn_type=parsed["type"],
        chat_id=chat_id,
    )

    cfg = load_config()
    currency = cfg.get("currency", "₹")
    month = datetime.date.today().strftime("%Y-%m")

    if parsed["type"] == "income":
        reply = (
            f"💵 Logged income: {fmt_money(parsed['amount'], currency)} "
            f"({parsed['note']})"
        )
    else:
        spent = db.month_total(month, "expense")
        budget = cfg.get("monthlyBudget", 0)
        bar = progress_bar(spent, budget)
        reply = (
            f"✅ {fmt_money(parsed['amount'], currency)} → *{parsed['category']}* "
            f"({parsed['note']})\n"
            f"Month so far: {fmt_money(spent, currency)} / {fmt_money(budget, currency)}\n"
            f"{bar}"
        )

    await update.message.reply_text(reply, parse_mode="Markdown")


def main(run_in_thread=False):
    cfg = load_config()
    token = cfg.get("telegram_token", "")
    if not token or token.startswith("PUT_YOUR"):
        raise SystemExit(
            "No Telegram token found. Set the TELEGRAM_TOKEN env var "
            "(Render) or telegram_token in config.json (local dev)."
        )

    db.init_db()

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("total", total_cmd))
    app.add_handler(CommandHandler("undo", undo_cmd))
    app.add_handler(CommandHandler("budget", budget_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot started. Listening for messages...")
    # stop_signals=None: signal handlers can only be installed on the main
    # thread, and this is run inside a background thread when launched from
    # app.py alongside the Flask server.
    app.run_polling(stop_signals=None)


if __name__ == "__main__":
    main()
