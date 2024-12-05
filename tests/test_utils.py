import datetime
from unittest import TestCase, mock

from freezegun import freeze_time

from app import utils
from app.models import Artist, Playlist, Track, UserID
from app.models.album import Album

case = TestCase()
case.maxDiff = None


def test_refresh_access_token__no_refresh_token(mock_request):
    with case.assertRaises(ValueError) as e:
        utils.refresh_access_token(request=mock_request())
        case.assertEqual("Missing refresh token", str(e))


@mock.patch("app.utils.requests.post")
@freeze_time("2024-12-02 12:00:00")
def test_refresh_access_token__standard(mock_post, mock_request):
    mock_post.return_value.json.return_value = {
        "access_token": "123abc",
        "refresh_token": "abc123",
        "expires_in": "3600",
    }

    mr = mock_request(access_token="456", refresh_token="678")
    actual = utils.refresh_access_token(request=mr)
    expected_request_session = {
        "access_token": "123abc",
        "refresh_token": "abc123",
        "expiration_time": 1733144370,
    }

    case.assertEqual("123abc", actual)
    case.assertEqual(expected_request_session | mr.session, mr.session)


@mock.patch("app.utils.requests.post")
def test_refresh_access_token__no_refresh_token_returned(mock_post, mock_request):
    mock_post.return_value.json.return_value = {
        "access_token": "123abc",
        "expires_in": 3600,
    }
    mr = mock_request(refresh_token="abc123")
    acutal = utils.refresh_access_token(request=mr)

    case.assertEqual("123abc", acutal)


@mock.patch("app.utils.requests.post")
def test_refresh_access_token__failed_to_refresh(mock_post, mock_request):
    mock_post.return_value.json.return_value = {}
    mr = mock_request(refresh_token="abc123")
    acutal = utils.refresh_access_token(request=mr)

    case.assertEqual(None, acutal)


@freeze_time("2024-12-02 12:59:00")
def test_get_auth__unexpired_and_access_token(mock_request):
    mr = mock_request(access_token="123abc", expiration_time=1733144400)
    actual = utils.get_auth(request=mr)
    case.assertEqual("123abc", actual)


@freeze_time("2024-12-02 12:59:00")
def test_get_auth__unexpired_and_no_access_token(mock_request):
    mr = mock_request(expiration_time=1733144400)
    with case.assertRaises(ValueError) as e:
        utils.get_auth(request=mr)
        case.assertEqual("Please call /authorize to generate new tokens", str(e))


@freeze_time("2024-12-02 13:00:00")
def test_get_auth__expired_and_no_access_and_no_refresh(mock_request):
    mr = mock_request(expiration_time=1733144400)
    with case.assertRaises(ValueError) as e:
        utils.get_auth(request=mr)
        case.assertEqual("Please call /authorize to generate new tokens", str(e))


@mock.patch("app.utils.refresh_access_token", return_value=None)
@freeze_time("2024-12-02 13:00:00")
def test_get_auth__expired_and_refresh_token_fails(
    mock_refresh_access_token, mock_request
):
    mr = mock_request(refresh_token="123abc", expiration_time=1733144400)
    with case.assertRaises(ValueError) as e:
        utils.get_auth(request=mr)
        case.assertEqual("Please call /authorize to generate new tokens", str(e))


@mock.patch("app.utils.refresh_access_token", return_value="123abc")
def test_get_auth__use_refresh_token(mock_refresh_access_token, mock_request):
    mr = mock_request(refresh_token="abc123")
    actual = utils.get_auth(request=mr)

    case.assertEqual("123abc", actual)


@mock.patch("app.utils.get_auth", return_value="123abc")
@mock.patch("app.utils.requests.get")
def test_get_user_id__no_access_token(mock_get, mock_get_auth, test_db):
    mock_get.return_value.json.return_value = {"id": "user1"}
    actual = utils.get_user_id(request=None, session=test_db)

    case.assertEqual("user1", actual)


