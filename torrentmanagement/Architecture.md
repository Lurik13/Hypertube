# Torrentmanagement POC Architecture

**Status:** Product behavior and the POC implementation baseline are confirmed. Production deployment and production dependency approval are out of scope.  
**Last updated:** 2026-11-26

## 1. Goals and scope

Build a local/demo website and backend API that take a manually selected torrent through background downloading, early playback, completed-file storage, and subtitle retrieval.

The Torrentmanagement boundary starts with a trusted local operator supplying a `.torrent` file manually selected from Archive.org. Searching torrent catalogs and verifying source legality belong to another project component. The project-wide rule remains: use only legal/royalty-free media. This POC does not accept arbitrary torrent URLs or magnets.

Included:

- Reuse an existing job or completed media item when the torrent infohash is already known.
- Download asynchronously and retain complete media until an operator invokes cleanup.
- Prefer browser-native MP4/WebM candidates for the default selection, then prefer larger files within a format tier; allow the user to override the choice.
- Prioritize startup pieces and missing pieces requested for playback.
- Support range seeking during direct playback; keep partial transcoded playback sequential and non-seekable.
- Download five subtitle matches total across English, French, German, and Italian.
- Provide a simple local/demo frontend and API; authentication is out of scope.

Not included:

- Torrent catalog search, Archive.org integration, user accounts, OAuth, or production deployment.
- A one-shot torrent-to-player/streaming library or a general-purpose torrent client UI.
- Automatic subtitle translation or generation.

## 2. Confirmed product decisions

### 2.1 Torrent identity, selection, and deduplication

- The uploaded `.torrent` metadata is parsed to calculate the infohash. The infohash is the deduplication key.
- A repeated request reuses the existing job or completed media; it must not create another copy.
- After reading torrent metadata, show the available files. Initially prefer MP4/WebM candidates, then select the largest supported file in that tier. Other supported formats are the fallback. Always allow an explicit override.
- Treat the extension preference as a heuristic only: inspect codecs and actual decodability before marking a file ready for direct playback. Browser-incompatible MP4/WebM still needs conversion after completion.
- Download only the selected video and required torrent metadata; avoid downloading unrelated files in multi-file torrents.
- Treat torrent paths and metadata as untrusted. Normalize paths and reject path traversal or invalid entries before writing to storage.

### 2.2 Background job lifecycle

Torrent work must not block API request handling. A request creates or reuses a durable job and returns its identifier. The UI can poll job state and readiness independently.

Suggested states:

`queued -> downloading -> streamable -> complete`

Failures transition to `failed` with a safe, user-visible reason and retryability information. `streamable` does not mean the torrent is complete.

Persist job state and torrent resume data so a service restart can reconcile active downloads instead of creating duplicates or falsely reporting completion.

The UI must label lifecycle and percentage separately. It may show `99.9% · still downloading`, but it must show `100% · download complete` only when the backend reports `complete`; visual rounding must never imply completion.

### 2.3 Piece priorities and readiness

- Prioritize the selected video's initial pieces and its final pieces early. The final pieces can contain container index/metadata needed for playback.
- Readiness requires the first video frame to be verified and decodable, plus any container metadata required by the selected playback mode. Further media bytes are requested and prioritized as the player consumes them.
- Readiness is evaluated for the selected video/output, not by a fixed byte count. Container and codec differences make a byte-only threshold unreliable.
- When a client requests a byte range that is not yet available during direct playback, raise the priority of the missing torrent pieces and wait for them. Waiting must be bounded; on timeout, return a retryable response and expose current job progress rather than occupying a request indefinitely.

### 2.4 Playback and transcoding modes

Use one media URL with explicit playback modes:

| Media state | Delivery behavior | Seeking |
|---|---|---|
| Incomplete, browser-compatible source | Direct byte-range delivery. Map requested file offsets to torrent pieces, prioritize missing pieces, and wait for verified data. | Supported while downloading |
| Incomplete, requires conversion | Sequential transcoder output after the input is readable in order. Do not claim byte-range support. | Not supported until conversion is complete |
| Complete, browser-compatible source | Serve the stored media with HTTP byte ranges. | Supported |
| Complete, requires conversion | Produce and store a browser-compatible output, then serve that output with HTTP byte ranges. | Supported |

