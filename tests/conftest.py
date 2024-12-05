from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker

from app import app
from app.models import Base


@pytest.fixture()
def test_db():
    """
    An in-memory test DB

    Yields:
        _type_: Session
    """
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    db = scoped_session(sessionmaker(bind=engine, autoflush=True))
    Base.metadata.create_all(bind=engine)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def test_client():
    return TestClient(app.app)


@pytest.fixture(scope="session")
def test_client_sesssion():
    return TestClient(app.app)


@pytest.fixture()
def mock_request():
    def real_mock_request(
        refresh_token: str = None,
        access_token: str = None,
        expiration_time: str | int = None,
        code: str = None,
        state: str = None,
        error: str = None,
    ) -> dict:
        """
        Factory to make a fixture for a mocked request for reusable testing.

        Args:
            refresh_token (str, optional): Defaults to None.
            access_token (str, optional): Defaults to None.
            expiration_time (str | int, optional): Defaults to None.
            code (str, optional): Defaults to None.
            state (str, optional): Defaults to None.
            error (str, optional): Defaults to None.

        Returns:
            dict: Mocked request with session as dict
        """
        mock_request = MagicMock(spec=Request)

        mock_request.session = {
            "refresh_token": refresh_token,
            "access_token": access_token,
            "expiration_time": expiration_time,
            "code": code,
            "state": state,
            "error": error,
        }

        return mock_request

    return real_mock_request