@mock.patch("app.utils.get_auth")
@mock.patch("app.utils.requests.get")
def test_get_user_id__access_token(mock_get, mock_get_auth, test_db):
    mock_get.return_value.json.return_value = {"id": "user1"}
    actual = utils.get_user_id(request=None, session=test_db, access_token="123abc")

    case.assertEqual("user1", actual)
    mock_get_auth.assert_not_called()


@mock.patch("app.utils.requests.get")
def test_get_user_id__access_token_but_request_fails(mock_get, test_db):
    mock_get.return_value.json.return_value = {}
    actual = utils.get_user_id(request=None, session=test_db, access_token="123abc")

    case.assertEqual(None, actual)


@mock.patch("app.utils.requests.get")
def test_get_user_id__access_token(mock_get, test_db):
    mock_get.return_value.json.return_value = {"id": "user1"}
    test_db.add(UserID(user_id="user1"))
    actual = utils.get_user_id(request=None, session=test_db, access_token="123abc")

    case.assertEqual("user1", actual)


@mock.patch("app.utils.requests.get")
def test_get_playlists_wrapper__request_fails_or_no_playlists(mock_get):
    mock_get.return_value.json.return_value = {}
    actual = utils.get_playlists_wrapper(access_token=None, user=None)

    case.assertEqual([], actual)


@mock.patch("app.utils.requests.get")
def test_get_playlists_wrapper__just_one_page_of_playlists(mock_get):
    mock_get.return_value.json.return_value = {
        "items": ["playlist1", None],
        "next": None,
    }
    actual = utils.get_playlists_wrapper(access_token=None, user=None)

    case.assertEqual(["playlist1"], actual)


@mock.patch("app.utils.time.sleep")
@mock.patch("app.utils.requests.get")
def test_get_playlists_wrapper__multiple_pages_of_playlists(mock_get, mock_sleep):
    mock_get.return_value.json.side_effect = [
        {
            "items": ["playlist1", None],
            "next": "next_url",
        },
        {"items": ["playlist2"], "next": None},
    ]
    actual = utils.get_playlists_wrapper(access_token=None, user=None)

    case.assertEqual(["playlist1", "playlist2"], actual)


@mock.patch("app.utils.get_auth")
@mock.patch("app.utils.get_playlists_wrapper", return_value=[])
def test_sync_playlists__no_playlists(mock_playlists, mock_get_auth, test_db):
    user = "user"
    utils.sync_playlists(request=None, session=test_db, user=user)

    case.assertEqual(
        None, test_db.query(Playlist).filter(Playlist.user_id == user).first()
    )


@mock.patch("app.utils.get_auth")
@mock.patch("app.utils.get_playlists_wrapper", return_value=[])
def test_sync_playlists__standard(mock_playlists, mock_get_auth, test_db):
    test_db.add_all([UserID(user_id="user"), UserID(user_id="not user")])
    test_db.commit()

    mock_playlists.return_value = [
        {"id": "1", "name": "playlist1", "owner": {"id": "user"}},
        {"id": "2", "name": "playlist2", "owner": {"id": "not user"}},
        {"id": "3", "name": "playlist3", "owner": {"id": "user"}},
        {"id": "4", "name": "playlist4", "owner": {"id": "user"}},
    ]

    utils.sync_playlists(request=None, session=test_db, user="user")

    expected = [
        Playlist(spotify_id="1", name="playlist1", user_id="user"),
        Playlist(spotify_id="3", name="playlist3", user_id="user"),
        Playlist(spotify_id="4", name="playlist4", user_id="user"),
    ]

    actual = (
        test_db.query(Playlist)
        .filter(Playlist.user_id == "user")
        .order_by(Playlist.spotify_id.asc())
        .all()
    )

    case.assertEqual(expected, actual)