The player must distinguish a sequential partial-transcode response from a range-capable response using response headers and readiness state. Test this behavior in Chrome and Firefox before relying on it.

Prefer remuxing when the codecs are already browser-compatible; transcode only when required. For completed conversion, a conventional MP4 with its index at the beginning is the initial candidate for range playback. For incomplete conversion, test a sequential fragmented-MP4 output with the actual browser/player combination; do not advertise seeking for it.

The selected video becomes streamable as soon as its opening video frame and required container metadata can be verified and decoded. If an input format cannot be safely/properly decoded from the available prefix, defer readiness until enough data arrives or until the full file is available; report the reason rather than presenting a success-shaped fallback.

### 2.5 Subtitle behavior

- Search and download five results total, filtered to English (`en`), French (`fr`), German (`de`), and Italian (`it`).
- Store the downloaded subtitle files and their language/provider metadata beside the selected media asset.
- Use the selected video's title/filename as the initial search query; allow the frontend to provide a corrected title when filename matching is poor.
- Keep provider access behind a replaceable adapter. Provider terms, API credentials, rate limits, four-language availability, and permitted redistribution must be checked before integration.

### 2.6 Retention and cleanup

Completed files are retained indefinitely until an operator runs a host-side cleanup script. The script enters the container and removes downloaded assets and their matching database/job records.

Cleanup must stop or drain active torrent/transcode work before deletion, be safe to rerun, and leave the database and storage consistent. If a failure occurs between filesystem deletion and database updates, startup reconciliation must identify and repair stale records. The cleanup script is an operator action, not an unauthenticated public API endpoint.

### 2.7 Trust and deployment boundary

- The POC has no user authentication and must bind to loopback/local demo access only.
- The operator is responsible for selecting a legal/royalty-free torrent from the approved source workflow. Provenance capture is out of scope for this service.
- Treat uploaded torrent metadata, media bytes, and subtitle files as untrusted input.
- Restrict filesystem writes to the configured storage volume. Apply size limits to torrent uploads and resource/time limits to media probing and transcoding.
- Do not interpolate user-controlled names or paths into shell commands. Invoke media tooling with argument arrays and isolated working directories.
- Torrent tracker and peer connections are outbound network activity. Container/network egress policy must be reviewed before running the POC on a shared or public network.
- Follow the repository's existing logging restriction; surface job failures through API state without exposing secrets or user-supplied file contents.

## 3. Proposed component boundaries

```text
Browser UI
   | job, readiness, subtitles
   v
HTTP API and job orchestrator ---- Metadata repository (PostgreSQL)
   |                                     |
   +---- Torrent-engine adapter          +---- Docker file-storage volume
   |          |                                  ^
   |          +---- BitTorrent engine -----------+
   |
   +---- Playback/range coordinator
   |          +---- direct verified-byte reader
   |          +---- isolated FFmpeg worker
   |
   +---- Subtitle-provider adapter ---- External subtitle API
```

Responsibilities:

- **HTTP API:** Validate inputs, expose job/media/subtitle resources, and return range/stream responses.
- **Job orchestrator:** Own idempotency, job state transitions, media selection, readiness, retry behavior, and cleanup coordination.
- **Torrent-engine adapter:** Isolate engine-specific APIs for piece/file priorities, progress, resume data, and cancellation.
- **Playback/range coordinator:** Translate client byte ranges into media-file offsets and torrent piece requests; keep direct playback distinct from sequential transcoder output.
- **Transcoder worker:** Probe/remux/convert media in a separate process with resource limits. It does not own torrent lifecycle or API state.
- **Subtitle-provider adapter:** Search and download subtitle results without coupling the domain model to one vendor.
- **Metadata repository and file storage:** Persist job and asset metadata separately from large media/subtitle files.

## 4. API contract sketch

