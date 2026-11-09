import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DB_URL        = os.environ.get("DATABASE_URL", "dbname=aipartner")
CHROMA_DIR    = os.environ.get("CHROMA_DIR", str(ROOT / "chroma_db"))
SESSIONS_DIR  = os.environ.get("SESSIONS_DIR", str(ROOT / "sessions"))
BASE_URL      = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]

ENABLE_RERANK = os.environ.get("ENABLE_RERANK", "1") == "1"