from datetime import date
from unittest import TestCase

from app import models

case = TestCase()
case.maxDiff = None


def test_album_repr():
    a = models.Album(
        spotify_id="1234abcd",
        artist_id="4321dcba",
        name="good album",
        release_date=date(2024, 12, 1),
    )
    expected = "<Album spotify_id=1234abcd artist_id=4321dcba name=good album release_date=2024-12-01>"

    case.assertEqual(expected, str(a))


def test_album_to_dict():
    a = models.album.Album(
        spotify_id="1234abcd",
        artist_id="4321dcba",
        name="good album",
        release_date=date(2024, 12, 1),
    )
    expected = {
        "spotify_id": "1234abcd",
        "artist_id": "4321dcba",
        "name": "good album",
        "release_date": date(2024, 12, 1),
    }

    case.assertDictEqual(expected, a.to_dict())


def test_artist_repr():
    a = models.Artist(spotify_id="123abc", name="good artist")
    expected = "<Artist spotify_id=123abc name=good artist>"

    case.assertEqual(expected, str(a))


def test_artist_to_dict():
    a = models.Artist(spotify_id="123abc", name="good artist")
    expected = {"spotify_id": "123abc", "name": "good artist"}

    case.assertDictEqual(expected, a.to_dict())


def test_playlist_repr():
    p = models.Playlist(spotify_id="123abc", user_id="user1", name="best songs")
    expected = "<Playlist spotify_id=123abc user_id=user1 name=best songs>"

    case.assertEqual(expected, str(p))


def test_playlist_to_dict():
    p = models.Playlist(spotify_id="123abc", user_id="user1", name="best songs")
    expected = {"spotify_id": "123abc", "user_id": "user1", "name": "best songs"}

    case.assertDictEqual(expected, p.to_dict())


def test_track_repr():
    t = models.Track(
        spotify_id="123abc",
        playlist_id="321cba",
        artist_id="abc123",
        album_id="cba321",
        name="song 2",
    )
    expected = "<Track id=None spotify_id=123abc playlist_id=321cba artist_id=abc123 album_id=cba321 name=song 2>"

    case.assertEqual(expected, str(t))


def test_track_to_dict():
    t = models.Track(
        spotify_id="123abc",
        playlist_id="321cba",
        artist_id="abc123",
        album_id="cba321",
        name="song 2",
    )
    expected = {
        "id": None,
        "spotify_id": "123abc",
        "playlist_id": "321cba",
        "artist_id": "abc123",
        "album_id": "cba321",
        "name": "song 2",
    }

    case.assertDictEqual(expected, t.to_dict())


def test_user_id_repr():
    u = models.UserID(user_id="123abc")
    expected = "<UserID user_id=123abc>"

    case.assertEqual(expected, str(u))


def test_user_id_to_dict():
    u = models.UserID(user_id="123abc")
    expected = {"user_id": "123abc"}

    case.assertDictEqual(expected, u.to_dict())
