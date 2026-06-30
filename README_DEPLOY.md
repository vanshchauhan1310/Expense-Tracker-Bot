# Deploying: Render (backend + bot) + Vercel (dashboard) + Supabase (DB)

Architecture:
- **Supabase** — hosted Postgres database, stores all transactions.
- **Render** — runs `app.py` (Flask API + the Telegram bot, in one process).
- **Vercel** — hosts `dashboard.html` as a static site, which calls the Render API.

## 1. Create the Supabase database

1. Sign up at supabase.com and create a new project (free tier).
2. Go to **Project Settings → Database → Connection string → URI**. Copy it —
   it looks like `postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres`.
3. You don't need to create any tables manually — `app.py` calls `db.init_db()`
   on startup and creates the `txns` table if it's missing.

## 2. Push this project to GitHub

Render and Vercel both deploy from a GitHub repo. `config.json` is in
`.gitignore` so your real token/password never get committed — only
`config.json`'s structure is implied by `.env.example`.

```
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

## 3. Deploy the backend on Render

1. Sign up at render.com, click **New → Web Service**, connect your GitHub repo.
2. Render should detect `render.yaml` automatically (Python web service,
   build command `pip install -r requirements.txt`, start command `python app.py`).
3. Under **Environment**, set:
   - `TELEGRAM_TOKEN` — your token from @BotFather
   - `DATABASE_URL` — the Supabase connection string from step 1
   - `MONTHLY_BUDGET` — optional, defaults to whatever's in `config.json`
   - `PORT` — Render sets this automatically; you don't need to add it
4. Deploy. Once live, your API is at `https://<your-service>.onrender.com`.
   Test it: open `https://<your-service>.onrender.com/api/data` — you should
   see `{"transactions": [...], "config": {...}}`.

   Note: Render's free tier spins down after inactivity, so the bot may take
   ~30s to respond to the first message after idling.

## 4. Deploy the dashboard on Vercel

1. Edit `env.js` in this repo and set:
   ```js
   window.EXPENSE_API_BASE = "https://<your-service>.onrender.com";
   ```
   Commit and push that change.
2. Sign up at vercel.com, click **New Project**, import the same GitHub repo.
3. Framework preset: **Other** (static site). No build command needed —
   Vercel will serve `dashboard.html`, `env.js`, etc. directly (`vercel.json`
   routes `/` to `dashboard.html`).
4. Deploy. Your public dashboard URL will be `https://<your-project>.vercel.app`.

## 5. Verify

- Message your bot on Telegram — `/start`, then log an expense like `500 ola`.
- Open the Vercel dashboard URL — the transaction should appear within a
  page refresh (no redeploy needed, it's a live fetch).
- Try `/total`, `/undo`, `/budget`, `/help` in Telegram.

## 6. Redeploying after changes

Both Render and Vercel auto-deploy on every push to your repo's main branch:

```
git add .
git commit -m "describe your change"
git push
```

Render rebuilds the backend; Vercel rebuilds the dashboard. No manual steps
needed unless you changed environment variables (update those in each
platform's dashboard, they aren't read from git).

## Local development

You can still run everything on your machine without touching Render/Vercel:

1. Copy `config.json`'s `telegram_token` and add a `"postgres"` block
   (or just export `DATABASE_URL` pointing at your Supabase project — it
   works the same locally and in production).
2. `pip install -r requirements.txt`
3. `python app.py` — serves the dashboard at `http://localhost:5000` and
   runs the bot in the background, same process.
