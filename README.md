# Expense Terminal — Telegram Bot + Offline Dashboard

A personal expense tracker you control 100% from Telegram.
Log spending in plain English → stored in MySQL → live offline HTML dashboard.
Zero cloud. Zero paid apps. Nothing leaves your machine.

---

## Architecture

```
[You]─Telegram──►[bot.py]──►[parser.py]──►[db.py / MySQL]
                     │                         │
                     └──►[export.py]◄──────────┘
                              │
                         [data.js]
                              │
                      [dashboard.html]  ← double-click to open
```

---

## Files

| File | Purpose |
|------|---------|
| `parser.py` | Turns a plain-English message into `{amount, category, note, type}` |
| `db.py` | MySQL storage — `add()`, `undo_last()`, `all_rows()`, `month_total()` |
| `export.py` | Dumps MySQL → `data.js` so the dashboard can read it offline |
| `bot.py` | Telegram bot wiring everything together |
| `config.json` | Token, MySQL credentials, budget caps (the only file you edit) |
| `dashboard.html` | Self-contained offline dashboard, no server, no internet needed |
| `test_parser.py` | 38 unit tests for the parser — run any time |

---

## Step-by-step Setup

### Step 1 — MySQL Setup

Install MySQL (or MariaDB) if you don't have it:

**Windows:**
Download MySQL Community Installer from https://dev.mysql.com/downloads/installer/
Select "MySQL Server" + "MySQL Shell" during installation. Default port 3306.

**macOS:**
```bash
brew install mysql
brew services start mysql
```

**Ubuntu/Debian Linux:**
```bash
sudo apt update && sudo apt install mysql-server -y
sudo systemctl start mysql
sudo systemctl enable mysql
```

**Create the database user** (run once in MySQL Shell or Workbench):

