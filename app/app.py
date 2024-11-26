import logging
import os
import secrets
import time
from typing import Annotated, List, Optional

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import delete
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

import app.database as db
from app.models import Playlist, PlaylistSchema, Track, UserID

load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SESSION_SECRET = os.getenv("SESSION_SECRET")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

log = logging.getLogger(__name__)

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
            time.sleep(0.25)
            res = requests.get(
                url=res["next"],
                headers={"Authorization": f"Bearer {access_token}"},
                params={"limit": 50},
            ).json()

            playlists.extend(res["items"])

    return playlists


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

        session.commit()


def get_tracks_wrapper(access_token: str, playlist_id: str):
    res = requests.get(
        url=f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"limit": 50},
    ).json()

    if tracks := res.get("items"):
        while res.get("next"):
            time.sleep(0.25)
            res = requests.get(
                url=res["next"],
                headers={"Authorization": f"Bearer {access_token}"},
                params={"limit": 50},
            ).json()

            tracks.extend(res["items"])

    return tracks


@app.get("/playlistsDB")
def sync_tracks(request: Request, session: SessionDep, user: str = None):
    log.info("Starting tracks sync")
    for playlist in session.query(Playlist).filter_by(user_id=user).all():
        log.debug(f"Syncing tracks for playlist: {playlist.name}")
        if raw_tracks := get_tracks_wrapper(
            access_token=get_auth(request=request), playlist_id=playlist.spotify_id
        ):
            session.add_all(
                [
                    Track(
                        spotify_id=t.get("track").get("id"),
                        playlist_id=playlist.spotify_id,
                        album_id=t.get("track").get("album").get("id"),
                        # only takes first artist
                        artist_id=t.get("track").get("artists")[0].get("id"),
                        name=t.get("track").get("name"),
                    )
                    for t in raw_tracks
                    if t.get("is_local") is False
                ]
            )

    session.commit()


def clean_tables(session: SessionDep, user: str):
    log.info("Cleaning tables")
    playlists = session.query(Playlist).filter_by(user_id=user)
    session.query(Track).filter(
        Track.playlist_id.in_([p.spotify_id for p in playlists.all()])
    ).delete()
    playlists.delete()

    session.commit()


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
