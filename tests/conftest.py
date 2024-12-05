import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from app import app
from app.database import get_db
from app.models import Album, Artist, Base, Playlist, Track, UserID


@pytest.fixture()
def test_db():
    """
    An in-memory test DB

    Yields:
        _type_: Session
    """
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    connection = engine.connect()

    db = scoped_session(sessionmaker(bind=connection, autoflush=True))
    Base.metadata.create_all(bind=engine)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        connection.close()


@pytest.fixture()
def test_client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            test_db.close()

    app.app.dependency_overrides[get_db] = override_get_db

    with TestClient(app.app) as client:
        yield client

    app.app.dependency_overrides.clear()


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


@pytest.fixture()
def seeded_test_db(test_db) -> Session:
    test_db.add_all([UserID(user_id="user1"), UserID(user_id="user2")])
    test_db.add_all(
        [
            Playlist(spotify_id="playlist_id1", user_id="user1", name="playlist1"),
            Playlist(spotify_id="playlist_id2", user_id="user1", name="playlist2"),
            Playlist(spotify_id="playlist_id3", user_id="user2", name="playlist3"),
        ]
    )

    test_db.add_all(
        [
            Artist(spotify_id="artist_id1", name="artist1"),
            Artist(spotify_id="artist_id2", name="artist2"),
            Artist(spotify_id="artist_id3", name="artist3"),
        ]
    )
    test_db.flush()
    test_db.add_all(
        [
            Album(
                spotify_id="album_id1",
                artist_id="artist_id1",
                name="album1",
                release_date=datetime.date(2024, 12, 5),
            ),
            Album(
                spotify_id="album_id2",
                artist_id="artist_id1",
                name="album2",
                release_date=datetime.date(2024, 10, 1),
            ),
            Album(
                spotify_id="album_id3",
                artist_id="artist_id2",
                name="album3",
                release_date=datetime.date(2024, 12, 5),
            ),
            Album(
                spotify_id="album_id4",
                artist_id="artist_id3",
                name="album4",
                release_date=datetime.date(2024, 12, 5),
            ),
            Album(
                spotify_id="album_id5",
                artist_id="artist_id3",
                name="album5",
                release_date=datetime.date(2024, 12, 5),
            ),
        ]
    )

    test_db.add_all(
        [
            Track(
                id=1,
                spotify_id="track_id1",
                playlist_id="playlist_id1",
                artist_id="artist_id1",
                album_id="album_id1",
                name="track1",
            ),
            Track(
                id=2,
                spotify_id="track_id2",
                playlist_id="playlist_id1",
                artist_id="artist_id1",
                album_id="album_id1",
                name="track2",
            ),
            Track(
                id=3,
                spotify_id="track_id3",
                playlist_id="playlist_id1",
                artist_id="artist_id1",
                album_id="album_id2",
                name="track3",
            ),
            Track(
                id=4,
                spotify_id="track_id4",
                playlist_id="playlist_id2",
                artist_id="artist_id1",
                album_id="album_id2",
                name="track4",
            ),
            Track(
                id=5,
                spotify_id="track_id5",
                playlist_id="playlist_id2",
                artist_id="artist_id2",
                album_id="album_id3",
                name="track5",
            ),
            Track(
                id=6,
                spotify_id="track_id6",
                playlist_id="playlist_id3",
                artist_id="artist_id3",
                album_id="album_id5",
                name="track6",
            ),
            Track(
                id=7,
                spotify_id="track_id7",
                playlist_id="playlist_id3",
                artist_id="artist_id3",
                album_id="album_id4",
                name="track7",
            ),
        ]
    )

    test_db.commit()
    return test_db
