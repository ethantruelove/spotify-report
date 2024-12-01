from datetime import date
from unittest import TestCase

from app import models

case = TestCase()


def test_album_repr():
    a = models.album.Album(
        spotify_id="1234",
        artist_id="4321",
        name="good album",
        release_date=date(2024, 12, 1),
    )

    expected = (
        "<Album spotify_id=1234 artist_id=4321 name=good album release_date=2024-12-01>"
    )

    case.assertEqual(expected, str(a))


test_album_repr()
