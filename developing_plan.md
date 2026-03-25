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

## Step 4 — Telegram bot skeleton ✅ DONE
- [x] `bot/main.py` — create `Bot`, `Dispatcher`, start polling
- [x] `bot/handlers/commands.py` — `/start` and `/help` in Russian
- [x] Register commands router in dispatcher
- [x] **Test:** bot responds to `/start`

---

## Step 5 — Auth middleware ✅ DONE
- [x] `bot/middlewares/auth.py` — `BaseMiddleware` checking `message.from_user.id`
- [x] Silently ignore messages from users not in `ALLOWED_USERS`
- [x] Register middleware before all handlers
- [x] **Test:** unknown user → bot ignores; allowed user → bot responds

---

## Step 6 — Voice transcription ✅ DONE
- [x] `services/transcription.py` — `async def transcribe(file_bytes: bytes) -> str` via OpenAI Whisper
- [x] `bot/handlers/voice.py` — download OGG from Telegram, call transcribe, pass to process_transaction
- [x] Shared `process_transaction` logic extracted to `text.py` and reused by voice handler
- [x] **Test:** send Russian voice note, verify transcribed text in logs

---

## Step 7 — LLM transaction parsing ✅ DONE
- [x] `services/llm.py` — `async def parse_transaction(text, categories) -> dict`
- [x] GPT-4o-mini with JSON response format
- [x] Schema: `{ amount, category, date, missing[] }`
- [x] System prompt in Russian; pass available categories for matching
- [x] Strict category matching — "unknown" if no clear match
- [x] Date parsing: supports "вчера", "позавчера", explicit dates

---

## Step 8 — Clarification FSM ✅ DONE
- [x] `bot/states.py` — `Form.clarifying_amount` and `Form.clarifying_category` states
- [x] Both amount and category missing → ask to rephrase, no FSM state saved
- [x] Amount missing → FSM clarifying_amount, max 3 attempts, 5 min timeout, then drop
- [x] Category missing → FSM clarifying_category, inline keyboard with all categories, accept voice too
- [x] Max 3 clarification rounds for category → write `unknown` and save
- [x] Timeout 5 min → clear state, ask to resend
- [x] **Test:** send message without amount → bot asks → user answers → complete

---

## Step 9 — Google Sheets integration ✅ DONE
- [x] `services/sheets.py` — service account auth via `gspread`
- [x] `get_categories()` — reads sheet from `CATEGORIES_SHEET` env var, cache 10 min
- [x] `append_transaction(date, category, amount, original_text, author, company)` — append to "raw" tab
  - Columns: `date | category | type | amount | original text | author | company`
- [x] **Test:** full flow → verify row in Google Sheets

---

## Step 10 — React dashboard with SQLite sync ✅ DONE
- [x] `dashboard/api/sync.py` — Sheets → SQLite, hourly; rewrites only current + previous month, history untouched
- [x] `dashboard/api/db.py` — SQLite reads: months list, category breakdown by month/year, by-author breakdown; all queries filtered by `company`
- [x] `dashboard/api/main.py` — FastAPI: serves React static + endpoints under `DASHBOARD_SECRET`
  - `GET /d/{secret}/api/months?company=`
  - `GET /d/{secret}/api/month?year=&month=&company=`
  - `GET /d/{secret}/api/year?year=&company=`
  - `GET /d/{secret}/api/month/by-author?year=&month=&company=`
  - `GET /d/{secret}/api/year/by-author?year=&company=`
- [x] `dashboard/frontend/` — React + Vite, dark fintech theme:
  - Dropdown selector: "БЮДЖЕТ СЕМЕЙНЫЙ" / "БЮДЖЕТ БИЗНЕС" (filters all data by company)
  - Separate year / month selectors
  - Two pie charts (month + year) with stats (доход / расходы / разница) and category table
  - Two bar charts (month + year) showing expense breakdown by author
- [x] `dashboard/Dockerfile` — multi-stage: Node build → Python runtime
- [x] `dashboard` service added to `docker-compose.yml`, port 8080
- [x] `DASHBOARD_SECRET` added to `.env` and `.env.example`
- [x] SQLite schema: `date, category, type, amount, author, company`

---

## Step 10a — Second bot and multi-company support ✅ DONE
- [x] `bot_corp_main.py` — entry point for second bot, reuses all handlers from `bot/`
- [x] `docker-compose.yml` — `bot_corp` service: `BOT_TOKEN_CORP`, `COMPANY=business`, `CATEGORIES_SHEET=corp_categories`
- [x] `config.py` — added `COMPANY`, `CATEGORIES_SHEET`, `USER_NAMES` (maps Telegram ID → display name)
- [x] `services/sheets.py` — `CATEGORIES_SHEET` is now configurable; `author` and `company` written to raw sheet
- [x] `bot/handlers/text.py` — reads `author` from `USER_NAMES`, `company` from `COMPANY`; stores both in FSM state
- [x] `bot/handlers/clarification.py` — all append_transaction calls pass `author` and `company` from FSM state
- [x] `bot/handlers/voice.py` — fixed: added `F.voice` filter so voice handler no longer intercepts text messages
- [x] `.env.example` — added `BOT_TOKEN_CORP`, `USERS_NAME`

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
- [ ] Place `.env` on server
- [ ] `docker compose up -d`
- [ ] Smoke test from real Telegram account
- [ ] Set up log monitoring: `docker compose logs -f`
- [ ] Configure systemd service so docker compose restarts automatically on server reboot