```sql
-- Connect as root first:
-- Windows: MySQL Shell → \connect root@localhost
-- Linux/Mac: sudo mysql -u root

CREATE USER 'expense_user'@'localhost' IDENTIFIED BY 'your_strong_password';
GRANT ALL PRIVILEGES ON expense_tracker.* TO 'expense_user'@'localhost';
-- If the above errors, try granting on all databases:
-- GRANT ALL PRIVILEGES ON *.* TO 'expense_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

The database `expense_tracker` and the `txns` table are created **automatically**
the first time you run `bot.py` — you do not need to create them manually.

---

### Step 2 — Get a Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow the prompts — give it a name and a username (must end in `bot`)
4. BotFather will give you a token like `7123456789:AAF...xYz`
5. Copy it — you'll paste it in the next step

---

### Step 3 — Edit config.json

Open `config.json` and fill in your values:

```json
{
  "telegram_token": "7123456789:AAF...xYz",
  "currency": "₹",
  "monthlyBudget": 40000,

  "mysql": {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "expense_user",
    "password": "your_strong_password",
    "database": "expense_tracker"
  },

  "budgets": {
    "travel": 3000,
    "food": 6000,
    "groceries": 5000,
    "clothes": 2500,
    "rent": 15000,
    "bills": 4000,
    "luxuries": 2000,
    "investments": 8000,
    "health": 2000,
    "education": 2000,
    "other": 1500
  }
}
```

**Never share this file** — it contains your bot token and DB password.

---

### Step 4 — Install Python dependencies

Requires Python 3.9+.

```bash
pip install python-telegram-bot mysql-connector-python
```

If you have multiple Python versions, use `pip3` or `python3 -m pip`.

---

### Step 5 — Run the bot

```bash
python bot.py
```

You should see:

```
INFO - Bot started. Listening for messages...
```

Leave this terminal open. The bot runs until you press `Ctrl+C`.

**To run in the background (Linux/Mac):**
```bash
nohup python bot.py &> bot.log &
```

---

### Step 6 — Open the dashboard

**Double-click `dashboard.html`** — it opens in your browser with no server needed.

`data.js` is regenerated after every transaction, so just **refresh the browser tab**
to see the latest data.

> **Tip:** If you open it before sending any messages, you'll see sample data
> so you can explore the layout immediately.

---

## Example Messages

Send these to your bot exactly as-is:

```
spent 500 on ola
swiggy 420 dinner
1.5k myntra shirt
got salary 75000
₹250 chai with friends
2l investment in stocks
rs 1,250 electricity bill
500rs petrol
received cashback 45
zomato 180 lunch
blinkit 1200 groceries
netflix 999
sip 5000 mutual fund
doctor 800 checkup
15000 rent
```

---

## Bot Commands

| Command | What it does |
|---------|-------------|
| `/start` | Welcome message + quick examples |
| `/help` | Full usage guide |
| `/total` | This month's spend vs budget with progress bar |
| `/undo` | Delete the last entry you logged |
| `/budget` | Show per-category spend vs caps |

---

## Amount Formats Understood

| You type | Parsed as |
|----------|-----------|
| `500` | ₹500 |
| `1,250` | ₹1,250 |
| `1.5k` | ₹1,500 |
| `2l` | ₹2,00,000 |
| `2L` | ₹2,00,000 |
| `rs 500` | ₹500 |
| `₹500` | ₹500 |
| `500rs` | ₹500 |
| `inr 800` | ₹800 |

---

## Category Keywords (edit `parser.py` freely)

| Category | Triggered by |
|----------|-------------|
| travel | ola, uber, rapido, metro, auto, petrol, cab, flight, irctc… |
| food | swiggy, zomato, dinner, lunch, chai, restaurant, pizza… |
| groceries | blinkit, zepto, bigbasket, dmart, vegetables, milk… |
| clothes | myntra, ajio, shirt, jeans, shoes, zara, h&m… |
| rent | rent, landlord, lease, maintenance… |
| bills | electricity, wifi, recharge, emi, jio, airtel… |
| luxuries | netflix, spotify, gym, movie, pvr, party, alcohol… |
| investments | sip, etf, stocks, groww, zerodha, fd, ppf… |
| health | doctor, medicine, pharmacy, hospital, apollo… |
| education | course, udemy, tuition, fees, book, exam… |
| other | anything not matched above |

---

## Running the Tests

```bash
python test_parser.py
```

Runs 38 unit tests covering amount parsing, category guessing, income detection,
and edge cases. All should show `OK`.

---

## Troubleshooting

**"telegram_token is not set"**
→ Open `config.json` and paste your BotFather token into `"telegram_token"`.

**MySQL connection refused**
→ Make sure MySQL is running: `sudo systemctl status mysql` (Linux) or check
Services on Windows. Verify `host`, `port`, `user`, `password` in `config.json`.

**"Access denied for user"**
→ Re-run the `GRANT ALL PRIVILEGES` SQL in Step 1, then `FLUSH PRIVILEGES`.

**dashboard.html shows sample data**
→ `data.js` hasn't been generated yet. Run `python export.py` or send one message
to the bot — it regenerates `data.js` automatically.

**Bot doesn't respond**
→ Make sure `python bot.py` is still running in your terminal.
Only one bot.py instance can run at a time with the same token.

**Amount not detected**
→ Make sure there's a number in your message: `ola 500`, `swiggy 420 dinner`, etc.

---

## Privacy & Data

- All data stays on your machine in MySQL.
- The only network traffic is between your device and Telegram's servers
  (the bot token + your messages). No third-party analytics, no cloud storage.
- `data.js` contains only your transaction amounts/notes/categories
  and your budget configuration. The bot token and MySQL password
  are **never written into** `data.js` or `dashboard.html`.

---

## Changing the Currency

1. Set `"currency"` in `config.json` (e.g. `"$"`, `"€"`, `"£"`).
2. Update the amount keywords in `parser.py` (`FILLER_WORDS` set) if needed.
3. The dashboard reads `currency` from `config.json` via `data.js` automatically.