@mock.patch("app.utils.requests.get")
def test_get_tracks_wrapper__request_fails_or_no_tracks(mock_get):
    mock_get.return_value.json.return_value = {}
    actual = utils.get_tracks_wrapper(access_token=None, playlist_id=None)

    case.assertEqual([], actual)


@mock.patch("app.utils.requests.get")
def test_get_tracks_wrapper__one_page_of_tracks(mock_get):
    mock_get.return_value.json.return_value = {
        "items": ["track1", "track2", None],
        "next": None,
    }
    actual = utils.get_tracks_wrapper(access_token=None, playlist_id=None)

    expected = ["track1", "track2"]

    case.assertEqual(expected, actual)


@mock.patch("app.utils.time.sleep")
@mock.patch("app.utils.requests.get")
def test_get_tracks_wrapper__multiple_pages_of_tracks(mock_get, mock_sleep):
    mock_get.return_value.json.side_effect = [
        {"items": ["track1", "track2", None], "next": "next_url"},
        {"items": ["track3", None, "track4"], "next": None},
    ]
    actual = utils.get_tracks_wrapper(access_token=None, playlist_id=None)

    case.assertEqual(["track1", "track2", "track3", "track4"], actual)


def test_clean_album__no_release_date():
    album = {"id": "1", "artist_id": "123abc", "name": "album1"}
    actual = utils.clean_album(album=album)

    expected = {
        "spotify_id": "1",
        "artist_id": "123abc",
        "name": "album1",
        "release_date": None,
    }

    case.assertDictEqual(expected, actual)


def test_clean_album__precision_day():
    album = {
        "id": "1",
        "artist_id": "123abc",
        "name": "album1",
        "release_date_precision": "day",
        "release_date": "2024-12-02",
    }
    actual = utils.clean_album(album=album)

    expected = {
        "spotify_id": "1",
        "artist_id": "123abc",
        "name": "album1",
        "release_date": datetime.date(2024, 12, 2),
    }

    case.assertDictEqual(expected, actual)


def test_clean_album__precision_month():
    album = {
        "id": "1",
        "artist_id": "123abc",
        "name": "album1",
        "release_date_precision": "month",
        "release_date": "2024-12",
    }
    actual = utils.clean_album(album=album)

    expected = {
        "spotify_id": "1",
        "artist_id": "123abc",
        "name": "album1",
        "release_date": datetime.date(2024, 12, 1),
    }

    case.assertDictEqual(expected, actual)


def test_clean_album__precision_year():
    album = {
        "id": "1",
        "artist_id": "123abc",
        "name": "album1",
        "release_date_precision": "year",
        "release_date": "2024",
    }
    actual = utils.clean_album(album=album)

    expected = {
        "spotify_id": "1",
        "artist_id": "123abc",
        "name": "album1",
        "release_date": datetime.date(2024, 1, 1),
    }

    case.assertDictEqual(expected, actual)


def test_clean_album__bad_parse():
    album = {
        "id": "1",
        "artist_id": "123abc",
        "name": "album1",
        "release_date_precision": "day",
        "release_date": "2024-123-32",
    }
    actual = utils.clean_album(album=album)

    expected = {
        "spotify_id": "1",
        "artist_id": "123abc",
        "name": "album1",
        "release_date": None,
    }

    case.assertDictEqual(expected, actual)


