# Torrentmanagement POC

This is a local-only torrent download and browser playback prototype. It accepts a `.torrent` file manually selected by a trusted operator from an approved legal/royalty-free source. It does not search torrent catalogs or verify provenance.

## Requirements

- Docker Engine with Docker Compose v2
- GNU Make
- Optional: a SubDL API key for subtitle downloads

The API port is published on `127.0.0.1` only. Do not expose this unauthenticated POC to a shared or public network.

## Start

```sh
cp .env.example .env
# Replace both database password placeholders with different strong passwords.
# Add SUBDL_API_KEY to .env if subtitle downloads are needed.
make build
make run
```

If `.env` already exists, merge the database variables from `.env.example` into it rather than overwriting existing secrets. For new passwords, generate two different values with `openssl rand -base64 32`.

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). PostgreSQL metadata and torrent/media files persist in separate Compose volumes. PostgreSQL is private to the Compose network; only the API port is published to host loopback.

The database starts fresh by design. Existing SQLite records remain untouched in the torrent-data volume and are not imported. Existing media files are retained. To make an existing torrent visible in the new library, upload its `.torrent` file again; libtorrent can verify/reuse available payload files.

New torrent selection prefers browser-native container candidates (`.mp4` and `.webm`), then chooses the largest file within that preference. Container extensions do not guarantee compatible codecs; readiness still probes and decodes the selected source. Other supported formats are converted after download completes.

## Make targets

| Target | Behavior |
|---|---|
| `make build` | Build the POC image. |
| `make run` | Build and run in the foreground. |
| `make start` | Build and run in the background. |
| `make stop` | Stop the service and keep data. |
| `make clean` | Remove this POC's containers/network and keep both persistent volumes. |
| `make cleanup-data` | Stop torrent writes, clear downloaded files and PostgreSQL records inside a one-off container, then restore previously running services. |
| `make prune` | Remove only this POC's containers, local image, PostgreSQL volume, and torrent-data volume. This is destructive and cannot be undone. |
| `make test` | Start PostgreSQL if needed and run focused tests in isolated temporary schemas. |

`make prune` is scoped to the `hypertube-torrentmanagement` Compose project. It does not run global Docker prune commands.

## API outline

- `POST /api/torrents` — raw `.torrent` body with `Content-Type: application/x-bittorrent`.
- `GET /api/torrents` and `GET /api/torrents/{id}` — list/status.
- `PUT /api/torrents/{id}/selection` — select a video file by index.
- `GET /api/torrents/{id}/readiness` — independent playback readiness.
- `GET /api/torrents/{id}/stream` — range-aware direct playback or sequential partial transcode.
- `POST /api/torrents/{id}/subtitles` — search and download up to five results across selected languages.
- `GET /api/torrents/{id}/subtitles` — list tracks.
- `GET /api/subtitles/{id}` — serve a downloaded subtitle file.

## Configuration

Copy `.env.example` to `.env`. Keep database credentials and API keys only in `.env`; it is git-ignored. PostgreSQL bootstrap creates a restricted application role from `TM_DB_USER` and `TM_DB_PASSWORD`; the separate `POSTGRES_SUPERUSER_PASSWORD` is only used to initialize the database container.

`TM_MAX_TORRENT_CONTENT_BYTES` caps the aggregate size advertised by a torrent (200 GiB by default). `TM_RANGE_WAIT_SECONDS` bounds how long a missing requested range may wait for torrent pieces. `TM_RANGE_CHUNK_BYTES` limits each explicit byte-range response. Subtitle downloads require `SUBDL_API_KEY` and are subject to SubDL's current API terms and quotas.

## Known POC limits

- Direct range playback is available only for supported browser codecs. Readiness requires a verified, decodable opening video frame and required container metadata. Other formats are converted after completion; MKV/WebM inputs may use sequential, non-seekable output as soon as that opening is ready.
- Browser support for fragmented MP4 from the partial-transcode route should be verified in Chrome and Firefox with approved test media.
- A torrent with no supported video is rejected. Multi-video torrents prefer MP4/WebM candidates before falling back to the largest supported file; the UI allows an override.
- No authentication, production egress policy, or external subtitle-provider fallback is included. The torrent's advertised aggregate size is capped, but no host-disk quota is enforced.

The progress display names the actual lifecycle state. A nearly full bar can still say “Still downloading · 99.9%”; only a backend `complete` state is displayed as “Download complete · 100%”.