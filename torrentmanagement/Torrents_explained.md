# How BitTorrent Downloads Work and What a `.torrent` File Contains

## Table of Contents

1.  [Introduction](#1-introduction)
2.  [The Main Components of
    BitTorrent](#2-the-main-components-of-bittorrent)
3.  [What Happens During a Torrent
    Download](#3-what-happens-during-a-torrent-download)
4.  [How Peers Find Each Other](#4-how-peers-find-each-other)
5.  [How Files Are Divided into Pieces and
    Blocks](#5-how-files-are-divided-into-pieces-and-blocks)
6.  [How Integrity Verification
    Works](#6-how-integrity-verification-works)
7.  [The Exact Structure of a `.torrent`
    File](#7-the-exact-structure-of-a-torrent-file)
8.  [Bencoding: The Encoding Used by Torrent
    Metadata](#8-bencoding-the-encoding-used-by-torrent-metadata)
9.  [The `info` Dictionary in Detail](#9-the-info-dictionary-in-detail)
10. [Trackers, Web Seeds, and Other Optional
    Fields](#10-trackers-web-seeds-and-other-optional-fields)
11. [Info Hashes: Identifying a
    Torrent](#11-info-hashes-identifying-a-torrent)
12. [Magnet Links vs. `.torrent`
    Files](#12-magnet-links-vs-torrent-files)
13. [What a Torrent File Does Not
    Contain](#13-what-a-torrent-file-does-not-contain)
14. [A Worked Example](#14-a-worked-example)
15. [Privacy, Security, and Practical
    Considerations](#15-privacy-security-and-practical-considerations)
16. [Glossary](#16-glossary)
17. [Further Reading](#17-further-reading)

------------------------------------------------------------------------

## 1. Introduction

BitTorrent is a peer-to-peer (P2P) protocol for distributing data.
Instead of requiring every downloader to retrieve an entire file from
one central server, BitTorrent lets participants exchange parts of the
data with one another.

A participant downloading a torrent is commonly called a **peer**. A
peer that has the complete content and is uploading it to others is a
**seed**. A peer that is still downloading is often called a **leecher**
or, more neutrally, an incomplete peer. An incomplete peer can upload
pieces it has already verified while it downloads the remaining pieces.

A `.torrent` file is not normally the content being downloaded. It is a
small metadata file that describes the content and provides information
that helps a BitTorrent client find other participants and verify
downloaded data.

The key distinction is:

-   **Torrent metadata** describes the files, their sizes, the piece
    layout, and usually one or more ways to discover peers.
-   **Torrent payload** is the actual content---documents, videos,
    archives, software, or other files---that peers exchange.

This document focuses on the widely deployed BitTorrent v1 format, the
v2 format, and hybrid torrents. Where a field differs between versions,
that difference is identified.

## 2. The Main Components of BitTorrent

### 2.1 BitTorrent client

The client is the application that implements the protocol. Examples
include qBittorrent, Transmission, Deluge, and other compatible
applications.

A client typically:

-   Reads `.torrent` metadata or a magnet link.
-   Calculates the torrent's identifier (the info hash).
-   Discovers peers through trackers, DHT, peer exchange, or local
    discovery.
-   Connects to peers and negotiates which pieces each side has.
-   Requests blocks of data.
-   Verifies received data against the hashes in the torrent metadata.
-   Writes verified data to disk.
-   Uploads available pieces to other peers.

### 2.2 Peers

A peer is a BitTorrent client participating in a swarm. A **swarm** is
the group of peers participating in the distribution of a particular
torrent.

Peers can have different subsets of the content. They exchange those
subsets, allowing the swarm to distribute the complete content without
every peer needing a full copy at the beginning.

### 2.3 Seeders

A seeder has all the content described by the torrent and can offer any
piece to other peers.

A torrent with several reachable seeders will often be easier to
download than one with very few seeders. However, the number shown by a
tracker or client is not necessarily a perfect count of all currently
reachable participants.

### 2.4 Trackers

A tracker is a coordination service. A client announces that it is
participating in a torrent and asks the tracker for peer contact
information.

A tracker generally helps peers find one another. It does **not**
normally store or transmit the torrent's payload.

### 2.5 Distributed Hash Table (DHT)

DHT is a decentralized peer-discovery mechanism. In the BitTorrent
Mainline DHT, peers use the torrent's identifier to locate other
participants without relying exclusively on a central tracker.

DHT is commonly used by trackerless torrents and can also supplement
tracker-based discovery.

### 2.6 Peer Exchange (PEX)

Peer Exchange allows connected peers to share information about other
peers they know. It can expand peer discovery after a client has
connected to at least one peer.

### 2.7 Web seeds

A web seed is an HTTP or HTTPS source from which a client can retrieve
torrent data. It can act as an additional source alongside ordinary
peers.

### 2.8 The swarm

The swarm is the collection of peers associated with a torrent's info
hash. A client may discover peers through several mechanisms and connect
to a subset of them.

------------------------------------------------------------------------

## 3. What Happens During a Torrent Download

The following sequence describes a typical download.

### Step 1: The client obtains metadata

The user opens a `.torrent` file or provides a magnet link.

With a `.torrent` file, the client can immediately read the metadata.
With a magnet link, it generally needs to retrieve the metadata from
peers before it can know the complete file layout.

### Step 2: The client identifies the torrent

The client extracts the `info` dictionary and calculates the relevant
info hash:

-   BitTorrent v1: SHA-1 of the exact bencoded `info` dictionary.
-   BitTorrent v2: SHA-256-based identifier of the exact bencoded `info`
    dictionary, represented as a 32-byte value.
-   Hybrid: includes metadata for both v1 and v2 compatibility.

The info hash identifies the torrent's metadata, not a particular user's
download session.

### Step 3: The client discovers peers

The client contacts the configured trackers and/or uses DHT, PEX, and
possibly local peer discovery. It may also use web seeds.

These mechanisms return or reveal network endpoints that may be
participating in the same swarm.

### Step 4: The client connects to peers

Peers establish TCP or uTP connections and perform the BitTorrent
handshake. The handshake identifies the protocol and the torrent the
connection concerns.

The peers then exchange messages describing their state, such as which
pieces they have, whether they are interested in one another's data, and
whether a peer is temporarily choking another peer.

### Step 5: The client selects pieces to request

A torrent is divided into pieces. A peer advertises which pieces it
possesses using a bitfield or related messages.

The downloading client chooses pieces it still needs and requests blocks
from peers that have them.

Piece-selection strategies can include:

-   **Rarest first:** prefer pieces that are less common in the swarm,
    helping preserve availability.
-   **Random first:** obtain an initial piece quickly so the client can
    begin uploading.
-   **Sequential selection:** request pieces in file order, sometimes
    useful for streaming or previewing.
-   **Endgame mode:** when only a few blocks remain, request them from
    multiple peers to reduce the chance that one slow peer delays
    completion. Duplicate responses are handled by cancelling
    unnecessary requests.

Actual strategies vary by client.

### Step 6: Data is transferred in blocks

A piece is usually requested as smaller blocks. A peer sends a block in
response to a request.

The requesting client tracks which blocks have arrived and assembles
them into the relevant piece.

### Step 7: The piece is verified

Once all blocks for a piece have arrived, the client calculates its hash
and compares it with the expected hash in the torrent metadata.

If the hash matches, the piece is accepted as valid. If it does not, the
piece is rejected and must be obtained again.

### Step 8: Verified pieces are shared

A client can generally upload verified pieces to other peers before its
own download is complete. This is one of the central features that makes
BitTorrent distribution scalable.

### Step 9: The download completes

When every required piece has been downloaded and verified, the client
has the complete content. It can continue seeding, meaning it makes the
complete content available to other peers.

------------------------------------------------------------------------

## 4. How Peers Find Each Other

BitTorrent separates **peer discovery** from **data transfer**. Finding
a peer does not mean that peer necessarily has every piece, and a
tracker is not the server from which the payload must be downloaded.

### 4.1 Tracker announces

A client sends an announce request to a tracker. Depending on the
tracker protocol and request, the announce can include information such
as:

-   The torrent's info hash.
-   The client's peer ID.
-   The client's listening port.
-   The number of bytes downloaded, uploaded, and left to download.
-   An event such as `started`, `completed`, or `stopped`.
-   Optional fields such as an IP address override or tracker-specific
    parameters.

The tracker may respond with a compact or non-compact list of peers,
along with interval information indicating when the client should
announce again.

Trackers can use HTTP(S) or UDP-based announce protocols.

### 4.2 DHT lookup

In DHT, a client uses the torrent's identifier as a lookup key. Nodes in
the distributed network help route the lookup toward nodes that know
about peers for that torrent.

DHT is decentralized: there is no single tracker that must be online for
every lookup.

### 4.3 Peer Exchange

Once connected, a peer can share endpoints for other peers in the same
swarm. This helps clients discover additional participants.

### 4.4 Local Peer Discovery

Local Peer Discovery (LPD) can help clients find other peers on the same
local network. It is useful when multiple devices on a LAN are
downloading the same content.

### 4.5 Discovery is not a guarantee

A discovered endpoint may be offline, unreachable, behind restrictive
NAT or firewall rules, or no longer participating. Clients retry and
combine discovery methods.

------------------------------------------------------------------------

## 5. How Files Are Divided into Pieces and Blocks

### 5.1 Pieces

BitTorrent does not generally transfer an entire file as one unit. The
torrent metadata defines a piece length, and the content is treated as a
sequence of pieces.

For a simple single-file torrent:

-   Total content length: 10 MiB.
-   Piece length: 1 MiB.
-   Number of pieces: 10.

For a multi-file torrent, the files are treated as a concatenated byte
stream for the purpose of the v1 piece layout. A piece can therefore
span a boundary between two files.

The final piece may be shorter than the standard piece length.

### 5.2 Blocks

A piece is subdivided into blocks for network requests. In the
traditional BitTorrent peer-wire protocol, a common block request is 16
KiB, although protocol extensions and implementations can vary.

The distinction is important:

-   **Piece:** the unit described by the torrent's piece-hash metadata.
-   **Block:** a smaller unit requested and transferred over a peer
    connection.

A client normally verifies a complete piece rather than treating each
individual block as independently authenticated by the v1 piece hash.

### 5.3 Why use pieces?

Pieces allow many peers to contribute different parts of a large
download. They also provide a practical unit for integrity checking and
scheduling.

A client can download piece 7 from one peer, piece 2 from another, and
piece 9 from a third, then reconstruct the original byte sequence
locally.

------------------------------------------------------------------------

## 6. How Integrity Verification Works

Integrity verification ensures that received data matches the content
described by the torrent metadata.

### 6.1 BitTorrent v1

In v1, the `pieces` field contains a concatenated sequence of 20-byte
SHA-1 hashes. Each hash corresponds to one piece in the torrent's
concatenated data stream.

If the piece length is `L` and the total payload length is `T`, the
number of pieces is:

`ceil(T / L)`

The expected length of the `pieces` byte string is therefore:

`20 × ceil(T / L)`

For each completed piece, the client calculates SHA-1 over that piece's
bytes and compares the result with the corresponding 20-byte entry.

A mismatch means the data does not match the expected piece hash. The
client must discard or overwrite the invalid piece data and retrieve it
again.

**Important:** SHA-1 is used here for compatibility and
accidental-corruption detection, not as a modern guarantee against a
malicious party constructing collisions. BitTorrent v2 uses
SHA-256-based Merkle hashing.

### 6.2 BitTorrent v2

BitTorrent v2 uses SHA-256 and a Merkle-tree structure for file data.
This supports more granular verification and avoids relying on the v1
flat list of SHA-1 piece hashes.

The `file tree` metadata describes the files, and each file's metadata
includes a root hash used by the Merkle structure. Piece layers provide
the hashes needed for verification at the relevant piece granularity.

### 6.3 What hashes do and do not prove

A matching hash demonstrates that the received bytes match the bytes
represented by the expected hash, subject to the security properties of
the hash function and the authenticity of the metadata.

It does not prove that:

-   The content is safe to open.
-   The content is legally distributable.
-   The content comes from a trustworthy publisher.
-   The filename or extension accurately describes the file.
-   The metadata itself was obtained from a trusted source.

A malicious torrent can consistently describe malicious files. Hash
verification is an integrity mechanism, not antivirus software or a
publisher-signature system.

------------------------------------------------------------------------

## 7. The Exact Structure of a `.torrent` File

A `.torrent` file is a bencoded dictionary. At its outermost level, it
contains keys and values describing the torrent.

A typical v1 torrent has a structure conceptually similar to:

``` text
{
  "announce": "https://tracker.example/announce",
  "announce-list": [
    ["https://tracker.example/announce"],
    ["udp://tracker.example:80/announce"]
  ],
  "comment": "Example torrent",
  "created by": "Example Client",
  "creation date": 1700000000,
  "encoding": "UTF-8",
  "info": {
    "name": "example-folder",
    "piece length": 262144,
    "pieces": "<binary concatenation of 20-byte SHA-1 hashes>",
    "files": [
      {
        "length": 1234567,
        "path": ["video.mkv"]
      },
      {
        "length": 5000,
        "path": ["readme.txt"]
      }
    ]
  }
}
```

This is a human-readable illustration, not literal bencoded file
content. Real torrent files use bencoding, and hash fields contain
binary bytes rather than printable placeholder text.

The exact keys present depend on the torrent version and optional
metadata. Not every `.torrent` file contains every field listed below.

### 7.1 Top-level fields

  ------------------------------------------------------------------------
  Field                   Type                    Meaning
  ----------------------- ----------------------- ------------------------
  `announce`              byte string             Primary tracker announce
                                                  URL, when present.

  `announce-list`         list of lists           Optional tracker tiers.
                                                  Trackers in a tier are
                                                  generally treated as
                                                  alternatives or peers in
                                                  the same tier by
                                                  clients.

  `comment`               byte string             Optional human-readable
                                                  comment.

  `created by`            byte string             Optional name/version of
                                                  the software that
                                                  created the torrent.

  `creation date`         integer                 Optional Unix timestamp
                                                  indicating when the
                                                  torrent was created.

  `encoding`              byte string             Optional
                                                  character-encoding hint
                                                  for text fields;
                                                  historical clients may
                                                  interpret it
                                                  differently.

  `info`                  dictionary              The essential metadata
                                                  dictionary used to
                                                  identify the torrent.

  `url-list`              byte string or list of  Optional web-seed URL or
                          byte strings            URLs, depending on the
                                                  format/implementation.

  `httpseeds`             list                    Optional HTTP seed URLs
                                                  in supported
                                                  implementations.

  `nodes`                 list                    Optional DHT bootstrap
                                                  node information,
                                                  typically host/port
                                                  pairs.

  `publisher`             byte string             Optional publisher
                                                  metadata in older or
                                                  less common extensions.

  `publisher-url`         byte string             Optional publisher URL
                                                  in older or less common
                                                  extensions.
  ------------------------------------------------------------------------

The `info` dictionary is especially important: its exact bencoded bytes
are hashed to form the torrent's info hash.

### 7.2 The `info` dictionary

The `info` dictionary describes the payload and the way it is divided
and verified.

Common v1 fields:

  -----------------------------------------------------------------------
  Field                   Type                    Meaning
  ----------------------- ----------------------- -----------------------
  `name`                  byte string             Suggested name for the
                                                  single file or
                                                  top-level directory.

  `piece length`          integer                 Number of bytes in each
                                                  full piece, except
                                                  possibly the final
                                                  piece.

  `pieces`                byte string             Concatenated 20-byte
                                                  SHA-1 hashes, one per
                                                  piece, in v1.

  `length`                integer                 Total length of a
                                                  single-file payload.

  `files`                 list of dictionaries    File entries for a
                                                  multi-file torrent.

  `private`               integer                 Optional
                                                  private-torrent flag;
                                                  `1` indicates private
                                                  behavior under the
                                                  relevant conventions.
  -----------------------------------------------------------------------

A v1 torrent uses either `length` for a single-file torrent or `files`
for a multi-file torrent.

### 7.3 Single-file layout

A single-file torrent typically contains:

``` text
info = {
  "length": 10485760,
  "name": "archive.zip",
  "piece length": 262144,
  "pieces": "..."
}
```

Interpretation:

-   `name`: suggested output filename.
-   `length`: 10,485,760 bytes, or 10 MiB.
-   `piece length`: 262,144 bytes, or 256 KiB.
-   `pieces`: the ordered SHA-1 hash list for the data pieces.

### 7.4 Multi-file layout

A multi-file torrent typically contains:

``` text
info = {
  "files": [
    {
      "length": 1048576,
      "path": ["folder", "video.mp4"]
    },
    {
      "length": 2048,
      "path": ["folder", "notes.txt"]
    }
  ],
  "name": "download",
  "piece length": 262144,
  "pieces": "..."
}
```

Each file dictionary commonly contains:

  -----------------------------------------------------------------------
  Field                   Type                    Meaning
  ----------------------- ----------------------- -----------------------
  `length`                integer                 File size in bytes.

  `path`                  list of byte strings    Path components
                                                  relative to the
                                                  torrent's top-level
                                                  directory.

  `attr`                  byte string             Optional file
                                                  attributes in
                                                  extensions, for example
                                                  to mark padding or
                                                  symlink-related
                                                  entries.

  `md5sum`                byte string             Optional legacy MD5
                                                  checksum; not generally
                                                  used as the primary
                                                  BitTorrent integrity
                                                  mechanism.

  `symlink path`          list                    Optional symlink target
                                                  path in supported
                                                  extensions.
  -----------------------------------------------------------------------

The `name` field is normally the top-level directory name. Each `path`
is relative to that directory.

**Path safety:** Clients should sanitize paths and prevent entries from
escaping the selected download directory. Torrent metadata is untrusted
input; a client should not blindly write arbitrary paths supplied by a
torrent.

### 7.5 File order and piece boundaries

For v1 multi-file torrents, files are concatenated in the order they
appear in the `files` list when computing the piece sequence. A piece
can begin at the end of one file and continue into the next.

This is why the piece hashes describe the torrent's overall byte stream,
not necessarily one independent hash per file.

------------------------------------------------------------------------

## 8. Bencoding: The Encoding Used by Torrent Metadata

Bencoding is a compact serialization format used by BitTorrent metadata.
It has four basic data types:

1.  Integers
2.  Byte strings
3.  Lists
4.  Dictionaries

### 8.1 Integers

An integer is encoded as:

`i<number>e`

Examples:

  Meaning   Bencoded form
  --------- ---------------
  42        `i42e`
  0         `i0e`
  -7        `i-7e`

The `i` starts the integer and `e` ends it.

### 8.2 Byte strings

A byte string is encoded as:

`<byte-count>:<bytes>`

Examples:

-   `4:test` represents the four bytes `test`.
-   `5:hello` represents the five bytes `hello`.

The length is a count of bytes, not necessarily a count of Unicode
characters. Torrent metadata can contain arbitrary binary data, so a
parser must not assume every byte string is ordinary text.

### 8.3 Lists

A list is encoded as:

`l<item-1><item-2>...e`

Example:

`l4:spam4:eggse`

This represents a list containing the byte strings `spam` and `eggs`.

### 8.4 Dictionaries

A dictionary is encoded as:

`d<key><value><key><value>...e`

Dictionary keys are byte strings. In canonical bencoding, keys are
sorted lexicographically by their raw byte representation.

Example:

`d3:cow3:moo4:spam4:eggse`

This represents a dictionary with:

-   `cow` → `moo`
-   `spam` → `eggs`

### 8.5 Why byte-accurate parsing matters

A torrent parser must preserve the exact byte representation of the
`info` dictionary when calculating its info hash.

If a program decodes the dictionary into ordinary objects and then
re-encodes it differently, the resulting bytes may not match the
original bytes. Different key ordering, string handling, or integer
representation can change the hash.

A correct implementation should hash the original bencoded byte range
corresponding to the `info` dictionary, or otherwise guarantee an
exactly equivalent canonical representation under the applicable
specification.

------------------------------------------------------------------------

## 9. The `info` Dictionary in Detail

This section explains the most important v1 fields and the major v2
additions.

### 9.1 `name`

The suggested name of the payload:

-   For a single-file torrent, usually the suggested filename.
-   For a multi-file torrent, usually the top-level directory name.

It is metadata supplied by the torrent creator. It is not proof of the
content's identity or safety.

### 9.2 `piece length`

The nominal size of a piece in bytes.

For example:

`piece length = 262144`

means each full piece is 256 KiB. The last piece may contain fewer
bytes.

The piece length is selected by the torrent creator and affects the
number of hashes and the granularity of piece scheduling.

### 9.3 `pieces` (v1)

A binary byte string containing one SHA-1 digest per piece, concatenated
with no separators.

Each SHA-1 digest is 20 bytes. If there are 100 pieces, the `pieces`
value is 2,000 bytes long.

It is not a list of text hashes. A parser must split the raw byte string
into 20-byte chunks.

### 9.4 `length` (v1 single-file)

The total payload length in bytes for a single-file torrent.

This value is not the size of the `.torrent` metadata file. It is the
size of the content described by the torrent.

### 9.5 `files` (v1 multi-file)

A list of file dictionaries. Each file entry describes a file's length
and relative path. The order of these entries matters for the v1
concatenated data stream and piece hashes.

### 9.6 `private`

An optional integer flag. A value of `1` indicates that clients should
follow private-torrent behavior, notably avoiding DHT and other
peer-discovery mechanisms outside the tracker-based arrangement, as
specified by the ecosystem's conventions.

It is not encryption. It does not hide a user's IP address from peers or
trackers.

### 9.7 BitTorrent v2 fields

BitTorrent v2 changes the metadata and hashing model. Important `info`
fields include:

  -----------------------------------------------------------------------
  Field                   Type                    Meaning
  ----------------------- ----------------------- -----------------------
  `meta version`          integer                 Value `2` identifies v2
                                                  metadata.

  `file tree`             dictionary              Hierarchical
                                                  representation of files
                                                  and directories.

  `piece layers`          top-level dictionary    Maps file Merkle roots
                                                  to the corresponding
                                                  piece-layer hash data
                                                  for files that need it.
  -----------------------------------------------------------------------

In v2:

-   File data is verified using SHA-256-based Merkle trees.
-   The `file tree` represents the directory hierarchy rather than
    relying on the v1 `files` list.
-   File metadata can include a `length` and a `pieces root`.
-   The `pieces root` is the Merkle root for a file's piece hashes.
-   Piece-layer data supplies hashes at the piece level so clients can
    verify pieces efficiently.

A v2 torrent can represent files with different sizes and structures
more naturally than the v1 concatenated-stream model.

### 9.8 Hybrid torrents

A hybrid torrent includes metadata that allows compatible clients to
treat it as both a v1 and v2 torrent. This supports interoperability
between older v1 clients and newer v2-capable clients.

The metadata contains the relevant v1 and v2 structures. The v1 and v2
identifiers are not interchangeable: each is calculated according to its
respective rules.

------------------------------------------------------------------------

## 10. Trackers, Web Seeds, and Other Optional Fields

### 10.1 `announce`

A URL for the primary tracker. It is commonly an HTTP(S) or UDP tracker
URL.

This URL tells the client where to announce its participation. It does
not point to the downloaded file itself.

### 10.2 `announce-list`

A list of tracker tiers. A tier is a group of tracker URLs that a client
can try according to its tracker-selection policy.

For example, a torrent might include multiple trackers to improve the
chance of peer discovery if one tracker is unavailable.

### 10.3 `creation date`

A Unix timestamp: the number of seconds since 1970-01-01 00:00:00 UTC.

It records the time the torrent metadata was created, not necessarily
the date the payload was published or last modified.

### 10.4 `created by`

A text field that may identify the software used to generate the
torrent.

It is informational and can be set to any value by whoever created the
metadata.

### 10.5 `comment`

An optional comment written by the creator.

It should be treated as untrusted text.

### 10.6 `url-list` and `httpseeds`

These fields can describe HTTP-based sources for the payload. Clients
that support them may download data from those sources in addition to
peer connections.

### 10.7 `nodes`

Optional DHT bootstrap node entries. They can help a client join the DHT
network, but modern clients often have their own bootstrap
configuration.

### 10.8 Unknown fields

Bencoded dictionaries can contain extension or implementation-specific
fields. A robust parser should tolerate unknown fields where the
specification permits them, while still validating required fields and
applying safe path and size limits.

------------------------------------------------------------------------

## 11. Info Hashes: Identifying a Torrent

The **info hash** is derived from the exact bencoded representation of
the `info` dictionary.

It is used by BitTorrent to identify the torrent in peer discovery and
peer handshakes.

### 11.1 v1 info hash

For v1:

`SHA-1(bencoded_info_dictionary)`

The result is 20 bytes, commonly displayed as 40 hexadecimal characters.

### 11.2 v2 info hash

For v2:

`SHA-256(bencoded_info_dictionary)`

The result is 32 bytes, commonly displayed as 64 hexadecimal characters.

The v2 specification defines how this identifier is used in peer
discovery and magnet links.

### 11.3 Why hash the `info` dictionary?

The `info` dictionary describes the payload layout and integrity
metadata. Hashing it creates a compact identifier for that metadata.

Top-level fields such as comments or tracker URLs are outside the `info`
dictionary. Changing a tracker URL does not, by itself, change the info
hash, provided the `info` dictionary remains byte-for-byte identical.

Changing a field inside `info`---for example, the file layout, piece
length, or piece hashes---changes the info hash.

### 11.4 Info hash is not a file hash

A torrent's info hash is not the SHA-1 or SHA-256 checksum of the entire
downloaded file.

It identifies the torrent's metadata. The piece hashes or Merkle data
are what the client uses to verify payload data.

Two torrents can describe identical payload bytes but have different
info hashes if their `info` metadata differs---for example, because of a
different piece length or file layout.

------------------------------------------------------------------------

## 12. Magnet Links vs. `.torrent` Files

A magnet link is a URI that identifies a torrent without requiring the
user to download a `.torrent` file first.

A typical magnet link may look like:

``` text
magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567
&dn=Example
&tr=https%3A%2F%2Ftracker.example%2Fannounce
```

Common parameters include:

  -----------------------------------------------------------------------
  Parameter                           Meaning
  ----------------------------------- -----------------------------------
  `xt`                                Exact topic. Often contains a
                                      BitTorrent info hash, such as
                                      `urn:btih:` for v1 or `urn:btmh:`
                                      for a multihash-based identifier
                                      used with v2.

  `dn`                                Display name; optional and
                                      informational.

  `tr`                                Tracker URL; may appear more than
                                      once.

  `ws`                                Web-seed URL; may appear more than
                                      once.

  `xs`                                Exact source, an optional source
                                      from which metadata may be
                                      retrieved.

  `as`                                Acceptable source, an optional
                                      source hint.
  -----------------------------------------------------------------------

### 12.1 How a magnet download starts

A magnet link may initially provide only the info hash and optional
hints. The client:

1.  Reads the info hash.
2.  Uses DHT, trackers, or other discovery mechanisms to find peers.
3.  Connects to peers that support the metadata exchange extension.
4.  Requests the torrent metadata.
5.  Validates the retrieved metadata against the info hash.
6.  Starts the normal piece download process.

This metadata retrieval process is often called **metadata exchange** or
**magnet metadata retrieval**.

### 12.2 Main difference

  -----------------------------------------------------------------------
  `.torrent` file                     Magnet link
  ----------------------------------- -----------------------------------
  Contains the bencoded metadata      Usually contains an info hash and
  directly.                           optional hints.

  Can provide file names and sizes    Often needs metadata retrieval
  immediately.                        before showing the complete file
                                      list.

  May include tracker and web-seed    Can include tracker and web-seed
  information.                        parameters in the URI.

  Is a small metadata file.           Is a URI string.
  -----------------------------------------------------------------------

Neither format normally contains the payload itself.

------------------------------------------------------------------------

## 13. What a Torrent File Does Not Contain

A `.torrent` file generally does **not** contain:

-   The actual video, archive, program, document, or other payload.
-   A copy of every peer's data.
-   A list of all currently connected peers.
-   A guarantee that any peer is online.
-   A guarantee that the torrent will be downloadable.
-   A guarantee that the payload is safe or authentic.
-   A user's download history or identity.
-   A user's current IP address.
-   A password that decrypts the payload.
-   A cryptographic publisher signature by default.

The torrent metadata can include file names, paths, lengths, hashes,
tracker URLs, comments, and other metadata. These can reveal information
about the content and its distribution, but they are not the content
itself.

------------------------------------------------------------------------

## 14. A Worked Example

Suppose a single-file torrent describes a file with these properties:

-   Filename: `example.bin`
-   File size: 1,000,000 bytes
-   Piece length: 250,000 bytes

The number of pieces is:

`ceil(1,000,000 / 250,000) = 4`

The v1 `pieces` field must therefore contain:

`4 × 20 = 80 bytes`

Those 80 bytes represent four consecutive SHA-1 hashes:

-   Bytes 0--19: hash of piece 0.
-   Bytes 20--39: hash of piece 1.
-   Bytes 40--59: hash of piece 2.
-   Bytes 60--79: hash of piece 3.

The client can obtain the pieces from different peers:

  Piece   Possible source
  ------- -----------------
  0       Peer A
  1       Peer B
  2       Peer A
  3       Peer C

After receiving each complete piece, the client hashes it and checks the
corresponding expected digest. Once all four pieces pass verification,
the reconstructed file contains the original 1,000,000 bytes.

This example is deliberately simple. Real torrents can contain many
files, much smaller or larger pieces, optional padding files, and
multiple discovery sources.

------------------------------------------------------------------------

## 15. Privacy, Security, and Practical Considerations

### 15.1 IP address visibility

In ordinary BitTorrent peer connections, participating peers can
generally see the network address used by the other endpoint. Trackers
also receive connection and announce information.

BitTorrent should not be assumed to provide anonymity.

### 15.2 Private torrents are not encrypted

The `private` flag controls peer-discovery behavior in compatible
clients. It does not encrypt the traffic, conceal IP addresses from
connected peers, or make the swarm anonymous.

### 15.3 Metadata is untrusted input

A torrent file can be crafted by an untrusted party. Clients should
validate metadata, enforce reasonable size limits, sanitize file paths,
and avoid unsafe filesystem operations.

Potential concerns include:

-   Paths designed to escape the selected download directory.
-   Misleading filenames and extensions.
-   Extremely large or malformed metadata structures.
-   Unexpected symlink or padding-file entries.
-   Comments or names containing deceptive text.

### 15.4 A valid hash does not mean a safe file

A malicious file can have perfectly valid piece hashes. Hash
verification confirms consistency with the torrent metadata; it does not
establish that the payload is harmless.

Use reputable sources, keep software updated, and scan or inspect files
when appropriate.

### 15.5 Uploading is part of the protocol

BitTorrent is designed around sharing. A client may upload verified
pieces while downloading and may continue uploading after completion if
seeding is enabled.

### 15.6 Availability depends on the swarm

A torrent can become unavailable if no reachable peer has a needed
piece. A high peer count does not guarantee that every piece is
available, and a low count does not necessarily mean a torrent is
impossible to complete.

------------------------------------------------------------------------

## 16. Glossary

  -----------------------------------------------------------------------
  Term                                Definition
  ----------------------------------- -----------------------------------
  BitTorrent                          A peer-to-peer protocol for
                                      distributing data.

  Client                              Software that participates in
                                      BitTorrent.

  Peer                                A participant in a torrent swarm.

  Seeder                              A peer with the complete payload.

  Leecher                             Informal term for a peer that is
                                      still downloading.

  Swarm                               All peers participating in a
                                      particular torrent.

  Tracker                             A service that helps peers discover
                                      one another.

  DHT                                 Distributed Hash Table, a
                                      decentralized peer-discovery
                                      system.

  PEX                                 Peer Exchange, a mechanism for
                                      sharing peer information.

  Piece                               A logical chunk of the torrent
                                      payload described by piece
                                      metadata.

  Block                               A smaller data range requested and
                                      transferred over a peer connection.

  Info hash                           Hash of the bencoded `info`
                                      dictionary; identifies torrent
                                      metadata.

  Bencoding                           Serialization format used for
                                      torrent metadata.

  Magnet link                         URI that identifies a torrent,
                                      usually by its info hash.

  Web seed                            HTTP/HTTPS source that can provide
                                      torrent payload data.

  Merkle tree                         A hash tree used by v2 to support
                                      structured data verification.

  Padding file                        A metadata entry used in some
                                      layouts to align file data to piece
                                      boundaries.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 17. Further Reading

The BitTorrent specifications are the best reference for exact protocol
behavior and field definitions.

-   **BEP 3 --- The BitTorrent Protocol:**
    https://www.bittorrent.org/beps/bep_0003.html
    -   Defines the original BitTorrent protocol, bencoding, v1 torrent
        metadata, tracker announces, and peer-wire protocol.
-   **BEP 5 --- DHT Protocol:**
    https://www.bittorrent.org/beps/bep_0005.html
    -   Describes the decentralized Mainline DHT peer-discovery
        protocol.
-   **BEP 9 --- Extension for Peers to Send Metadata Files:**
    https://www.bittorrent.org/beps/bep_0009.html
    -   Describes metadata exchange used by magnet links.
-   **BEP 10 --- Extension Protocol:**
    https://www.bittorrent.org/beps/bep_0010.html
    -   Defines the extension handshake and extension mechanism.
-   **BEP 12 --- Multitracker Metadata Extension:**
    https://www.bittorrent.org/beps/bep_0012.html
    -   Describes the `announce-list` tracker-tier convention.
-   **BEP 19 --- WebSeed:**
    https://www.bittorrent.org/beps/bep_0019.html
    -   Describes HTTP/FTP-style web seeds.
-   **BEP 52 --- The BitTorrent Protocol Specification (BitTorrent
    v2):** https://www.bittorrent.org/beps/bep_0052.html
    -   Defines v2 metadata, SHA-256 Merkle trees, file trees, and
        hybrid torrents.

------------------------------------------------------------------------

## Final Summary

A BitTorrent download is a cooperative process: a client discovers
peers, connects to them, requests blocks belonging to pieces, verifies
each completed piece, and shares verified data with other participants.

A `.torrent` file is the metadata blueprint for that process. Its most
important component is the `info` dictionary, which describes the
payload's name, file structure, lengths, piece layout, and integrity
metadata. In v1, piece integrity is represented by concatenated SHA-1
hashes. In v2, file data is verified using SHA-256-based Merkle trees.

The torrent's info hash identifies the metadata---not the entire
downloaded file. Trackers and DHT help find peers, while the peers and
optional web seeds provide the actual payload data.