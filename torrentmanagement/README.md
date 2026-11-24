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
# Add SUBDL_API_KEY to .env if subtitle downloads are needed.
make build
make run
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Torrent data and SQLite metadata persist in the Compose volume.

## Make targets

| Target | Behavior |
|---|---|
| `make build` | Build the POC image. |
| `make run` | Build and run in the foreground. |
| `make start` | Build and run in the background. |
| `make stop` | Stop the service and keep data. |
| `make clean` | Remove this POC's containers/network and keep its volume. |
| `make cleanup-data` | Stop the service, clear downloaded files and corresponding records inside a one-off container, then restart if it was running. |
| `make prune` | Remove only this POC's containers, local image, and Compose volume, including all downloaded data. This is destructive and cannot be undone. |
| `make test` | Run focused unit tests in the container. |

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

Copy `.env.example` to `.env`. Keep API keys only in `.env`; it is git-ignored.

`TM_MAX_TORRENT_CONTENT_BYTES` caps the aggregate size advertised by a torrent (200 GiB by default). `TM_RANGE_WAIT_SECONDS` bounds how long a missing requested range may wait for torrent pieces. `TM_RANGE_CHUNK_BYTES` limits each explicit byte-range response. Subtitle downloads require `SUBDL_API_KEY` and are subject to SubDL's current API terms and quotas.

## Known POC limits

- Direct range playback is available only for supported browser codecs. Other formats are converted after completion; MKV/WebM inputs may use sequential, non-seekable output once their first ten playable seconds are ready.
- Browser support for fragmented MP4 from the partial-transcode route should be verified in Chrome and Firefox with approved test media.
- A torrent with no supported video is rejected. Multi-video torrents default to the largest supported file; the UI allows an override.
- No authentication, production egress policy, or external subtitle-provider fallback is included. The torrent's advertised aggregate size is capped, but no host-disk quota is enforced.