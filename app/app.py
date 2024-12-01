import datetime
import logging
import os
import secrets
import time
from typing import Annotated, List, Optional

import orjson
import requests
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from sqlalchemy import delete, desc, func
from sqlalchemy.dialects.postgresql import insert as pginsert
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

import app.database as db
from app.models import Album, Artist, Playlist, Track, UserID
from app.visualizer import MediaType, freq

load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SESSION_SECRET = os.getenv("SESSION_SECRET")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

log = logging.getLogger("uvicorn.error")

SessionDep = Annotated[Session, Depends(db.get_db)]


@app.get("/getAccessToken")
def get_access_token(request: Request, code: str, next_url: Optional[str] = None):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    headers = {
        "Content-type": "application/x-www-form-urlencoded",
    }

    res = requests.post(
        url="https://accounts.spotify.com/api/token",
        data=data,
        headers=headers,
    )

    return res.json()


# https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens
@app.get("/refreshAccessToken")
def refresh_access_token(request: Request, refresh_token: str = None):
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
        if refresh_token := res.get(refresh_token):
            request.session["refresh_token"] = refresh_token

        request.session["expiration_time"] = int(res.get("expires_in")) + time.time()
        return access_token

    return JSONResponse(status_code=401, content=res)


@app.get("/authorize")
def get_user_auth(request: Request, next_url: Optional[str] = None):
    if not next_url:
        next_url = ""

    scope = [
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "playlist-read-private",
        "playlist-read-collaborative",
        "user-top-read",
        "user-read-recently-played",
        "user-library-read",
    ]

    state = f"{secrets.token_urlsafe(16)}:{next_url}"
    request.session["state"] = state

    auth_url = (
        f"https://accounts.spotify.com/authorize?response_type=code&client_id={CLIENT_ID}"
        + f"&redirect_uri={REDIRECT_URI}&scope={' '.join(scope)}&state={state}"
    )

    return RedirectResponse(auth_url)


@app.get("/callback")
def callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
):
    stored_state = request.session.get("state")
    if error:
        return HTMLResponse(f"Failed due to {error}")

    if code and state == stored_state:
        next_url = state[state.index(":") + 1 :]
        next_url = next_url if next_url != "" else "/docs"

        res = get_access_token(request=request, code=code, next_url=next_url)

        request.session["access_token"] = res["access_token"]
        request.session["expiration_time"] = int(res.get("expires_in")) + time.time()
        if refresh_token := res.get("refresh_token"):
            request.session["refresh_token"] = refresh_token

        return RedirectResponse(url=next_url)

    return HTMLResponse(f"State mismatch! expected {stored_state} but got {state}")


def get_auth(request: Request):
    if expiration_time := request.session.get("expiration_time"):
        if expiration_time > time.time():
            if access_token := request.session.get("access_token"):
                return access_token

    if refresh_token := request.session.get("refresh_token"):
        return refresh_access_token(request=request, refresh_token=refresh_token)

    # TODO: this scenario is not well handled, easiest fix is to manually go to
    # localhost:8080/authorize, but shouldn't need to do that more than every 60 day or so
    return request.session.get("access_token")


@app.get("/getUserID")
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

    return HTTPException(status_code=404, detail="Unable to locate current user name")


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

    return [p for p in playlists if p is not None]


def sync_playlists(request: Request, session: SessionDep, user: str):
    log.info("Starting playlist sync")
    if raw_playlists := get_playlists_wrapper(
        access_token=get_auth(request=request),
        user=user,
    ):
        for playlist in raw_playlists:
            spotify_id = playlist.get("id")
            name = playlist.get("name")
            owner = playlist.get("owner", {})
            user_id = owner.get("id") if isinstance(owner, dict) else None

            if spotify_id and name and user_id == user:
                session.add(Playlist(spotify_id=spotify_id, name=name, user_id=user_id))

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

    return tracks


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
            release_date = datetime.datetime.strptime(release_date_str, f)
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


@app.get("/sync")
def sync(request: Request, session: SessionDep, user: str = None):
    user = add_or_get_user(request=request, session=session, user=user)
    clean_tables(session=session, user=user)

    sync_playlists(request=request, session=session, user=user)
    sync_tracks(request=request, session=session, user=user)

    return "successfully synced"


@app.get("/getTracksFromPlaylistDB")
def get_tracks_db(session: SessionDep, playlist_id: str):
    tracks = session.query(Track).filter(Track.playlist_id == playlist_id).all()
    return StreamingResponse(
        iter(
            [
                orjson.dumps(
                    [t.to_dict() for t in tracks],
                    option=orjson.OPT_INDENT_2,
                )
            ]
        ),
        media_type="application/json",
    )


@app.get("/getFrequent")
def get_frequent(
    request: Request,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    user: str = None,
    media_type: MediaType = MediaType.tracks,
    top: int = 10,
):
    user = add_or_get_user(request=request, session=session, user=user)

    if media_type == MediaType.tracks:
        sub_query = (
            session.query(Track.spotify_id, func.count(Track.spotify_id).label("freq"))
            .group_by(Track.spotify_id)
            .order_by(desc("freq"))
            .limit(top)
            .subquery()
        )

        data = session.query(Track.name, sub_query.c.freq).join(
            sub_query, Track.spotify_id == sub_query.c.spotify_id
        )
    elif media_type == MediaType.artists:
        sub_query = (
            session.query(Track.artist_id, func.count(Track.artist_id).label("freq"))
            .group_by(Track.artist_id)
            .order_by(desc("freq"))
            .limit(top)
            .subquery()
        )

        data = session.query(Artist.name, sub_query.c.freq).join(
            sub_query, Artist.spotify_id == sub_query.c.artist_id
        )
    else:
        sub_query = (
            session.query(Track.album_id, func.count(Track.album_id).label("freq"))
            .group_by(Track.album_id)
            .order_by(desc("freq"))
            .limit(top)
            .subquery()
        )

        data = session.query(Album.name, sub_query.c.freq).join(
            sub_query, Album.spotify_id == sub_query.c.album_id
        )

    # https://stackoverflow.com/questions/73754664/how-to-display-a-matplotlib-chart-with-fastapi-nextjs-without-saving-the-chart
    img_buf = freq(data.order_by(sub_query.c.freq.desc()).all())
    background_tasks.add_task(img_buf.close)
    headers = {"Content-Disposition": 'inline; filename="out.png"'}

    return Response(img_buf.getvalue(), headers=headers, media_type="image/png")


@app.get("/test")
def func_test(request: Request, session: SessionDep):
    session.query(UserID).filter(UserID.user_id == "drfriday13th").delete()
    session.commit()


@app.get("/debug")
def debug(request: Request):
    from datetime import datetime

    expiration_time = str(request.session.get("expiration_time"))

    return {
        "access_token": request.session.get("access_token"),
        "refresh_token": request.session.get("refresh_token"),
        "expiration_time": datetime.fromtimestamp(
            int(expiration_time[: expiration_time.index(".")])
        ),
        "expired": request.session.get("expiration_time") < time.time(),
    }


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exception: HTTPException):
    if exception.status_code == 307:
        return RedirectResponse(url="/authorize")

    return {"detail": exception.detail}
