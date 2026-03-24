import json
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]

ALLOWED_USERS: set[int] = {
    int(uid.strip())
    for uid in os.environ["ALLOWED_USERS"].split(",")
    if uid.strip()
}

OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]

SPREADSHEET_ID: str = os.environ["SPREADSHEET_ID"]

GOOGLE_CREDENTIALS: dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
