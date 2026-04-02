from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import BASE_DIR, DATABASE_URL

if DATABASE_URL.startswith("sqlite"):
    (BASE_DIR / "data").mkdir(exist_ok=True)


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import ScrapedPost, ScrapingProfile  # noqa: F401

    Base.metadata.create_all(bind=engine)
