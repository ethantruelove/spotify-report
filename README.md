# spotify-report
Reporting on what you think you already know about your music habits

# Quickstart

### Setting up FastAPI

```
pip install requirements.txt
python -m uvicorn src.app:app --host 0.0.0.0 --port 8080 --reload
```
Endpoints are locally hosted at: [localhost:8080/docs](localhost:8080/docs)

For OAuth flow through to Spotify, be sure to not use the Spotify page to retrieve the initial session token. Instead, visit [localhost:8080/authorize](localhost:8080/authorize) in client/browser and then Swagger endpoints *should* work as expected.

### Connecting to Spotify API

- Create a project at https://developer.spotify.com/dashboard
- Create a `.env` file wiith the following environment variables (both found in Spotify project settings):
  - CLIENT_ID
  - CLIENT_SECRET
  - REDIRECT_URI (whatever you set in the Spotify App)
  - SESSION_SECRET (a secret to use for session middleware; not important so can be weak string as long as not externally hosting this API)

# Project proposal:

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