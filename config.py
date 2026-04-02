import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")
INSTAGRAM_COOKIES = os.getenv("INSTAGRAM_COOKIES", "")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/scraper.db")

MAX_PROFILES_PER_RUN = int(os.getenv("MAX_PROFILES_PER_RUN", "15"))
MIN_DELAY_SECONDS = int(os.getenv("MIN_DELAY_SECONDS", "30"))
MAX_DELAY_SECONDS = int(os.getenv("MAX_DELAY_SECONDS", "60"))
MAX_SESSION_MINUTES = int(os.getenv("MAX_SESSION_MINUTES", "20"))
DELAY_BETWEEN_POSTS = int(os.getenv("DELAY_BETWEEN_POSTS", "8"))
MAX_DAYS = int(os.getenv("MAX_DAYS", "5"))
MAX_POSTS_PER_PROFILE = int(os.getenv("MAX_POSTS_PER_PROFILE", "6"))
SAFE_HOUR_START = int(os.getenv("SAFE_HOUR_START", "7"))
SAFE_HOUR_END = int(os.getenv("SAFE_HOUR_END", "23"))
