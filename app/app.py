import csv
import datetime
import io
import logging
import os
import secrets
import time
from typing import Annotated, Optional

import orjson
import pytz
import requests
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

import app.database as db
from app import utils
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
tz = pytz.timezone("America/Chicago")

SessionDep = Annotated[Session, Depends(db.get_db)]


@app.get("/getAccessToken")
def get_access_token(code: str) -> dict:
    """
    Wrapper to get an access token from Spotify API.

    Args:
        code (str): The code provided from Spotify's OAuth flow

    Returns:
        dict: Resulting JSON
    """
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


@app.get("/authorize")
def get_user_auth(request: Request, next_url: Optional[str] = None) -> RedirectResponse:
    """
    Redirects the user through Spotify's API for OAuth verification.

    Args:
        request (Request): Current request
        next_url (Optional[str], optional): Next url to redirect to. Defaults to None.

    Returns:
        RedirectResponse: Redirect to Spotify site for OAuth approval
    """
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
) -> RedirectResponse:
    """
    Callback URL from Spotify OAuth flow. Will redirect to user specified URL (defaults to /docs).

    Args:
        request (Request): Current request
        code (str, optional): Spotify provided code. Defaults to None.
        state (str, optional): Returned state to prevent cross site request forgery. Defaults to None.
        error (str, optional): Optional error if failure. Defaults to None.

    Raises:
        HTTPException: Raises if any error is specified
        HTTPException: Raises if returned state from Spotify mismatches cached state
        HTTPException: Raises for any other reason if auth fails and no code provided

    Returns:
        RedirectResponse: Redirects to previous user specified URL after authorization (defaults to /docs)
    """
    stored_state = request.session.get("state")
    if error:
        raise HTTPException(detail=f'Failed due to "{error}"', status_code=401)

    if code:
        if state == stored_state:
            next_url = state[state.index(":") + 1 :]
            next_url = next_url if next_url != "" else "/docs"

            res = get_access_token(code=code)

            request.session["access_tokens"] = res["access_token"]
            request.session["expiration_time"] = (
                int(res.get("expires_in")) + time.time()
            )
            if refresh_token := res.get("refresh_token"):
                request.session["refresh_token"] = refresh_token

            return RedirectResponse(url=next_url)
        raise HTTPException(
            detail=f"State mismatch! Expected {stored_state} but got {state}",
            status_code=401,
        )
    raise HTTPException(
        detail=f"Failed to receive code from Spotify; please try again", status_code=401
    )


@app.get("/sync")
def sync(request: Request, session: SessionDep, user: str = None) -> HTMLResponse:
    """
    Syncs a provided user's playlists to local database.

    Args:
        request (Request): Current request
        session (SessionDep): Current session
        user (str, optional): Provided user. Defaults to None. If not provided, it will be looked up via Spotify

    Returns:
        HTMLResponse: Indication of successful sync
    """
    user = utils.add_or_get_user(request=request, session=session, user=user)
    utils.clean_tables(session=session, user=user)

    utils.sync_playlists(request=request, session=session, user=user)
    utils.sync_tracks(request=request, session=session, user=user)

    return HTMLResponse("Successfully synced", status_code=200)


@app.get("/getTracksFromPlaylistDB")
def get_tracks_db(session: SessionDep, playlist_id: str) -> StreamingResponse:
    """
    A small function to get tracks pulled from database rendered as JSON

    Args:
        session (SessionDep): Current session
        playlist_id (str): Spotify playlist ID to get tracks for from DB

    Returns:
        StreamingResponse: Faster render response to serialize returned Track data
    """
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
) -> Response:
    """
    Fets most frequent items of a given media type (tracks, albums, artists) and renders as bar graph.

    Args:
        request (Request): Current
        session (SessionDep): Current sesssion
        background_tasks (BackgroundTasks): Current background tasks
        user (str, optional): User to get top media for. Defaults to None.
        media_type (MediaType, optional): tracks, albums, or artists. Defaults to MediaType.tracks.
        top (int, optional): Quantity of items to return. Defaults to 10.

    Returns:
        Response: Image response with bar graph of data
    """
    user = utils.add_or_get_user(request=request, session=session, user=user)

    if media_type == MediaType.tracks:
        sub_query = (
            session.query(Track.spotify_id, func.count(Track.spotify_id).label("freq"))
            .join(Playlist, Playlist.spotify_id == Track.playlist_id)
            .join(UserID, UserID.user_id == Playlist.user_id)
            .filter(UserID.user_id == user)
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
            .join(Playlist, Playlist.spotify_id == Track.playlist_id)
            .join(UserID, UserID.user_id == Playlist.user_id)
            .filter(UserID.user_id == user)
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
            .join(Playlist, Playlist.spotify_id == Track.playlist_id)
            .join(UserID, UserID.user_id == Playlist.user_id)
            .filter(UserID.user_id == user)
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


@app.get("/report")
def get_report(request: Request, session: SessionDep, user: str = None):
    if not user:
        user = utils.get_user_id(
            request=request,
            session=session,
            access_token=utils.get_auth(request=request),
        )

    if session.query(UserID).filter(UserID.user_id == user).first():
        data = (
            session.query(
                Playlist.name,
                Track.name,
                Artist.name,
                Album.name,
                Album.release_date,
                Playlist.spotify_id,
                Track.spotify_id,
                Artist.spotify_id,
                Album.spotify_id,
            )
            .filter(Playlist.user_id == user)
            .filter(Playlist.spotify_id == Track.playlist_id)
            .filter(Track.album_id == Album.spotify_id)
            .filter(Track.artist_id == Artist.spotify_id)
        )
    else:
        raise HTTPException(
            detail=f'User "{user}" not found; nothing to generate', status_code=404
        )

    columns = [
        "playlist_name",
        "track_name",
        "artist_name",
        "album_name",
        "album_release_date",
        "playlist_spotify_id",
        "track_spotify_id",
        "artist_spotify_id",
        "album_spotify_id",
    ]

    data = [dict(zip(columns, row)) for row in data]

    mem = io.StringIO()

    writer = csv.DictWriter(mem, columns)
    writer.writeheader()
    writer.writerows(data)

    mem.seek(0)

    export_media_type = "text/csv"
    export_headers = {
        "Content-Disposition": f"attachment; filename={user}_playlists.csv"
    }
    return StreamingResponse(mem, headers=export_headers, media_type=export_media_type)


@app.get("/debug")
def debug(request: Request) -> dict:
    """
    A debug helper to get the current session cookie values

    Args:
        request (Request): Current request

    Returns:
        dict: Current session cookie data
    """
    expiration_time = str(request.session.get("expiration_time"))

    return {
        "access_token": request.session.get("access_token"),
        "refresh_token": request.session.get("refresh_token"),
        "expiration_time": datetime.datetime.fromtimestamp(
            int(expiration_time[: expiration_time.index(".")]), tz=tz
        ),
        "expired": float(request.session.get("expiration_time")) < time.time(),
    }


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exception: HTTPException) -> JSONResponse:
    """
    A helper handler to handle various status code exception differently if more data is needed.
\
    Args:
        request (Request): Current request
        exception (HTTPException): Raised exception

    Returns:
        JSONResponse: Detailed response about raised exception
    """
    return JSONResponse({"detail": exception.detail}, status_code=exception.status_code)
