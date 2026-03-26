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

---

## Step 13 — Notes notebook feature ✅ DONE

### 13a — Notes bot (bot_notes) ✅ DONE
- [x] `bot/handlers/notes.py` — text + voice handler, calls `process_note()`
- [x] `bot_notes_main.py` — entry point, registers commands.router + notes.router + AuthMiddleware
- [x] `bot/states.py` — added `NoteForm.clarifying_category`, `NoteForm.clarifying_date`
- [x] `services/llm.py` — added `parse_note(text, categories)` returning `{category, event_date}`
- [x] `services/sheets.py` — added `get_note_categories()`, `append_note()`, `delete_note()`
- [x] Categories read from "notes_categories" sheet (first column, no header, cached 10 min)
- [x] If category unknown → inline buttons (sorted alphabetically)
- [x] Confirmation message includes note text
- [x] Date always = today (recording date, not event date)
- [x] docker-compose.yml — added `bot_notes` service with `BOT_TOKEN_NOTES`
- [x] `.env.example` — added `BOT_TOKEN_NOTES`, `NOTES_SECRET`

### 13b — Notes dashboard ✅ DONE
- [x] `dashboard/api/notes_db.py` — SQLite: `init_notes_table`, `get_notes`, `get_note_categories`, `delete_note_local`
- [x] `dashboard/api/notes_sync.py` — full resync (DELETE all + INSERT all), every 10 seconds
- [x] `dashboard/api/main.py` — added NOTES_SECRET, `_notes_sync_loop` (10s), `/n/{secret}` endpoints
- [x] `dashboard/frontend/src/main.jsx` — URL routing: `/n/` → NotesApp, else → App
- [x] `dashboard/frontend/src/NotesApp.jsx` — light theme, category pills, date range filters, note cards with colored left border by category, trash icon, optimistic delete, auto-polling every 10s
- [x] Delete cascades: dashboard → Sheets + SQLite

### 13c — Google Calendar integration ✅ DONE
- [x] Google Calendar API enabled in Google Cloud project `tg-budgeting`
- [x] Primary calendar shared with service account `tg-budgeting-bot@tg-budgeting.iam.gserviceaccount.com`
- [x] `config.py` — added `GOOGLE_CALENDAR_ID`, `CALENDAR_CATEGORIES` (stored lowercase for case-insensitive match)
- [x] `services/sheets.py` — added Calendar scope, `_create_calendar_event()`, updated `append_note()` with `event_date`
- [x] `services/llm.py` — `parse_note()` now extracts `event_date` from message text; category assigned only if explicitly mentioned in text
- [x] `bot/handlers/notes.py` — if category is calendar type and no date found → FSM `NoteForm.clarifying_date`
- [x] `dashboard/api/notes_db.py` — added `calendar_event_id` column with migration
- [x] `dashboard/api/notes_sync.py` — syncs 5 columns; `delete_note_from_sheets()` also deletes Google Calendar event
- [x] `requirements.txt` + `dashboard/api/requirements.txt` — added `google-api-python-client`
- [x] `.env` — added `GOOGLE_CALENDAR_ID=ruslanglotov@gmail.com`
- [x] `.env.example` — added `GOOGLE_CALENDAR_ID`, `CALENDAR_CATEGORIES`
- [x] Google Sheets "notes" tab: column E = `calendar_event_id` (no header row)

---

## Step 14 — UI polish & logging ✅ DONE

### 14a — Notes dashboard redesign ✅ DONE
- [x] `NotesApp.jsx` — dark/light theme toggle with localStorage persistence
- [x] Dark theme: purple-blue gradient (`#1C1B2E → #16213E`), pink accents (`#E8649A`), `rgba` cards
- [x] Light theme: `#F0F2F8` background, white cards with shadow
- [x] Theme toggle: pill switch with moon/sun icon, purple knob (dark) / yellow knob (light)
- [x] "Все" pill — distinct neutral grey, does not clash with category colors
- [x] `body` background set to dark in `index.html` — no white gaps on wide screens
- [x] `colorScheme: dark/light` on date inputs — native picker matches theme

### 14b — Favicons ✅ DONE
- [x] `dashboard/frontend/public/favicon-notes.svg` — pink notebook icon
- [x] `dashboard/frontend/public/favicon-budget.svg` — blue/purple bar chart icon
- [x] `docs/favicon-arch.svg` — network graph icon
- [x] `main.jsx` — sets favicon and `document.title` based on route (`/n/` vs `/d/`)
- [x] FastAPI `/n/{secret}` — injects `favicon-notes.svg` link into HTML before serving
- [x] FastAPI routes for `/favicon-notes.svg` and `/favicon-budget.svg`
- [x] `docs/architecture.html` — renamed to "TG Agents Architecture", favicon linked

### 14c — Logging cleanup ✅ DONE
- [x] `bot_notes_main.py` — suppressed `httpx` and `aiogram.event` INFO logs
- [x] `dashboard/api/notes_sync.py` — notes sync log moved to DEBUG level
- [x] `dashboard/api/main.py` — notes sync complete log moved to DEBUG level
- [x] `dashboard/Dockerfile` — uvicorn `--no-access-log` to hide HTTP request lines
