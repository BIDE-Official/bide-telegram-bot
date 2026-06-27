from os import getenv
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

BOT_TOKEN = getenv("BOT_TOKEN", "")
SPREADSHEET_ID = getenv("SPREADSHEET_ID", "")
GOOGLE_CREDENTIALS = getenv("GOOGLE_CREDENTIALS", "credentials/service_account.json")
