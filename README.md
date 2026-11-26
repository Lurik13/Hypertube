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

### Getting started

