import os
import secrets
import time
from typing import Annotated, Optional

import requests
from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.database import get_db
from app.models import Playlist, UserID

load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SESSION_SECRET = os.getenv("SESSION_SECRET")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

SessionDep = Annotated[Session, Depends(get_db)]


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


def get_auth(request: Request, next_url: Optional[str] = None):
    if expiration_time := request.session.get("expiration_time"):
        if expiration_time > time.time():
            if access_token := request.session.get("access_token"):
                return access_token

    if refresh_token := request.session.get("refresh_token"):
        return refresh_access_token(request=request, refresh_token=refresh_token)

    raise HTTPException(status_code=307, detail=f"/authorize?next={next_url}")


@app.get("/getUserID")
def get_user_id(request: Request, session: SessionDep):
    res = requests.get(
        url=f"https://api.spotify.com/v1/me",
        headers={
            "Authorization": f"Bearer {get_auth(request=request, next_url=request.url)}"
        },
    ).json()

    if user_id := res.get("id"):
        if not session.query(UserID).filter_by(user_id=user_id).first():
            session.add(UserID(user_id=user_id))
            session.commit()

        return user_id

    return HTTPException(status_code=404, detail="Unable to locate current user name")


def get_playlists_wrapper(
    request: Request,
    session: SessionDep,
    access_token: str,
    offset: int = 0,
    limit: int = 50,
    user: str = None,
):
    if not user:
        user = get_user_id(request)

    res = requests.get(
        url=f"https://api.spotify.com/v1/users/{user}/playlists",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"limit": limit, "offset": offset},
    ).json()

    if playlists := res["items"]:
        while res["next"]:
            time.sleep(1)
            res = requests.get(
                url=res["next"],
                headers={"Authorization": f"Bearer {access_token}"},
            ).json()

            playlists.extend(res["items"])

    return playlists


@app.get("/getPlaylists")
def get_playlists(
    request: Request,
    session: SessionDep,
    offset: int = 0,
    limit: int = 50,
    user: str = None,
):
    playlists = get_playlists_wrapper(
        request=request,
        access_token=get_auth(request=request, next_url=request.url),
        user=user,
        offset=offset,
        limit=limit,
    )

    return {"data": playlists}


@app.get("/debug")
def debug(request: Request):
    return {
        "access_token": request.session.get("access_token"),
        "refresh_token": request.session.get("refresh_token"),
        "expiration_time": request.session.get("expiration_time"),
    }


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exception: HTTPException):
    if exception.status_code == 307:
        return RedirectResponse(url="/authorize")

    return {"detail": exception.detail}
