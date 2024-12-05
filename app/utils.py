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
SESSION_SECRET = os.getenv("SESSION_SECRET")

log = logging.getLogger("uvicorn.error")

SessionDep = Annotated[Session, Depends(db.get_db)]


# https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens
def refresh_access_token(
    request: Request,
    refresh_token: str = None,
) -> str:
    """
    Try to get the refresh access token from the cached session cookie and renew with Spotify.

    Args:
        request (Request): Current request
        refresh_token (str, optional): The refresh token to use. Defaults to None.
            Will try to pull from cookies if not provided

    Raises:
        ValueError: If not provided and not in cookies, error as impossible to refresh

    Returns:
        str: The refresh token
    """
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


def get_auth(request: Request) -> str:
    """
    Gets the necessary access token to use for Spotify API calls.
        Will use cached access token if unexpired
        Will attempt to use refresh token to get new access token if expired
        Will finally error if options exhausted (could look into redirecting to /authorize)

    Args:
        request (Request): Current request

    Raises:
        ValueError: Error if all sources exhausted

    Returns:
        str: The access token
    """
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


def get_user_id(request: Request, session: SessionDep, access_token: str = None) -> str:
    """
    Wrapper to get the user name from Spotify.

    Args:
        request (Request): Current request
        session (SessionDep): Current session
        access_token (str, optional): The access token to use to get current user. Defaults to None.

    Returns:
        str: The user id for the current authenticated user
    """
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


def get_playlists_wrapper(access_token: str, user: str) -> List[Playlist]:
    """
    Wrapper to get playlists for a user from Spotify.
    Note that playlists will be public only if not the currently authenticated user.

    Args:
        access_token (str): Access token to use
        user (str): User to get playlists for

    Returns:
        List[Playlist]: List of playlists found
    """
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


def sync_playlists(request: Request, session: SessionDep, user: str) -> None:
    """
    Sync the acquired playlists with the database.

    Args:
        request (Request): Current request
        session (SessionDep): Current session
        user (str): The user to sync
    """
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


def get_tracks_wrapper(access_token: str, playlist_id: str) -> List[Track]:
    """
    Wrapper for getting tracks from Spotify for a given playlist

    Args:
        access_token (str): Access token to use for authentication
        playlist_id (str): Spotify's playlist ID to get tracks for

    Returns:
        List[Track]: List of tracks found in the playlist
    """
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


def clean_album(album: dict) -> dict:
    """
    Clean a provided album by formatting the release date as a date object and renaming keys appropriately.

    Args:
        album (dict): Spotify's raw provided album dict information

    Returns:
        dict: Cleaned dictionary ready to be converted to Album object
    """
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


def sync_albums(session: SessionDep, albums: List[dict]) -> None:
    """
    Sync the albums with the database.
    This will clean albums and deduplicate the list before committing to DB in one transaction,
    ignoring albums that are already present in the DB.

    Args:
        session (SessionDep): Current session
        albums (List[dict]): Raw albums from Spotify to clean and sync
    """
    seen_albums = set()
    cleaned_albums = []
    for album in albums:
        album_id = album.get("id")
        if album_id not in seen_albums:
            album_name = album.get("name")
            log.info(f"Adding album {album_name} by {album_name} with id {album_id}")
            seen_albums.add(album_id)
            cleaned_albums.append(clean_album(album))

    if cleaned_albums:
        stmt = pginsert(Album).values(cleaned_albums).on_conflict_do_nothing()
        session.execute(stmt)
        session.flush()


def sync_artists(session: SessionDep, artists: List[dict]) -> None:
    """
    Sync the artists with the database.
    This will deduplicate the list before committing to DB in one transaction,
    ignoring artists that are already present in the DB.

    Args:
        session (SessionDep): Current session
        artists (List[dict]): Raw artists from Spotify
    """
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


def sync_tracks(request: Request, session: SessionDep, user: str = None) -> None:
    """
    Sync the tracks with the DB for a provided user

    Args:
        request (Request): Current request
        session (SessionDep): Current session
        user (str, optional): User to sync tracks for. Defaults to None.
            User will be currently authenticated user if not provided.
    """
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


def clean_tables(session: SessionDep, user: str) -> None:
    """
    Delete all the playlists for a current user.
    Since the application has no concept of its own user, we must do everything based on a Spotify username,
    and our definition of sync is to delete all existing playlists made by a user and then reacquire the current set.

    Args:
        session (SessionDep): Current session
        user (str): The user to delete playlists for
    """
    log.info("Cleaning tables")
    session.query(Playlist).filter_by(user_id=user).delete()
    session.flush()


def add_or_get_user(request: Request, session: SessionDep, user: str = None) -> str:
    """
    Add the requested user ID to DB if not present and return the object.

    Args:
        request (Request): Current request
        session (SessionDep): Current session
        user (str, optional): The user to add or get. Defaults to None.

    Returns:
        str: User ID for the requested user
    """
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
