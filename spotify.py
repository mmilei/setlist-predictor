"""Spotify for the playlists in playlists.csv (stdlib, Authorization Code + PKCE: the Client ID is enough).

  python spotify.py login    # opens the browser once; saves the token to .spotify_token.json
  python spotify.py links    # looks up every song (read-only) and writes spotify_links.json; then: python analyze.py
  python spotify.py create   # creates (or replaces) the two private playlists in your account

Needs SPOTIFY_CLIENT_ID in the environment or in .env, and an app with Redirect URI http://127.0.0.1:8888/callback.
"""
import base64
import csv
import hashlib
import http.server
import json
import os
import re
import secrets
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

HERE = Path(__file__).parent
TOKEN = HERE / ".spotify_token.json"
LINKS = HERE / "spotify_links.json"
ALBUMS_CACHE = HERE / "raw" / "albums.json"
# setlist.fm and Spotify spell some titles differently: normalized Spotify key -> setlist.fm key.
ALIASES = {"nyc cops": "new york city cops", "new genious brother": "new genius brother"}
REDIRECT = "http://127.0.0.1:8888/callback"
SCOPES = "playlist-read-private playlist-modify-private playlist-modify-public"
# Covers: look up the original artist's version.
COVER_ARTIST = {("The Strokes", "This Is Not"): "Blonde Redhead"}
PLAYLIST_NAME = "Primavera BA 2026 · {artist} (probable setlist)"


def client_id():
    cid = os.environ.get("SPOTIFY_CLIENT_ID")
    env = HERE / ".env"
    if not cid and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("SPOTIFY_CLIENT_ID="):
                cid = line.split("=", 1)[1].strip()
    if not cid:
        sys.exit("Missing SPOTIFY_CLIENT_ID (environment or .env)")
    return cid


def token_request(fields):
    body = urllib.parse.urlencode({"client_id": client_id(), **fields}).encode()
    with urllib.request.urlopen("https://accounts.spotify.com/api/token", body, timeout=30) as r:
        tok = json.load(r)
    old = json.loads(TOKEN.read_text()) if TOKEN.exists() else {}
    tok["refresh_token"] = tok.get("refresh_token") or old.get("refresh_token")
    tok["expires_at"] = time.time() + tok["expires_in"] - 60
    TOKEN.write_text(json.dumps(tok))
    return tok


def login():
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(dict(
        client_id=client_id(), response_type="code", redirect_uri=REDIRECT, scope=SCOPES,
        code_challenge_method="S256", code_challenge=challenge, state=state))
    got = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            got.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Done, you can close this tab.".encode())

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 8888), Handler)
    print("Opening the browser to log in to Spotify...\n" + url)
    webbrowser.open(url)
    while "code" not in got and "error" not in got:
        server.handle_request()
    if got.get("state", [None])[0] != state or "error" in got:
        sys.exit(f"Login failed: {got}")
    token_request(dict(grant_type="authorization_code", code=got["code"][0], redirect_uri=REDIRECT,
                       code_verifier=verifier))
    print("Token saved to .spotify_token.json")


def access_token():
    if not TOKEN.exists():
        sys.exit("First run: python spotify.py login")
    tok = json.loads(TOKEN.read_text())
    if time.time() > tok["expires_at"]:
        tok = token_request(dict(grant_type="refresh_token", refresh_token=tok["refresh_token"]))
    return tok["access_token"]


def api(method, path, params=None, body=None):
    url = f"https://api.spotify.com/v1{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {access_token()}",
                                          "Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                time.sleep(int(e.headers.get("Retry-After", 2)))
                continue
            sys.exit(f"{method} {path}: {e.code} {e.read().decode(errors='replace')}")


