import datetime
import logging
import os
import time
from typing import Annotated, List

import requests
from dotenv import load_dotenv
from fastapi import Depends, Request
from sqlalchemy.dialects.postgresql import insert as pginsert
from sqlalchemy.orm import Session

import app.database as db
from app.models import Album, Artist, Playlist, Track, UserID

load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

log = logging.getLogger("uvicorn.error")

SessionDep = Annotated[Session, Depends(db.get_db)]


# https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens
def refresh_access_token(
    request: Request,
    refresh_token: str = None,
):
    if not refresh_token and not (
        refresh_token := request.session.get("refresh_token")
    ):
        raise ValueError("Missing refresh token")

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    headers = {"Content-type": "application/x-www-form-urlencoded"}

    res = requests.post(
        url="https://accounts.spotify.com/api/token",
        data=data,
        headers=headers,
    ).json()

    if access_token := res.get("access_token"):
        if refresh_token := res.get("refresh_token"):
            request.session["refresh_token"] = refresh_token

        # add 30 second buffer in case of mistiming
        request.session["expiration_time"] = (
            int(res.get("expires_in")) + time.time() - 30
        )
        request.session["access_token"] = access_token
        return access_token


def get_auth(request: Request):
    if expiration_time := request.session.get("expiration_time"):
        if expiration_time > time.time():
            if access_token := request.session.get("access_token"):
                return access_token

    if refresh_token := request.session.get("refresh_token"):
        if access_token := refresh_access_token(
            request=request, refresh_token=refresh_token
        ):
            return access_token

    # TODO: this scenario is not well handled, easiest fix is to manually go to
    # localhost:8080/authorize every 1 hour
    raise ValueError("Please call /authorize to generate new tokens")


def get_user_id(request: Request, session: SessionDep, access_token: str = None):
    if not access_token:
        access_token = get_auth(request=request)

    res = requests.get(
        url=f"https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()

    if user_id := res.get("id"):
        if not session.query(UserID).filter_by(user_id=user_id).first():
            session.add(UserID(user_id=user_id))
            session.commit()

        return user_id


def get_playlists_wrapper(access_token: str, user: str):
    res = requests.get(
        url=f"https://api.spotify.com/v1/users/{user}/playlists",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"limit": 50},
    ).json()

    if playlists := res.get("items"):
        while res.get("next"):
            time.sleep(0.1)
            res = requests.get(
                url=res["next"],
                headers={"Authorization": f"Bearer {access_token}"},
                params={"limit": 50},
            ).json()
            playlists.extend(res["items"])

    return [p for p in playlists if p is not None] if playlists is not None else []


def sync_playlists(request: Request, session: SessionDep, user: str):
    log.info("Starting playlist sync")
    if raw_playlists := get_playlists_wrapper(
        access_token=get_auth(request=request),
        user=user,
    ):
        for playlist in raw_playlists:
            user_id = playlist.get("owner").get("id")
            if user_id == user:
                session.add(
                    Playlist(
                        spotify_id=playlist.get("id"),
                        name=playlist.get("name"),
                        user_id=user_id,
                    )
                )

        session.flush()


def get_tracks_wrapper(access_token: str, playlist_id: str):
    res = requests.get(
        url=f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"limit": 50},
    ).json()

    if tracks := res.get("items"):
        while res.get("next"):
            time.sleep(0.1)
            res = requests.get(
                url=res["next"],
                headers={"Authorization": f"Bearer {access_token}"},
                params={"limit": 50},
            ).json()

            tracks.extend(res["items"])

    return [t for t in tracks if t is not None] if tracks is not None else []


def clean_album(album: dict):
    precision = album.get("release_date_precision")
    if release_date_str := album.get("release_date"):
        if precision == "day":
            f = "%Y-%m-%d"
        elif precision == "month":
            f = "%Y-%m"
        else:
            f = "%Y"

        try:
            release_date = datetime.datetime.strptime(release_date_str, f).date()
        except ValueError:
            release_date = None
    else:
        release_date = None

    return {
        "spotify_id": album.get("id"),
        "artist_id": album.get("artist_id"),
        "name": album.get("name"),
        "release_date": release_date,
    }


def sync_albums(session: SessionDep, albums: List[dict]):
    seen_albums = set()
    cleaned_albums = []
    for album in albums:
        album_id = album.get("id")
        if album_id not in seen_albums:
            album_name = album.get("name")
            log.info(f"Adding album {album_name} by {album_name} with id {album_id}")
            seen_albums.add(album_id)
            cleaned_albums.append(clean_album(album))

    print(cleaned_albums)
    print(bool(cleaned_albums))
    if cleaned_albums:
        stmt = pginsert(Album).values(cleaned_albums).on_conflict_do_nothing()
        session.execute(stmt)
        session.flush()


def sync_artists(session: SessionDep, artists: List[dict]):
    seen_artists = set()
    deduped_artists = []
    for artist in artists:
        artist_id = artist.get("id")
        if artist_id not in seen_artists:
            artist_name = artist.get("name")
            log.info(f"Adding artist {artist_name} with id {artist_id}")
            seen_artists.add(artist_id)
            deduped_artists.append({"spotify_id": artist_id, "name": artist_name})

    if deduped_artists:
        stmt = pginsert(Artist).values(deduped_artists).on_conflict_do_nothing()
        session.execute(stmt)
        session.flush()


def sync_tracks(request: Request, session: SessionDep, user: str = None):
    log.info("Starting tracks sync")
    artists = []
    albums = []
    tracks = []
    for playlist in session.query(Playlist).filter_by(user_id=user).all():
        log.info(f"Getting track data for playlist: {playlist.name}")
        if raw_tracks := get_tracks_wrapper(
            access_token=get_auth(request=request), playlist_id=playlist.spotify_id
        ):
            no_local_tracks = [
                t.get("track") for t in raw_tracks if t.get("is_local") is False
            ]

            artists.extend([t.get("artists")[0] for t in no_local_tracks])
            # we need to use the artist_id from the track, not from the album
            albums.extend(
                [
                    {"artist_id": t.get("artists")[0].get("id"), **t.get("album")}
                    for t in no_local_tracks
                ]
            )

            tracks.extend(
                [
                    Track(
                        spotify_id=t.get("id"),
                        playlist_id=playlist.spotify_id,
                        album_id=t.get("album").get("id"),
                        # only takes first artist
                        artist_id=t.get("artists")[0].get("id"),
                        name=t.get("name"),
                    )
                    for t in no_local_tracks
                ]
            )

    sync_artists(session=session, artists=artists)
    sync_albums(session=session, albums=albums)
    session.add_all(tracks)

    session.commit()


def clean_tables(session: SessionDep, user: str):
    log.info("Cleaning tables")
    session.query(Playlist).filter_by(user_id=user).delete()
    session.flush()


def add_or_get_user(request: Request, session: SessionDep, user: str = None):
    log.info("Getting user")
    if not user:
        user = get_user_id(
            request=request, session=session, access_token=get_auth(request=request)
        )

    user_id = session.query(UserID).filter_by(user_id=user).first()
    if not user_id:
        user_id = UserID(user_id=user)
        session.add(user_id)
        session.flush()

    return user_id.user_id