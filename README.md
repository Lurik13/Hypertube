# Hypertube 42

### Roles 
- Lurik13: Responsable du front
- Gkubina: Gestion de toute la logique torrent
- lumingoprogramming: Gestion de tout ce qui touche aux users (back + aide au front)
- KoganeShiro: Monitoring dashboard

KoganeShiro + Gkubina apres avoir fini leur partie -> Agregateur de bases (IMDB + Base torrents + nos bases)


### MANDATORY

#### Ground rules
- [ ] Only legal / royalty-free sources (archive.org, legittorrents.info)
- [ ] No torrent-streaming library (webtorrent, peerflix, pulsar...)
- [ ] Secrets in a `.env` excluded from git (none in git history)
- [ ] Nothing in the console (client) or server logs: no errors, warnings or notices
- [ ] Anything not specifically authorized is forbidden

#### General / layout
- [ ] Is responsive ? (usable on a phone, acceptable on small resolutions)
- [ ] Have a header - main content - footer ?
- [ ] Is working on both Chrome and Firefox ?

#### Security
- [ ] Is it secure ?
  - [ ] Passwords hashed in the DB
  - [ ] Protected against SQL injection
  - [ ] Protected against XSS (comments, profile fields...)
  - [ ] Uploads validated (type, size, extension)
  - [ ] Every form validated (client + server side)

#### Account & authentication
- [ ] Register with email, username, last name, first name, password
- [ ] Log in with username + password
- [ ] Be able to create an account / log in using 42 + google
- [ ] Receive email when forgot password ? (reset link)
- [ ] Be able to log out with only one click on every page ?
- [ ] Multi language ? (user picks a preferred language, default English)

#### User profile
- [ ] Can modify its profile information (email, name, profile picture etc...)
- [ ] Be able to see the profile of other user (minus their email)

#### Library (authenticated users only)
- [ ] Search field
- [ ] Search queries at least 2 external legal sources
- [ ] Results shown as thumbnails, sorted by name
- [ ] Thumbnails show: name, year, IMDb rating (OMDb/TMDb), cover image
- [ ] Home page with thumbnails need to let the user know if they already watched it or not
- [ ] Without a search, show the most popular videos (downloads, peers, seeders...)
- [ ] Infinite scroll (async next page, no "load more" link)
- [ ] Be able to sort per rating (and name, genre, year)
- [ ] Be able to filter per year (and genre, rating, name...)

#### Video page (authenticated users only)
- [ ] Video player
- [ ] Details: summary, casting (producer, director, main cast), year, length, IMDb rating, cover
- [ ] Write comments + list of previous comments
- [ ] Torrent workflow to download and see the media in the video player
  - [ ] Torrent launched on the server if the file isn't there yet
  - [ ] Stream starts as soon as enough data is downloaded (download + stream at the same time)
  - [ ] Everything runs in the background, non-blocking
  - [ ] Movie kept on the server once fully downloaded
- [ ] Remove the media files after 30d unwatched (can be config)
- [ ] Add subtitle
  - [ ] English subtitles downloaded and available in the player
  - [ ] Subtitles in the user's preferred language if the video language differs
- [ ] On-the-fly conversion for non-native formats (mkv minimum)

#### REST API (OAuth2)
- [ ] API call to get media informations
- [ ] POST /oauth/token (client + secret -> token)
- [ ] GET /users, GET /users/:id (no email unless owner)
- [ ] PATCH /users/:id (own profile only, 403 otherwise)
- [ ] GET /movies (public front page), GET /movies/:id
- [ ] GET /comments, GET /comments/:id, PATCH, DELETE
- [ ] POST /comments or POST /movies/:movie_id/comments
- [ ] Undefined routes return the appropriate HTTP code
- [ ] Be able to prove it is truly RESTful (defense)

### BONUS (only evaluated if the mandatory part is PERFECT)

#### Content & discovery
- [ ] Be able to see shows
- [ ] Create category
- [ ] Be able to filter per category
- [ ] View people that worked on the media
- [ ] Be able to filter per people
- [ ] Be able to search per name of multiple language
- [ ] Continue to watch, keep in memory where did we left out
- [ ] History tab?

#### Personalization & social
- [ ] Create lists (like favorite or anything you would want)
- [ ] Add review (can be shown on the user profile)

#### Player & media
- [ ] Add / manage subtitle tracks
- [ ] Add multiple audio

#### Platform
- [ ] Have an admin dashboard to monitor the webapp


---
### Architecture of the project 

