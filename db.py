"""
db.py
-----
Postgres (Supabase) storage layer for the expense tracker.

Table schema (auto-created on first run):

    CREATE TABLE txns (
        id          SERIAL PRIMARY KEY,
        date        DATE NOT NULL,
        category    VARCHAR(50) NOT NULL,
        amount      NUMERIC(12,2) NOT NULL,
        note        VARCHAR(255),
        type        VARCHAR(10) NOT NULL,   -- 'expense' | 'income'
        chat_id     BIGINT NOT NULL,
        created_at  TIMESTAMP NOT NULL
    );

Connection comes from the DATABASE_URL (or SUPABASE_DB_URL) environment
variable in production (Render), falling back to config.json -> "postgres"
for local development.

Requires: pip install psycopg2-binary
"""

import os
import json
import datetime
import psycopg2
import psycopg2.extras

CONFIG_PATH = "config.json"


def _load_local_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _get_dsn():
    """Prefer env-provided connection string (Render/Supabase), else config.json."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if url:
        return url

    cfg = _load_local_config()
    pg = cfg.get("postgres", {})
    host = pg.get("host", "127.0.0.1")
    port = pg.get("port", 5432)
    user = pg.get("user", "postgres")
    password = pg.get("password", "")
    database = pg.get("database", "expense_tracker")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def _connect():
    """Open a fresh Postgres connection. Caller is responsible for closing it."""
    return psycopg2.connect(_get_dsn())


def init_db():
    """Creates the txns table (if missing). Safe to call every time the app starts."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS txns (
            id          SERIAL PRIMARY KEY,
            date        DATE NOT NULL,
            category    VARCHAR(50) NOT NULL,
            amount      NUMERIC(12,2) NOT NULL,
            note        VARCHAR(255),
            type        VARCHAR(10) NOT NULL,
            chat_id     BIGINT NOT NULL,
            created_at  TIMESTAMP NOT NULL
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_date ON txns (date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chat ON txns (chat_id)")
    conn.commit()
    cur.close()
    conn.close()


def add(category, amount, note, txn_type, chat_id, date=None):
    """Insert one transaction. Returns the new row's id."""
    if date is None:
        date = datetime.date.today()
    now = datetime.datetime.now()

    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO txns (date, category, amount, note, type, chat_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (date, category, amount, note, txn_type, chat_id, now),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return new_id


def undo_last(chat_id):
    """
    Deletes the most recently added row for this chat_id.
    Returns the deleted row as a dict, or None if there was nothing to undo.
    """
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT * FROM txns
        WHERE chat_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (chat_id,),
    )
    row = cur.fetchone()
    if row:
        cur.execute("DELETE FROM txns WHERE id = %s", (row["id"],))
        conn.commit()
    cur.close()
    conn.close()
    return dict(row) if row else None


def all_rows():
    """Returns every transaction as a list of dicts, oldest first."""
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM txns ORDER BY date ASC, id ASC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def _month_bounds(month):
    """month: 'YYYY-MM' -> (first_day, first_day_of_next_month) as date objects."""
    year, mon = (int(x) for x in month.split("-"))
    first = datetime.date(year, mon, 1)
    if mon == 12:
        next_first = datetime.date(year + 1, 1, 1)
    else:
        next_first = datetime.date(year, mon + 1, 1)
    return first, next_first


def month_total(month, txn_type="expense"):
    """month: 'YYYY-MM' string. Returns the float total for that month."""
    first, next_first = _month_bounds(month)
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM txns
        WHERE date >= %s AND date < %s AND type = %s
        """,
        (first, next_first, txn_type),
    )
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    return float(total)


def category_totals(month, txn_type="expense"):
    """Returns {category: total} for the given month."""
    first, next_first = _month_bounds(month)
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT category, COALESCE(SUM(amount), 0)
        FROM txns
        WHERE date >= %s AND date < %s AND type = %s
        GROUP BY category
        """,
        (first, next_first, txn_type),
    )
    result = {cat: float(total) for cat, total in cur.fetchall()}
    cur.close()
    conn.close()
    return result


if __name__ == "__main__":
    # quick smoke test: init db, add a row, read it back, undo it
    init_db()
    print("DB initialised OK.")

    new_id = add("food", 420.0, "swiggy dinner", "expense", chat_id=12345)
    print("Inserted row id:", new_id)

    rows = all_rows()
    print("Total rows in table:", len(rows))

    this_month = datetime.date.today().strftime("%Y-%m")
    print("This month's expense total:", month_total(this_month))

    deleted = undo_last(12345)
    print("Undid row:", deleted)
