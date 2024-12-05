import csv
import io
import json
from unittest import TestCase, mock

from fastapi.responses import JSONResponse

case = TestCase()
case.maxDiff = None


@mock.patch("app.app.requests.post")
def test_get_access_token(mock_post, test_client):
    mock_post.return_value.json.return_value = {"data": "value"}
    actual = test_client.get("/getAccessToken", params={"code": "123"})

    case.assertEqual(200, actual.status_code)
    case.assertDictEqual({"data": "value"}, actual.json())

    actual_data = mock_post.call_args.kwargs.get("data")

    case.assertIsNotNone(actual_data)
    case.assertEqual("123", actual_data.get("code"))


@mock.patch("app.app.secrets.token_urlsafe", return_value="1234")
def test_get_user_auth__no_next_url(mock_secret, test_client):
    actual = test_client.get("/authorize", follow_redirects=False)

    case.assertEqual(307, actual.status_code)
    case.assertEqual("1234:", actual.headers.get("location")[-5:])


@mock.patch("app.app.secrets.token_urlsafe", return_value="1234")
def test_get_user_auth__with_next_url(mock_secret, test_client):
    actual = test_client.get(
        "/authorize", params={"next_url": "/nextUrlToVisit"}, follow_redirects=False
    )

    case.assertEqual(307, actual.status_code)
    case.assertIn("state=1234:/nextUrlToVisit", actual.headers.get("location"))


def test_callback__with_error(test_client):
    actual = test_client.get("/callback", params={"error": "Insufficient permissions"})

    expected = {"detail": 'Failed due to "Insufficient permissions"'}

    case.assertEqual(401, actual.status_code)
    case.assertEqual(expected, actual.json())


@mock.patch(
    "app.app.Request.session",
    new_callable=mock.PropertyMock,
)
def test_callback__with_mismatched_state(mr, test_client):
    mr.return_value = {"state": "123"}
    actual = test_client.get("/callback", params={"code": "abc", "state": "321"})

    expected = {"detail": "State mismatch! Expected 123 but got 321"}

    case.assertEqual(401, actual.status_code)
    case.assertEqual(expected, actual.json())


def test_callback__with_no_code(test_client):
    actual = test_client.get("/callback")

    expected = {"detail": "Failed to receive code from Spotify; please try again"}

    case.assertEqual(401, actual.status_code)
    case.assertEqual(
        expected,
        actual.json(),
    )


@mock.patch(
    "app.app.Request.session",
    new_callable=mock.PropertyMock,
)
@mock.patch("app.app.get_access_token")
def test_callback__standard(mock_get_access_token, mr, test_client):
    mock_get_access_token.return_value = {
        "access_token": "abc",
        "expires_in": "3600",
        "refresh_token": "def",
    }
    mr.return_value = {"state": "123:/sync"}
    actual = test_client.get(
        "/callback",
        params={
            "code": "abc",
            "state": "123:/sync",
        },
        follow_redirects=False,
    )

    case.assertEqual(307, actual.status_code)
    case.assertEqual("/sync", actual.headers.get("location"))


@mock.patch(
    "app.app.Request.session",
    new_callable=mock.PropertyMock,
)
@mock.patch("app.app.get_access_token")
def test_callback__standard_no_refresh_token(mock_get_access_token, mr, test_client):
    mock_get_access_token.return_value = {
        "access_token": "abc",
        "expires_in": "3600",
    }
    mr.return_value = {"state": "123:/sync"}
    actual = test_client.get(
        "/callback",
        params={
            "code": "abc",
            "state": "123:/sync",
        },
        follow_redirects=False,
    )

    case.assertEqual(307, actual.status_code)
    case.assertEqual("/sync", actual.headers.get("location"))


@mock.patch("app.app.utils")
def test_sync(mock_utils, test_client):
    actual = test_client.get("/sync")

    case.assertEqual(200, actual.status_code)
    case.assertEqual("Successfully synced", actual.content.decode("utf-8"))

    mock_utils.add_or_get_user.assert_called_once()
    mock_utils.clean_tables.assert_called_once()
    mock_utils.sync_playlists.assert_called_once()
    mock_utils.sync_tracks.assert_called_once()


def test_get_tracks_db(test_client):
    actual = test_client.get("/getTracksFromPlaylistDB", params={"playlist_id": "123"})

    case.assertEqual(200, actual.status_code)
    case.assertEqual("application/json", actual.headers.get("Content-Type"))


@mock.patch("app.app.freq")
@mock.patch("app.app.utils.add_or_get_user", return_value="user")
def test_get_frequent__tracks(mock_user, mock_freq, test_client):
    mock_freq.return_value.getvalue.return_value = None
    actual = test_client.get(
        "/getFrequent", params={"user": "user", "media_type": "tracks"}
    )

    case.assertEqual(200, actual.status_code)
    case.assertEqual("image/png", actual.headers.get("Content-Type"))