micro architecture
```
.
├── docker-compose.yml
├── .env.example
├── .gitignore                    # .env, data/, certs, node_modules...
├── .dockerignore
├── Makefile                      # up, down, logs, migrate, test, lint, clean
├── README.md
│
├── frontend/                     # React + TypeScript
│   ├── Dockerfile                # multi-stage: build with Node, serve static files
│   ├── index.html
│   ├── public/
│   │   └── locales/              # i18next: en/, fr/ ... translation.json
│   └── src/                      # routes, fetch client, TanStack Query hooks Header, Footer, MovieCard, Player, Login, Register, Library, Movie,  useAuth, useInfiniteMovies... i18next config
│
├── backend/
│   ├── Dockerfile                # one image, used by api AND worker (different command)
│   ├── requirements.txt
│   ├── app/                      # FastAPI
│   │   ├── routers/              # auth, users, movies, comments, oauth, stream
│   │   ├── services/             # omdb/tmdb, sources etc...
│   ├── worker/                   # Torrents
│   └── tests/
│       ├── api/
│       └── worker/
│
├── nginx/
│   ├── nginx.conf
│   ├── conf.d/default.conf       # proxy /api, static front, range requests
│   └── certs/                    # self-signed for dev (gitignored)
│
├── monitoring/
│   ├── prometheus/
│   ├── grafana/
├── scripts/                      # init-db, seed, generate-certs.sh, backup
├── docs/                         # subject PDF, database-schema.md, features checklist
└── data/                         # dev only, gitignored (media volume, db dumps)
```

> The folders are named `back/` and `front/` in the repo.

### Getting started

Requirements: Docker with the Compose plugin, and `make`.

```sh
cp .env.example .env    # the placeholder values work for local dev
make up                 # builds and starts everything, applies migrations
make help               # every available target
```

| URL | What |
|-----|------|
| http://localhost:8000/api/docs | API docs (OpenAPI / Swagger) |
| http://localhost:8025 | Mailpit: every email sent in dev (password reset links) |

Services in `docker-compose.yml`:

| Service | Role |
|---------|------|
| `db` | PostgreSQL 17. Data in the `pgdata` volume, so it survives restarts. Not exposed to the host. |
| `api` | FastAPI backend (`back/`). Runs `alembic upgrade head` on start, then uvicorn. |
| `worker` | Celery worker + beat scheduler (same image as `api`): periodic cleanup jobs. |
| `valkey` | Celery broker. |
| `mailpit` | Catches outgoing emails in dev. |

Useful targets: `make logs s=api`, `make psql` (SQL shell in the db), `make seed` (fake users, password `Hypertube42!`), `make test`, `make migration name=...`, `make reset-db` (deletes all local data, same as `docker compose down -v`).

#### OAuth (42 and Google)

A provider is enabled once its client id and secret are set in `.env`. Until then, its login route answers 404. Each developer creates their own test credentials. They are secrets: put them only in `.env`, never in git, Slack or an issue.

**42**
1. Go to https://profile.intra.42.fr/oauth/applications/new (intra > Settings > API > *Register a new app*).
2. Name: `Hypertube dev`. Redirect URI: `http://localhost:8000/api/auth/oauth/42/callback`. Scopes: `public` only.
3. Submit, then copy the **UID** into `FORTYTWO_CLIENT_ID` and the **SECRET** into `FORTYTWO_CLIENT_SECRET`.
4. The 42 secret expires (the date is on the app page). When it does, generate a new one there and update `.env`.

**Google**
1. Go to https://console.cloud.google.com/, then create a project (for example `hypertube-dev`).
2. *APIs & Services > OAuth consent screen* (called *Google Auth Platform* in newer consoles): user type **External**, app name `Hypertube dev`, your email as the support and developer contact. Scopes: `openid`, `email`, `profile`. Leave the app in **Testing** mode and add every teammate's Google address under **Test users**: only test users can log in.
3. *APIs & Services > Credentials > Create credentials > OAuth client ID*: type **Web application**.
   - Authorized JavaScript origins: `http://localhost:8000`
   - Authorized redirect URIs: `http://localhost:8000/api/auth/oauth/google/callback`
4. Copy the **Client ID** into `GOOGLE_CLIENT_ID` and the **Client secret** into `GOOGLE_CLIENT_SECRET`.

**Then**
```sh
docker compose up -d api      # recreates the api with the new .env values
```
Open http://localhost:8000/api/auth/oauth/42/login (or `/google/login`) in the browser. After you log in at the provider, you land on `FRONTEND_URL/` (the front page). Check that it worked with http://localhost:8000/api/me.

The redirect URIs are built from `PUBLIC_API_URL`. If the API is served elsewhere (for example `https://localhost:8443` behind nginx), change `PUBLIC_API_URL` and register the new URIs at both providers. They must match exactly: same scheme, host, port and path, with no trailing slash.

---
### Authentication API

Sessions use an `HttpOnly`, `Secure`, `SameSite=Lax` cookie (`hypertube_session`). The cookie holds a random token; the database stores only its SHA-256 hash. Passwords are hashed with argon2id.

| Method | Route | Body | Success | Errors |
|--------|-------|------|---------|--------|
| POST | `/api/auth/register` | `email, username, first_name, last_name, password` | 201 + user, logged in | 409 email/username taken, 422 |
| POST | `/api/auth/login` | `username, password` | 200 + user | 401 `Invalid username or password` |
| POST | `/api/auth/logout` | - | 204 | - |
| POST | `/api/auth/password/forgot` | `email` | 202 (same answer whether the email exists or not) | 422 |
| POST | `/api/auth/password/reset` | `token, password` | 204, every session logged out | 400 invalid/expired/used link, 422 |
| GET | `/api/auth/oauth/{42,google}/login` | - | redirects to the provider | 404 provider not configured |
| GET | `/api/auth/oauth/{42,google}/callback` | - | redirects to `FRONTEND_URL/` | redirects to `FRONTEND_URL/login?error=oauth_failed` or `email_in_use` |
| GET | `/api/me` | - | 200 + current user | 401 when logged out |

