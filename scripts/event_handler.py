#!/usr/bin/env python3
import os
import sys
import urllib.request
import errno
import stat
import base64
import json
from datetime import datetime


# ---------- CONFIGURATION ----------
PIPE_PATH = "/mnt/pipe/spotipipe.metadata"   # FIFO 
OUTPUT_FILE = "/userscripts/shairport-sync-meta.bin"   # file is for debugging
OUTPUT_MODE = "fifo"                           # "fifo" or "file"
VOLUME_MAX = 65536
# -----------------------------------

def log(msg):
    """Simple console logger with timestamps."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

def to_hex(s: str) -> str:
    return ''.join(f"{ord(c):02x}" for c in s[:4])

def make_item_xml(mtype, code, data_bytes):
    """Create an <item>...</item> XML block with base64 data."""
    encoded = base64.b64encode(data_bytes).decode("ascii")
    item = (
        f"<item>"
        f"<type>{to_hex(mtype)}</type>"
        f"<code>{to_hex(code)}</code>"
        f"<length>{len(data_bytes)}</length>"
        f"<data encoding=\"base64\">\n{encoded}</data>"
        f"</item>\n"
    )
    return item.encode("utf-8")

def ensure_output_valid(path, mode):
    import stat
    if not os.path.exists(path):
        if mode == "fifo":
            log(f"❌ FIFO not found: {path}")
            sys.exit(1)
        elif mode == "file":
            log(f"ℹ️ Creating new file at {path}")
            open(path, "wb").close()
            return
    st = os.stat(path)
    if mode == "fifo" and not stat.S_ISFIFO(st.st_mode):
        log(f"❌ {path} exists but is not a FIFO")
        sys.exit(1)


def fetch_spotify_metadata(track_id):
    """Fetch track metadata and artwork URL via Spotify's oEmbed API."""
    url = f"https://open.spotify.com/oembed?url=spotify:track:{track_id}"
    with urllib.request.urlopen(url) as resp:
        data = json.load(resp)
    try:
        title, artist = data["title"].split(" – ", 1)
    except ValueError:
        title, artist = data["title"], "Unknown Artist"
    return {
        "title": title,
        "artist": artist,
        "artwork_url": data.get("thumbnail_url"),
    }

def download_artwork(url):
    """Download artwork binary data (JPEG/PNG)."""
    with urllib.request.urlopen(url) as resp:
        return resp.read()

def handle_event():
    """Main librespot event handler entry point."""
    event = os.environ.get("PLAYER_EVENT")
    track_id = os.environ.get("TRACK_ID")
    volume = os.environ.get("VOLUME")

    if not track_id and not volume:
        log("⚠️  No TRACK_ID or VOLUME provided; nothing to do.")
        return
    if event not in ("start", "track_changed","volume_changed"):
        log(f"ℹ️  Ignoring event: {event}")
        return        

    ensure_output_valid(PIPE_PATH, OUTPUT_MODE)

    # Deal with volume changed
    if volume:
        log(f"🎵 Handling event '{event}' for volume {volume}")
        xmlValue = (float(volume) - VOLUME_MAX) * 30.0 / (VOLUME_MAX - 1)
        volData = f"{xmlValue:.2f},0.00,0.00,0.00"

    # Fetch metadata and artwork
    if track_id:
        log(f"🎵 Handling event '{event}' for track {track_id}")
        try:
            meta = fetch_spotify_metadata(track_id)
            artwork_data = download_artwork(meta.get("artwork_url", ""))
        except Exception as e:
            log(f"❌ ERROR fetching metadata or artwork: {e}")
            return
        # Override the information  
        meta['artist'] = os.environ.get("ALBUM_ARTISTS")
        meta['album'] = os.environ.get("ALBUM")
        log(f"→ Title:   {meta['title']}")
        log(f"→ Artist:  {meta['artist']}")
        log(f"→ Album:   {meta['album']}")
        log(f"→ Artwork: {len(artwork_data)} bytes")

    # Open output
    if OUTPUT_MODE == "fifo":
        try:
            fd = os.open(PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as e:
            if e.errno in (errno.ENXIO, errno.ENOENT):
                log(f"⚠️ No reader connected to FIFO; skipping write.")
                return
            raise
        out = os.fdopen(fd, "wb", buffering=0)
    else:
        out = open(OUTPUT_FILE, "ab")

    try:
        # Write XML-formatted <item> blocks
        if track_id:
            out.write(make_item_xml("core", "asgn", b"Spotify"))
            out.write(make_item_xml("core", "minm", meta["title"].encode("utf-8")))
            out.write(make_item_xml("core", "asar", meta["artist"].encode("utf-8")))
            out.write(make_item_xml("core", "asal", meta["album"].encode("utf-8")))
	# Does not seem too reliable. Better let owntone search for the picture
#            if artwork_data:
#                out.write(make_item_xml("ssnc", "PICT", artwork_data))
        elif volume:
            out.write(make_item_xml("ssnc","pvol",volData.encode("utf-8")))

        out.flush()
        log("✅ Metadata written in XML-style Shairport format.")
    finally:
        out.close()

# ---------- Entry Point ----------
if __name__ == "__main__":
    try:
        handle_event()
    except Exception as e:
        log(f"❌ FATAL ERROR: {e}")
        sys.exit(1)
