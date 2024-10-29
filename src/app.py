import os
import secrets
import time
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SESSION_SECRET = os.getenv("SESSION_SECRET")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)


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
    if not refresh_token and (refresh_token := request.session.get("refresh_token")):
        raise ValueError("Missing refresh token")

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
    }

    headers = {"Content-type": "application/x-www-form-urlencoded"}

    res = requests.post(
        url="https://accounts.spotify.com/api/token",
        data=data,
        headers=headers,
    ).json()

    access_token = res["access_token"]
    if refresh_token := res.get(refresh_token):
        request.session["refresh_token"] = refresh_token

    request.session["expiration_time"] = int(res.get("expires_in")) + time.time()

    return access_token


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


@app.get("/getMyPlaylists")
def get_my_playlists(request: Request):
    access_token = get_auth(request=request, next_url=request.url)
    res = requests.get(
        url=f"https://api.spotify.com/v1/me/playlists",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    return res.json()


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exception: HTTPException):
    if exception.status_code == 307:
        return RedirectResponse(url="/authorize")

    return {"detail": exception.detail}