@mock.patch("app.utils.clean_album")
def test_sync_albums(mock_clean_album, test_db):
    test_db.add_all(
        [
            Artist(spotify_id="artist1", name="artist1_name"),
            Artist(spotify_id="artist2", name="artist2_name"),
            Artist(spotify_id="artist3", name="artist3_name"),
        ]
    )
    test_db.commit()

    albums = [
        {"id": "1", "name": "album1"},
        {"id": "2", "name": "album2"},
        {"id": "1", "name": "album1"},
        {"id": "1", "name": "album1"},
        {"id": "3", "name": "album3"},
    ]

    mock_clean_album.side_effect = [
        {
            "spotify_id": "1",
            "artist_id": "artist1",
            "name": "album1",
            "release_date": datetime.date(2024, 12, 2),
        },
        {
            "spotify_id": "2",
            "artist_id": "artist2",
            "name": "album2",
            "release_date": datetime.date(2024, 12, 2),
        },
        {
            "spotify_id": "3",
            "artist_id": "artist3",
            "name": "album3",
            "release_date": datetime.date(2024, 12, 2),
        },
    ]

    utils.sync_albums(session=test_db, albums=albums)
    actual = test_db.query(Album).order_by(Album.spotify_id.asc()).all()

    expected = [
        Album(
            spotify_id="1",
            artist_id="artist1",
            name="album1",
            release_date=datetime.date(2024, 12, 2),
        ),
        Album(
            spotify_id="2",
            artist_id="artist2",
            name="album2",
            release_date=datetime.date(2024, 12, 2),
        ),
        Album(
            spotify_id="3",
            artist_id="artist3",
            name="album3",
            release_date=datetime.date(2024, 12, 2),
        ),
    ]

    case.assertEqual(expected, actual)


def test_sync_albums__empty(test_db):
    utils.sync_albums(session=test_db, albums=[])
    actual = test_db.query(Album).order_by(Album.spotify_id).all()

    case.assertEqual([], actual)


def test_sync_artists(test_db):
    artists = [
        {"id": "1", "name": "artist1"},
        {"id": "2", "name": "artist2"},
        {"id": "1", "name": "artist1"},
        {"id": "3", "name": "artist3"},
        {"id": "3", "name": "artist3"},
    ]

    utils.sync_artists(session=test_db, artists=artists)
    actual = test_db.query(Artist).order_by(Artist.spotify_id.asc()).all()

    expected = [
        Artist(spotify_id="1", name="artist1"),
        Artist(spotify_id="2", name="artist2"),
        Artist(spotify_id="3", name="artist3"),
    ]

    case.assertEqual(expected, actual)


def test_sync_artists__empty(test_db):
    utils.sync_artists(session=test_db, artists=[])
    actual = test_db.query(Artist).order_by(Artist.spotify_id).all()

    case.assertEqual([], actual)


@mock.patch("app.utils.sync_albums")
@mock.patch("app.utils.sync_artists")
def test_sync_tracks__no_playlists(mock_sync_artists, mock_sync_albums, test_db):
    utils.sync_tracks(request=None, session=test_db, user="user")

    case.assertEqual([], test_db.query(Artist).all())
    case.assertEqual([], test_db.query(Album).all())
    case.assertEqual([], test_db.query(Track).all())


@mock.patch("app.utils.get_auth")
@mock.patch("app.utils.get_tracks_wrapper", return_value=None)
@mock.patch("app.utils.sync_albums")
@mock.patch("app.utils.sync_artists")
def test_sync_tracks__playlists_but_no_tracks(
    mock_sync_artists, mock_sync_albums, mock_get_tracks, mock_get_auth, test_db
):
    test_db.add(UserID(user_id="user"))
    test_db.add(Playlist(spotify_id="123abc", user_id="user", name="playlist1"))
    test_db.commit()

    mock_get_tracks.return_value = []

    utils.sync_tracks(request=None, session=test_db, user="user")

    case.assertEqual([], test_db.query(Artist).all())
    case.assertEqual([], test_db.query(Album).all())
    case.assertEqual([], test_db.query(Track).all())


