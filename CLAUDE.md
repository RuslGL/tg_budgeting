Прочитай CLAUDE.md, developing_plan.md и файлы в memory/. Потом скажи что сейчас в проекте и что делаем дальше.

# CLAUDE.md — Project Rules

## Development workflow

- Follow `developing_plan.md` strictly, one step at a time.
- Do not start coding a step until the user explicitly says to proceed.
- After completing a step, stop and wait for the user to confirm before moving to the next.
- After each completed step, mark it as done in `developing_plan.md`.
- After each completed step, commit and push to git with a short, plain English message (no emojis, no symbols).

## Before coding

- Discuss the approach with the user before writing any code.
- If anything is unclear or has multiple valid approaches, ask — do not assume.
- Read existing files before modifying them.

## Code style

- No emojis, symbols, or decorative characters in any files, commit messages, or bot responses.
- Keep code simple and focused on the current step only. Do not add features ahead of schedule.
- All bot-facing text (messages, prompts, errors) must be in Russian.

## Tech stack (fixed)

- Telegram: `aiogram` v3
- Voice transcription: OpenAI Whisper API
- Parsing and clarification: `gpt-4o-mini` with function calling (sufficient for structured extraction from short Russian phrases)
- Google Sheets: `gspread` + `google-auth` (service account)
- Config: `python-dotenv`
- Runtime: Python 3.11+, async
- Dashboard: FastAPI + SQLite + React/Vite + recharts, multi-stage Docker build

## Architecture decisions (settled)

- Two bots: `bot` (family) and `bot_corp` (business), same codebase, different env vars per docker-compose service.
- `bot_corp_main.py` is the entry point for the second bot; it reuses all handlers from `bot/`.
- Google Sheets `raw` tab columns: `date | category | type | amount | original_text | author | company`.
- `categories` sheet for family bot, `corp_categories` sheet for business bot (set via `CATEGORIES_SHEET` env var).
- `USERS_NAME` env var maps `ALLOWED_USERS` order to display names (comma-separated, same order).
- Dashboard SQLite is synced hourly from Sheets; only current + previous month are rewritten, older history is untouched.
- Dashboard filtered by `company` query param on all endpoints; frontend has "БЮДЖЕТ СЕМЕЙНЫЙ / БЮДЖЕТ БИЗНЕС" dropdown.
- Allowed users are stored as comma-separated Telegram numeric user IDs in `.env` under `ALLOWED_USERS`.
- Deployment: VPS with long-polling (`docker compose up -d`).
