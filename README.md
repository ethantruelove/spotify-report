# spotify-report
Reporting on what you think you already know about your music habits

# Setup

## Connecting to Spotify API

- Create a project at https://developer.spotify.com/dashboard
  - Set redirect URI/callback to: http://localhost:8080/callback/

## Environment variables

Create a `.env` file with the following environment variables (both found in Spotify project settings):
```
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
REDIRECT_URI=http://localhost:8080/callback/
SESSION_SECRET="a super secret key"

POSTGRES_USER=admin
POSTGRES_PASSWORD=admin
POSTGRES_HOST=localhost
POSTGRES_DB=spotify
```

## Running inside Docker (Recommended)

### Quickstart
```
docker compose up --build website
```

### Fully reset everything with Docker

Sometimes in the process of modiying the Dockerfile or needing to fully purge old Alembic files, you may need various levels of cleansing Docker cached items. If the above command isn't sufficient, use one or all of these as necessary.

```
docker rm -f $(docker ps -a -q)
docker volume rm $(docker volume ls -q)
docker image rm $(docker image ls -q)
docker builder prune --force --all
```

## Running outside Docker

Make sure you have a local Postgres database running (could alternatively run just the Postgres container in Docker and run the app locally, but be sure to make sure that the DB connection string does not need modifying)
```
pip install requirements.txt
alembic upgrade head
python -m uvicorn app.app:app --host 0.0.0.0 --port 8080 --reload
```

## Access
Endpoints are locally hosted at: [localhost:8080/docs](localhost:8080/docs)

For OAuth flow through to Spotify, be sure to not use the Spotify page to retrieve the initial session token. Instead, visit [localhost:8080/authorize](localhost:8080/authorize) in client/browser and then Swagger endpoints *should* work as expected.

# Current functionality

Note that there is a good bit of functionality that should be wrapped in a more secure pattern, but since this is running locally for now, there are less concerns

### App
- Allow user to authenticate with Spotify
  - Saves relevant access and refresh tokens to session cookies
- Acquires track data for a user's playlists and saves
  - Also gets artist and album data corresponding to the tracks
- Generates bar graph image for user's top x requested tracks, albums, or artists based on the occurrence frequency in their playlists
- Generates a data file with all relevant information about a user's playlists

### Database
- Runs a Postgres server inside of Docker to save data to locally
- Uses Alembic to handle database migrations
- Uses SQLAlchemy for ORM

### Testing
- Uses pytest framework for fixtures
- Provides comprehensive coverage overview with pytest-cov

### Limitations/enhancement possibilities
- If you login somewhere else like a private browser, the access token may be revoked. To fix, run the clear session endpoint (and maybe logout of Spotify as well if that still does not resolve)
- Tests are a bit flaky on some of the endpoints, specifically the frequency image generator as it doesn't return data readily available to test
- The /authorize endpoint must be hit directly and not via the Swagger page (http://localhost:8080/authorize)

# Original roject proposal

### Spotify API enhancements / maybe data visualizer:

- Create a Spotify web API project (https://developer.spotify.com/documentation/web-api)
- Expand on the base functionality they provide to create an experience utilizing a user’s data based on them logging in and authenticating
- Expand app development via complexity of base web API functions:
- Information on library
- Information on playlists
- Statistics on metadata of items
- Stretch goal of representing statistics visually
- Use Docker to have local database to store information and only pull new from Spotify on request
- Maybe a really stretch goal: combine Django with FastAPI to get frontend instead of a Swagger API page or some other means of frontend setup

### Timeline proposal (aligned with Wednesdays of week # to keep with homework)

The overall plan is to start slow, pick up in November, and then have the last couple weeks to either wrap up smoothly or allow for push back if features prove too time consuming to implement in their scheduled week.

- Week 4 (10/23):
  - Lighter and focused on ensuring that repo is created and that API key can be generated from Spotify (if this fails, I will switch to my other project proposal)
- Week 5 (10/30):
  - Hello world application inside of FastAPI
  - Ensure that basic endpoint functionality is working for Spotify API key and that simple operations are loading as intended
- Week 6 (11/06):
  - Expand on API endpoints and create more robust statistics and data collection behaviors (consider moving items into classes where it makes sense)
- Week 7 (11/13):
  - Work on adding Docker support that will containerize application
  - This is a good time to add Docker hosted local Postgres DB
- Week 8 (11/20):
  - Add in SQLAlchemy support with Alembic provisioning for models for DB
  - This will allow API to be called only on demand or some other interval instead of every call
- Week 9 (11/27):
  - Investigate how this would combine with Django or some other full stack app to produce a front end
  - If front end is entirely too complex for this task, focus on adding endpoints that will simply output image files of data visualizations
- Week 10 (12/04):
  - Wrap up loose ends
  - Add additional testing and documentation where needed
- Week 11 (12/11):
  - Failover week for anything that needs to be pushed back due to other time constraints
  - Time to record video presentation and ensure final touches