The implemented POC routes are:

| Operation | Contract |
|---|---|
| Submit torrent | `POST /api/torrents` with the raw `.torrent` file as `application/x-bittorrent`; return `202` with job/torrent ID, or reuse the existing infohash job. |
| Inspect job/files | `GET /api/torrents/{id}` returns status, progress, candidate files, selected file, and failure details. |
| Select video | `PUT /api/torrents/{id}/selection` selects one validated video file when the default is not desired. |
| Check readiness | `GET /api/torrents/{id}/readiness` returns readiness, playback mode, and a reason when the file is not ready. |
| Play media | `GET /api/torrents/{id}/stream`; support `Range`/`206` when in a range-capable mode. For missing direct-play ranges, prioritize pieces and wait within the configured request deadline. |
| Search/download subtitles | `POST /api/torrents/{id}/subtitles` requests five matches across the requested languages and returns downloaded track metadata or per-result failures. |
| List subtitles | `GET /api/torrents/{id}/subtitles` returns available tracks, language, and provider metadata. |
| Serve subtitle | `GET /api/subtitles/{id}` returns a downloaded subtitle file. |

Use consistent API errors for invalid torrent metadata, unsupported/no video selection, unavailable pieces, provider failures, and transcoder failures. Job status remains the source of truth for asynchronous work.

## 5. POC technology decisions

These decisions apply only to this local, single-host POC. Revisit them before production deployment.

### 5.1 Torrent engine: libtorrent-rasterbar

**Decision:** Use the `libtorrent` Python binding as the low-level BitTorrent engine behind the torrent-engine adapter. Pin version `2.1.3` for the POC.

Why:

- Its documented torrent-handle API exposes file and piece priorities, piece deadlines, file progress, resume data, and torrent lifecycle. Those controls let this application implement first/tail prioritization and on-demand range priorities itself.
- It is an engine, not a complete torrent-to-browser streaming product. The API, job state, storage policy, and playback behavior remain owned by Torrentmanagement.
- Do not use its WebTorrent-specific API or add a webtorrent/peerflix/pulsar-style all-in-one streaming layer.

**Alternative:** aria2 documents prioritizing the head and tail byte ranges of BitTorrent files, which is attractive for startup. The libtorrent handle API is the stronger initial candidate for finer per-piece priorities when a particular requested playback range arrives. Revisit aria2 if the POC only needs fixed head/tail priorities and libtorrent's build/binding complexity is too high.

PyPI listed `libtorrent 2.1.3` as the latest release on 2026-11-24, with CPython 3.13 Linux wheels; Snyk reported no known direct vulnerabilities for that release at the time checked. Recheck transitive/container dependencies before production use.

### 5.2 API/runtime: Python 3.13, FastAPI, and Uvicorn

**Decision:** Implement the API in Python 3.13 with FastAPI `0.165.0`, Uvicorn `0.54.0`, and psycopg `3.3.9`. Serve the static POC frontend from the same API process. Use synchronous endpoints for filesystem/torrent operations that wait, and stream response bodies incrementally; keep the torrent worker asynchronous relative to request creation.

FastAPI provides typed request/response contracts and Uvicorn serves the single local process. A Go service or a TypeScript service with a separate torrent daemon would add a process/adapter boundary without benefiting this single-service POC. Direct and resolved transitive Python dependencies are pinned in `requirements.txt`; the Python base image is digest-pinned. Recheck all dependencies and container packages before production use.

### 5.3 Metadata and file storage: PostgreSQL plus separate Docker volumes

**Decision:** Use the official PostgreSQL 19 Alpine image for metadata, psycopg as the Python adapter, and separate Docker-managed persistent volumes for database files and torrent/media/subtitle payloads. Keep PostgreSQL private on the Compose network; publish only the loopback API port.

PostgreSQL enforces infohash uniqueness and job/subtitle relationships, while large media remains outside the database as files. The application uses a dedicated non-superuser role initialized from `.env`; a separate PostgreSQL bootstrap account is not passed to the API. Keep the repository interface independent from the driver so the domain and HTTP contracts do not depend on PostgreSQL-specific row types.