def norm(s):
    s = unicodedata.normalize("NFKD", s.replace("’", "'")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def key(title):
    """Key to match setlist.fm and Spotify titles (no "- Remaster", "(feat. ...)", accents or punctuation)."""
    k = norm(re.split(r" - | \(feat\.", title)[0])
    return ALIASES.get(k, k)


def album_tracks(album_ids):
    """Tracklists {album_id: [{name, ms}]}, cached in raw/albums.json."""
    cache = json.loads(ALBUMS_CACHE.read_text(encoding="utf-8")) if ALBUMS_CACHE.exists() else {}
    missing = [a for a in album_ids if a not in cache]
    for aid in missing:
        cache[aid] = [dict(name=t["name"], ms=t["duration_ms"]) for t in api("GET", f"/albums/{aid}")["tracks"]["items"]]
    if missing:
        ALBUMS_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return cache


BAD = re.compile(r"\b(live|remix|demo|instrumental|acoustic|edit|version|session|mix)\b")


def best(items, song, artist):
    """First the artist's exact title that isn't live/remix; then anything by the artist."""
    want = norm(song)
    mine = [t for t in items if norm(artist) in {norm(a["name"]) for a in t["artists"]}]
    for t in mine:
        title = norm(re.split(r" - | \(feat", t["name"])[0])
        if title == want and not BAD.search(norm(t["name"]).replace(want, "")):
            return t, "exact"
    return (mine[0], "approximate") if mine else (None, None)


def links():
    rows = list(csv.DictReader(open(HERE / "playlists.csv", encoding="utf-8")))
    out, report = {}, []
    for r in rows:
        song, artist = r["song"], r["artist"]
        artist = COVER_ARTIST.get((artist, song), artist)
        q = f'track:"{song.replace(chr(8217), chr(39))}" artist:"{artist}"'
        items = api("GET", "/search", dict(q=q, type="track", limit=10))["tracks"]["items"]
        t, how = best(items, song, artist)
        if not t:  # covers and titles Spotify spells differently: free search, no artist filter
            items = api("GET", "/search", dict(q=song, type="track", limit=10))["tracks"]["items"]
            t, how = (items[0], "without the artist (cover or different title)") if items else (None, "not found")
        if t:
            out[f"{r['artist']}|{song}"] = t["external_urls"]["spotify"]
            out[f"uri|{r['artist']}|{song}"] = t["uri"]
            out[f"ms|{r['artist']}|{song}"] = t["duration_ms"]
        if how != "exact":
            report.append(f"- {artist} · {song}: {how}" +
                          (f" → {', '.join(a['name'] for a in t['artists'])} - {t['name']} ({t['album']['name']})"
                           if t else ""))
    LINKS.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{sum(1 for k in out if not k.startswith(('uri|', 'ms|')))}/{len(rows)} songs with a link")
    print("\n".join(report) or "all exact")


def create():
    rows = list(csv.DictReader(open(HERE / "playlists.csv", encoding="utf-8")))
    uris = json.loads(LINKS.read_text(encoding="utf-8"))
    mine = {p["name"]: p["id"] for p in api("GET", "/me/playlists", dict(limit=50))["items"]}
    urls = {}
    for artist in dict.fromkeys(r["artist"] for r in rows):
        name = PLAYLIST_NAME.format(artist=artist)
        tracks = [uris[f"uri|{artist}|{r['song']}"] for r in rows
                  if r["artist"] == artist and f"uri|{artist}|{r['song']}" in uris]
        pid = mine.get(name)
        if pid:
            api("PUT", f"/playlists/{pid}/items", body={"uris": tracks})
        else:
            pid = api("POST", "/me/playlists", body={
                "name": name, "public": False,
                "description": "Probable setlist built from setlist.fm, in show order."})["id"]
            api("POST", f"/playlists/{pid}/items", body={"uris": tracks})
        urls[artist] = f"https://open.spotify.com/playlist/{pid}"
        print(f"{name}: {len(tracks)} songs → {urls[artist]}")
    (HERE / "spotify_playlists.json").write_text(json.dumps(urls, indent=1), encoding="utf-8")


if __name__ == "__main__":
    {"login": login, "links": links, "create": create}[sys.argv[1] if len(sys.argv) > 1 else "links"]()
