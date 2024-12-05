import os

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

load_dotenv()
POSTGRES_USER = os.getenv("POSTGRES_USER", "admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "admin")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", 5432)
POSTGRES_DB = os.getenv("POSTGRES_DB", "spotify")


def get_engine() -> Engine:
    """
    Create an engine for SQLAlchemy

    Returns:
        Engine: The DB engine
    """
    engine = create_engine(
        f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )

    return engine


def get_db():
    """
    Get the database session object

    Yields:
        Session: Get the DB session
    """
    engine = get_engine()
    db = scoped_session(sessionmaker(bind=engine, autoflush=True))

    try:
        yield db
    finally:
        db.close()