The metadata represents torrent infohash, job state, selected torrent file, source/output paths, completion/readiness, conversion state, and subtitle assets. Enforce a unique infohash. Torrent uploads are capped at 10 MiB and the aggregate content size advertised by a torrent is capped at 200 GiB by default; no host-wide disk quota is enforced.

**Cutover:** The POC starts PostgreSQL with an empty database and does not migrate the existing SQLite records. The SQLite file and downloaded files are left untouched in the existing torrent-data volume. Re-uploading a torrent metadata file creates a fresh job and allows libtorrent to verify existing media payloads.

The selected PostgreSQL image digest is `sha256:cac45fb483caee3668946088a1c0532db89d5285c28dbfeac889b4068296e06f`. PostgreSQL 19 was the latest stable major release on 2026-11-26. A public scan of this exact image digest reported no high/critical findings (the reachable finding was scored moderate); re-scan the image and update its digest before production use.

### 5.4 Media processing: FFmpeg as a constrained external worker

**Decision:** Use the FFmpeg command-line tools as a separate, constrained worker process, not as a bundled torrent-streaming product or as the owner of download orchestration. Use the current Debian stable FFmpeg package in the POC image and update it through Debian security releases.

- Probe input and verify codec/container support before marking playback ready.
- Direct-play supported browser-compatible media; remux or transcode only when necessary.
- For complete converted media, write a browser-compatible MP4 candidate with its index at the front, then serve ranges from the completed stored output.
- For incomplete conversion, use sequential fragmented output only after a Chrome/Firefox spike verifies the chosen format and headers. Do not offer ranges or seeking for that output.
- The POC bounds probe and conversion duration and limits concurrent partial-transcode workers. CPU, memory, and converted-output quotas still need explicit limits before production use. The Debian Trixie package was `7:7.1.5-0+deb13u1` when checked; review Debian security advisories on each dependency update.

### 5.5 Subtitle provider: SubDL

**Decision:** Use SubDL's v2 search/download API behind the subtitle-provider adapter. The provider documents language filters and lists all four requested languages (English, French, German, Italian). Request five total results across those languages and download them using the provider's download endpoint.

The API key is optional for startup but required to invoke the provider; configure it through `SUBDL_API_KEY` and never commit it. The POC is local/demo-only. SubDL's terms distinguish free API use from commercial/shared service use, so review the current plan and terms before exposing the API to other users or using it commercially. Subtitle download permissions remain subject to the source files' rights.

### 5.6 Frontend and local operations

**Decision:** Use plain HTML, CSS, and JavaScript with no frontend package manager for the responsive demo UI. Bind the container port to host loopback only. Name the Compose project explicitly so `make clean` and `make prune` affect only Torrentmanagement resources. `prune` removes this project's Compose volume and local image; it must never invoke global `docker system prune`.

## 6. Failure modes and operational behavior

| Failure | Expected behavior |
|---|---|
| Invalid/unsupported `.torrent` | Reject before creating a download job; return a clear validation error. |
| Torrent has no supported video | Keep no successful media record; report that the operator must choose a supported torrent. |
| Selected piece/range is unavailable | Raise its priority and wait up to a bounded deadline; then return a retryable response and keep the download job active. |
| No peers or stalled transfer | Keep the job non-blocking and report stalled/active progress; allow a later retry without creating a duplicate infohash job. |
| Partial media cannot be probed/decoded | Keep readiness false and explain whether more pieces or complete download is required. |
| FFmpeg/provider failure | Mark that operation failed separately from the torrent download; preserve a retry path and never report a successful output that does not exist. |
| Cleanup races with work | Stop/drain jobs before deleting; make cleanup idempotent and reconcile database/filesystem state on restart. |
| Process/container restart | Restore valid torrent resume state and reconcile stored files against metadata before serving playback. |

## 7. Acceptance gates

