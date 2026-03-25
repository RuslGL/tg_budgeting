import json
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]

_allowed_list = [int(uid.strip()) for uid in os.environ["ALLOWED_USERS"].split(",") if uid.strip()]
_names_list = [n.strip() for n in os.getenv("USERS_NAME", "").split(",") if n.strip()]

ALLOWED_USERS: set[int] = set(_allowed_list)
USER_NAMES: dict[int, str] = dict(zip(_allowed_list, _names_list))

OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]

SPREADSHEET_ID: str = os.environ["SPREADSHEET_ID"]

GOOGLE_CREDENTIALS: dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

COMPANY: str = os.getenv("COMPANY", "family")
CATEGORIES_SHEET: str = os.getenv("CATEGORIES_SHEET", "categories")
