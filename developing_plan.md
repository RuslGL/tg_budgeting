# tg_budgeting — Development Plan

Track progress step by step. Check off each item as it's completed.

---

## Step 1 — Project scaffolding ✅ DONE
- [x] Create full directory + file structure with empty/stub files
- [x] Write `developing_plan.md` to project root

**Files created:**
```
tg_budgeting/
├── bot/
│   ├── __init__.py
│   ├── main.py               # entry point
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── voice.py
│   │   ├── text.py
│   │   └── commands.py
│   ├── middlewares/
│   │   ├── __init__.py
│   │   └── auth.py
│   └── states.py
├── services/
│   ├── __init__.py
│   ├── transcription.py
│   ├── llm.py
│   └── sheets.py
├── config.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── developing_plan.md
├── .env
└── .env.example
```

---

## Step 2 — Docker Compose ✅ DONE
- [x] Write `Dockerfile` (Python 3.11-slim, install deps, run bot)
- [x] Write `docker-compose.yml` (single `bot` service, env_file `.env`, restart `unless-stopped`)
- Note: all credentials including Google service account JSON stored in `.env` as a single-line string

---

## Step 3 — Config & environment wiring ✅ DONE
- [x] Write `config.py` — load and expose all env vars
- [x] Update `.env` and `.env.example` with all variables:
  - `BOT_TOKEN`
  - `ALLOWED_USERS` (comma-separated Telegram user IDs)
  - `OPENAI_API_KEY`
  - `SPREADSHEET_ID`
  - `GOOGLE_CREDENTIALS_JSON` (service account JSON as single-line string)
  - `LOG_LEVEL`
- Note: switched from OAuth2 to service account for Google Sheets auth

---

## Step 4 — Telegram bot skeleton
- [ ] `bot/main.py` — create `Bot`, `Dispatcher`, start polling
- [ ] `bot/handlers/commands.py` — `/start` and `/help` in Russian
- [ ] Register commands router in dispatcher
- [ ] **Test:** bot responds to `/start`

---

## Step 5 — Auth middleware
- [ ] `bot/middlewares/auth.py` — `BaseMiddleware` checking `message.from_user.id`
- [ ] Silently ignore messages from users not in `ALLOWED_USERS`
- [ ] Register middleware before all handlers
- [ ] **Test:** unknown user → bot ignores; allowed user → bot responds

---

## Step 6 — Voice transcription
- [ ] `services/transcription.py` — `async def transcribe(file_bytes: bytes) -> str` via OpenAI Whisper
- [ ] `bot/handlers/voice.py` — download OGG from Telegram, call transcribe, log result
- [ ] **Test:** send Russian voice note, verify transcribed text in logs

---

## Step 7 — LLM transaction parsing
- [ ] `services/llm.py` — `async def parse_transaction(text, categories, context) -> dict`
- [ ] Use GPT-4o-mini with function calling / structured output
- [ ] Schema: `{ amount, type, category, date, description, missing_fields[], clarifying_question? }`
- [ ] System prompt in Russian; pass available categories for matching
- [ ] **Test:** send "потратил 3000 на обед", verify parsed JSON

---

## Step 8 — Clarification FSM
- [ ] `bot/states.py` — define `Form.clarifying` state
- [ ] On incomplete parse: send `clarifying_question`, enter FSM state, store partial data
- [ ] Next message re-parsed with accumulated context
- [ ] Max 3 clarification rounds; on failure → ask user to rephrase
- [ ] **Test:** send "купил продукты" (no amount) → bot asks → user answers → complete

---

## Step 9 — Google Sheets integration
- [ ] `services/sheets.py` — service account auth via `gspread`
- [ ] `get_categories()` — read Categories tab, cache 10 min
- [ ] `append_transaction(row)` — append to Transactions tab
  - Columns: `Date | Type | Category | Amount | Description | Source | Added by`
- [ ] **Test:** full flow → verify row in Google Sheets

---

## Step 10 — Dashboard setup (manual, one-time)
- [ ] Create "Dashboard" tab in Google Sheets
- [ ] Insert bar chart: Income vs Expenses by month (from Transactions data)
- [ ] Insert pie chart: Category breakdown (SUMIF formulas)
- [ ] Insert yearly summary table
- [ ] Verify charts auto-update as new rows are added

---

## Step 11 — End-to-end testing & polish
- [ ] "потратил 3000 на обед" → row in Sheets
- [ ] Voice with complete info → row in Sheets
- [ ] Voice with missing amount → clarification → row in Sheets
- [ ] Unknown user → bot silent
- [ ] `/start` and `/help` work
- [ ] Error handling: API failures → friendly Russian message to user

---

## Step 12 — VPS deployment
- [ ] Copy project to VPS (git clone or scp)
- [ ] Place `.env` and `credentials.json` on server
- [ ] `docker compose up -d`
- [ ] Smoke test from real Telegram account
- [ ] Set up log monitoring: `docker compose logs -f`