@mock.patch("app.utils.get_auth")
@mock.patch("app.utils.get_tracks_wrapper")
@mock.patch("app.utils.sync_albums")
@mock.patch("app.utils.sync_artists")
def test_sync_tracks__playlists_and_tracks(
    mock_sync_artists, mock_sync_albums, mock_get_tracks, mock_get_auth, test_db
):
    test_db.add(UserID(user_id="user"))
    test_db.add(Playlist(spotify_id="123abc", user_id="user", name="playlist1"))
    test_db.commit()

    mock_get_tracks.return_value = [
        {"id": "1", "playlist_id": "123abc", "album": {"id": "321"}, "name": "track1"},
        {"id": "2", "playlist_id": "123abc", "album": {"id": "321"}, "name": "track2"},
    ]

    utils.sync_tracks(request=None, session=test_db, user="user")

    case.assertEqual([], test_db.query(Artist).all())
    case.assertEqual([], test_db.query(Album).all())
    case.assertEqual([], test_db.query(Track).all())


def test_clean_tables(test_db):
    not_user_playlist = Playlist(
        spotify_id="321cba", user_id="not user", name="playlist1"
    )
    not_user_track = Track(
        id="3",
        spotify_id="345",
        playlist_id="321cba",
        album_id="678",
        artist_id="456",
        name="track2",
    )

    test_db.add_all([UserID(user_id="user"), UserID(user_id="not user")])
    test_db.add_all(
        [
            Playlist(spotify_id="123abc", user_id="user", name="playlist1"),
            not_user_playlist,
        ]
    )
    test_db.add(Artist(spotify_id="456", name="artist1"))
    test_db.flush()
    test_db.add(
        Album(
            spotify_id="678",
            artist_id="456",
            name="album1",
            release_date=datetime.date(2024, 12, 3),
        )
    )
    test_db.add_all(
        [
            Track(
                id="1",
                spotify_id="abc123",
                playlist_id="123abc",
                album_id="678",
                artist_id="456",
                name="track1",
            ),
            Track(
                id="2",
                spotify_id="cba123",
                playlist_id="123abc",
                album_id="678",
                artist_id="456",
                name="track2",
            ),
            not_user_track,
        ]
    )
    test_db.commit()

    case.assertIsNotNone(test_db.query(Playlist).all())
    case.assertIsNotNone(test_db.query(Track).all())

    utils.clean_tables(session=test_db, user="user")
    test_db.commit()

    case.assertEqual([not_user_playlist], test_db.query(Playlist).all())
    case.assertEqual([not_user_track], test_db.query(Track).all())


@mock.patch("app.utils.get_auth")
@mock.patch("app.utils.get_user_id")
def test_add_or_get_user__no_user_provided_and_not_stored(
    mock_get_user_id, mock_get_auth, test_db
):
    test_db.add(UserID(user_id="not user"))
    test_db.commit()

    mock_get_user_id.return_value = "user"
    actual = utils.add_or_get_user(request=None, session=test_db)

    case.assertEqual("user", actual)
    case.assertEqual(
        [UserID(user_id="user")],
        test_db.query(UserID).filter(UserID.user_id == "user").all(),
    )


@mock.patch("app.utils.get_auth")
@mock.patch("app.utils.get_user_id")
def test_add_or_get_user__user_provided_and_not_stored(
    mock_get_user_id, mock_get_auth, test_db
):
    test_db.add(UserID(user_id="not user"))
    test_db.commit()

    actual = utils.add_or_get_user(request=None, session=test_db, user="user")

    case.assertEqual("user", actual)
    mock_get_user_id.assert_not_called()

    case.assertEqual(
        [UserID(user_id="user")],
        test_db.query(UserID).filter(UserID.user_id == "user").all(),
    )


@mock.patch("app.utils.get_auth")
@mock.patch("app.utils.get_user_id")
def test_add_or_get_user__user_provided_and_stored(
    mock_get_user_id, mock_get_auth, test_db
):
    test_db.add_all([UserID(user_id="user"), UserID(user_id="not user")])
    test_db.commit()

    actual = utils.add_or_get_user(request=None, session=test_db, user="user")

    case.assertEqual("user", actual)
    case.assertEqual(
        [UserID(user_id="user")],
        test_db.query(UserID).filter(UserID.user_id == "user").all(),
    )