@mock.patch("app.app.freq")
@mock.patch("app.app.utils.add_or_get_user", return_value="user")
def test_get_frequent__artists(mock_user, mock_freq, test_client):
    mock_freq.return_value.getvalue.return_value = None
    actual = test_client.get(
        "/getFrequent", params={"user": "user", "media_type": "artists"}
    )

    case.assertEqual(200, actual.status_code)
    case.assertEqual("image/png", actual.headers.get("Content-Type"))


@mock.patch("app.app.freq")
@mock.patch("app.app.utils.add_or_get_user", return_value="user")
def test_get_frequent__albums(mock_user, mock_freq, test_client):
    mock_freq.return_value.getvalue.return_value = None
    actual = test_client.get(
        "/getFrequent", params={"user": "user", "media_type": "albums"}
    )

    case.assertEqual(200, actual.status_code)
    case.assertEqual("image/png", actual.headers.get("Content-Type"))


@mock.patch("app.app.freq")
@mock.patch("app.app.utils.add_or_get_user", return_value="user")
def test_get_frequent__bad_media_type(mock_user, mock_freq, test_client):
    mock_freq.return_value.getvalue.return_value = None
    actual = test_client.get(
        "/getFrequent", params={"user": "user", "media_type": "invalid_type"}
    )

    case.assertEqual(422, actual.status_code)
    case.assertEqual(
        "Input should be 'tracks', 'artists' or 'albums'",
        actual.json().get("detail")[0].get("msg"),
    )


@mock.patch("app.app.utils.get_auth")
@mock.patch("app.app.utils.get_user_id", return_value="user1")
def test_get_report__no_user_provided(
    mock_get_user, mock_get_auth, test_client, seeded_test_db
):
    actual = test_client.get("/report").content.decode("utf-8").splitlines()

    expected = [
        "playlist_name,track_name,artist_name,album_name,album_release_date,playlist_spotify_id,track_spotify_id,artist_spotify_id,album_spotify_id",
        "playlist1,track1,artist1,album1,2024-12-05,playlist_id1,track_id1,artist_id1,album_id1",
        "playlist1,track2,artist1,album1,2024-12-05,playlist_id1,track_id2,artist_id1,album_id1",
        "playlist1,track3,artist1,album2,2024-10-01,playlist_id1,track_id3,artist_id1,album_id2",
        "playlist2,track4,artist1,album2,2024-10-01,playlist_id2,track_id4,artist_id1,album_id2",
        "playlist2,track5,artist2,album3,2024-12-05,playlist_id2,track_id5,artist_id2,album_id3",
    ]

    case.assertEqual(expected, actual)


@mock.patch("app.app.utils.get_auth")
@mock.patch("app.app.utils.get_user_id", return_value="user1")
def test_get_report__user_provided(
    mock_get_user, mock_get_auth, test_client, seeded_test_db
):
    actual = (
        test_client.get("/report", params={"user": "user1"})
        .content.decode("utf-8")
        .splitlines()
    )

    expected = [
        "playlist_name,track_name,artist_name,album_name,album_release_date,playlist_spotify_id,track_spotify_id,artist_spotify_id,album_spotify_id",
        "playlist1,track1,artist1,album1,2024-12-05,playlist_id1,track_id1,artist_id1,album_id1",
        "playlist1,track2,artist1,album1,2024-12-05,playlist_id1,track_id2,artist_id1,album_id1",
        "playlist1,track3,artist1,album2,2024-10-01,playlist_id1,track_id3,artist_id1,album_id2",
        "playlist2,track4,artist1,album2,2024-10-01,playlist_id2,track_id4,artist_id1,album_id2",
        "playlist2,track5,artist2,album3,2024-12-05,playlist_id2,track_id5,artist_id2,album_id3",
    ]

    case.assertEqual(expected, actual)


@mock.patch("app.app.utils.get_auth")
@mock.patch("app.app.utils.get_user_id", return_value="user1")
def test_get_report__user_not_found(
    mock_get_user, mock_get_auth, test_client, seeded_test_db
):
    actual = test_client.get("/report", params={"user": "not user"})

    case.assertEqual(404, actual.status_code)
    case.assertEqual(
        {"detail": 'User "not user" not found; nothing to generate'}, actual.json()
    )


@mock.patch("app.app.time.time", return_value=1733144400.0)
@mock.patch(
    "app.app.Request.session",
    new_callable=mock.PropertyMock,
)
def test_debug(mr, mock_time, test_client):
    mr.return_value = {
        "access_token": "123",
        "refresh_token": "321",
        "expiration_time": "1733144500.123",
    }
    actual = test_client.get("/debug")

    expected = {
        "access_token": "123",
        "refresh_token": "321",
        "expiration_time": "2024-12-02T07:01:40-06:00",
        "expired": False,
    }

    case.assertEqual(200, actual.status_code)
    case.assertEqual(expected, actual.json())


from sqlalchemy import inspect


def test_tables_exist(test_db):
    inspector = inspect(test_db.get_bind())
    assert "user_id" in inspector.get_table_names()