1. Submitting the same torrent twice reuses one job and one stored asset, including after service restart.
2. The selected file prefers browser-native MP4/WebM candidates, falls back to the largest supported video, and an explicit override is honored.
3. Startup pieces receive higher priority; readiness remains false until the opening video frame is verified and playable.
4. For direct playback, an unavailable requested byte range raises the corresponding piece priorities and waits for verified pieces; a bounded timeout returns a retryable result.
5. Incomplete transcoded playback is sequential and non-seekable. Completed converted output supports correct HTTP range responses and seeking.
6. Five subtitles total are downloaded for the requested language set, or the API reports a partial/provider failure without fabricating missing tracks.
7. Host cleanup removes assets and matching metadata, handles active work safely, and can be run repeatedly.
8. The UI never labels an incomplete job complete based on rounded progress, and the local demo is not reachable as an unauthenticated service from outside the intended local environment.

## 8. Open decisions and revisit triggers

- **Subtitle provider and terms:** Decide after testing real search/download responses in all four languages and reviewing current API terms and quotas.
- **Partial transcoding format:** Validate fragmented output, startup latency, and Chrome/Firefox playback with representative legal test files before treating the approach as settled.
- **Request wait deadline and concurrency limits:** Set measurable values after observing download latency and frontend player retry behavior.
- **Storage exhaustion policy:** Indefinite retention requires an operator capacity/cleanup policy before the POC runs for extended periods.

Revisit the design if the service becomes multi-user/public, needs multiple backend replicas, adds authenticated access, or must support adaptive bitrate streaming. Those changes affect authorization, storage coordination, job ownership, and delivery contracts.

## 9. References checked

- Project constraints and existing media workflow: [root README](../README.md)
- Architecture document guidance: [architecture-documents.instructions.md](../.github/instructions/architecture-documents.instructions.md)
- libtorrent torrent-handle API, including piece/file priority and deadlines: [Torrent Handle reference](https://libtorrent.org/reference-Torrent_Handle.html)
- libtorrent Python binding build requirements: [Python binding documentation](https://libtorrent.org/python_binding.html)
- aria2 head/tail piece priority option: [aria2 manual](https://github.com/aria2/aria2/blob/master/doc/manual-src/en/aria2c.rst)
- SubDL API capabilities: [SubDL developer documentation](https://subdl.com/developers)
- OpenSubtitles API capabilities: [OpenSubtitles API reference](https://ai.opensubtitles.com/api-docs)
- FFmpeg muxer/output format options: [FFmpeg formats documentation](https://ffmpeg.org/ffmpeg-formats.html)
- FFmpeg security fixes by release: [FFmpeg security page](https://ffmpeg.org/security.html)
- PostgreSQL 19 release announcement: [PostgreSQL Global Development Group](https://www.postgresql.org/about/news/postgresql-19-released-3449/)
- PostgreSQL official image: [Docker Hub](https://hub.docker.com/_/postgres/)
- Exact PostgreSQL 19 Alpine image scan: [BaseImage report](https://baseimage.io/docker-security-scanner/report/postgres/19.0-alpine)
- psycopg 3.3.9 vulnerability and maintenance status: [Snyk package report](https://security.snyk.io/package/pip/psycopg)
- FastAPI package version: [PyPI](https://pypi.org/project/fastapi/); direct advisory summary: [Snyk](https://security.snyk.io/package/pip/fastapi)
- Uvicorn package version: [PyPI](https://pypi.org/project/uvicorn/); direct advisory summary: [Snyk](https://security.snyk.io/package/pip/uvicorn)
- libtorrent package version and wheels: [PyPI](https://pypi.org/project/libtorrent/); direct advisory summary: [Snyk](https://security.snyk.io/package/pip/libtorrent)
- SubDL API and supported languages: [developer documentation](https://subdl.com/developers), [language list](https://subdl.com/api-files/language_list.json), and [terms](https://subdl.com/terms)
- Debian FFmpeg package and security status: [Trixie package](https://packages.debian.org/trixie/ffmpeg) and [Debian security tracker](https://security-tracker.debian.org/tracker/source-package/ffmpeg)