- **Form errors** always look like `{"detail": "...", "errors": [{"field": "password", "message": "..."}]}`.
- **Rules**: username 3-30 characters (letters, digits, `.` `_` `-`); names 1-50 characters (letters, spaces, `'` `-`); password 8-128 characters with a lowercase letter, an uppercase letter, a digit and a special character, and not containing the username.
- **Reset email**: the link is `FRONTEND_URL/reset-password?token=...`. The front reads `token` and POSTs it with the new password. It is valid for `PASSWORD_RESET_TTL_MINUTES` (30) and works only once.
- **Frontend in dev**: proxy `/api` to `http://localhost:8000` in `vite.config.ts` (`server.proxy`) so cookies are same-origin, and send requests with `credentials: "include"`.
- **Protecting a route** (backend): add a `user: CurrentUser` parameter (from `app.deps`), or protect a whole router with `APIRouter(dependencies=[Depends(require_auth)])`. Use `OptionalUser` when a route works for both logged-in and anonymous visitors.

---
### Database conventions

Every feature task creates its own tables and queries, following these rules. Ask for a review on any PR that adds a migration.

**Migrations** (Alembic, in `back/alembic/versions/`)
- One numbered file per change: `0004_movies.py`, `0005_comments.py`... Create it with `make migration name=movies`. Each file has an `upgrade()` and a `downgrade()` that undoes it exactly (`make test` runs every migration up, down and up again).
- Migrations are applied automatically when the `api` container starts (`make migrate` to apply them by hand).
- **Never edit a migration that has been merged.** Always add a new one.
- Add the matching SQLAlchemy model to `back/app/models.py` (or a module next to it).

**Naming**
- Tables: plural snake_case (`movies`, `watched_movies`). Columns: snake_case.
- Primary key: `id BIGINT GENERATED ALWAYS AS IDENTITY` (`sa.BigInteger(), sa.Identity(always=True), primary_key=True`).
- Timestamps: `created_at` / `updated_at` as `TIMESTAMPTZ` with `server_default=now()`. Tables with `updated_at` attach the existing trigger: `CREATE TRIGGER <table>_set_updated_at BEFORE UPDATE ON <table> FOR EACH ROW EXECUTE FUNCTION set_updated_at()`.
- Foreign keys: `<singular_table>_id` (`user_id`, `movie_id`), type `BIGINT`.
- Constraint names follow PostgreSQL defaults: `<table>_<column>_fkey`, `_key` (unique), `_idx`, `_check`.

**Integrity**
- `NOT NULL` unless a value can really be missing; `UNIQUE` where duplicates are a bug; `CHECK` for closed sets of values.
- Every foreign key states its `ondelete` (`CASCADE`, `SET NULL` or `RESTRICT`) on purpose.
- Index every foreign key and every column used for frequent lookups or sorting.

**Queries**
- Use SQLAlchemy (ORM or Core expressions). They are always parameterized.
- Raw SQL only through `text()` with bound parameters (`text("... WHERE id = :id"), {"id": movie_id}`). **Never** build SQL with f-strings, `%` or `+` from user input: that is SQL injection.
- Async code (API) uses the `DbSession` dependency from `app.db`; sync code (worker, scripts) uses `get_sync_engine()`.

**Sensitive data**
- No plain-text passwords, tokens or secrets in the database or the logs: store hashes only (`app.security`).
- Don't log request bodies. Don't return input values in error messages.

**Upkeep jobs** (`back/app/jobs/cleanup.py`, scheduled every `CLEANUP_INTERVAL_MINUTES` by the `worker`)
- `cleanup.expired_auth_rows`: deletes expired sessions and expired or used password reset tokens.
- `cleanup.unwatched_movies`: deletes the files of movies not watched for `MOVIE_RETENTION_DAYS` (30) and sets their `file_path` to `NULL` (the row stays, because comments point to it). **Contract with the movies task**: `movies` needs `file_path TEXT NULL` (relative to `MEDIA_ROOT`, the `media` volume mounted at `/data/media`), `last_watched_at TIMESTAMPTZ NULL` (updated on every play) and `created_at`. The job does nothing until that table exists.

**Dev data**
- `make seed` runs `back/app/seed.py`: it is idempotent and inserts fake users. Each feature adds its own seeder (movies, comments...) to the `SEEDERS` list.
- `make reset-db` deletes the local database and media (`docker compose down -v`). The next `make up` starts from scratch.
- The app connects with a restricted role (`APP_DB_USER`, not a superuser), created by `scripts/init-db/` when the volume is first initialised. It owns the app database, so it can run migrations.
