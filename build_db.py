"""Downloads every show of the configured tours from the setlist.fm API and builds setlists.db.

Usage: SETLISTFM_API_KEY=... python build_db.py   (or the key in .env, line SETLISTFM_API_KEY=...)
Re-runnable: raw responses are cached in raw/ and only missing pages are downloaded
(--refresh downloads them all again).
"""
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "raw"
DB = HERE / "setlists.db"
API = "https://api.setlist.fm/rest/1.0"

# Current tour = weight 1; previous tour = added and tagged separately (analyze.py applies its weight).
# stop_before: date (YYYY-MM-DD) at which paging backwards stops.
# The current tours have 31 and 47 shows: no need to add the previous ones ("previous" stays empty).
ARTISTS = {
    "The Strokes": {"tours": {"current": ["Reality Awaits"], "previous": []}, "stop_before": "2026-06-01"},
    "Gorillaz": {"tours": {"current": ["The Mountain Tour"], "previous": []}, "stop_before": "2026-03-01"},
}

# The setlist.fm API doesn't flag festivals: list checked by hand on the web (2026-10-10).
FESTIVALS = {
    ("The Strokes", "2026-06-12"): "Bonnaroo",
    ("The Strokes", "2026-07-19"): "Minnesota Yacht Club Festival",
    ("The Strokes", "2026-08-08"): "Outside Lands",
    ("The Strokes", "2026-08-14"): "Summer Sonic Tokyo",
    ("The Strokes", "2026-08-15"): "Summer Sonic Osaka",
    ("The Strokes", "2026-08-22"): "Just Like Heaven",
    ("The Strokes", "2026-09-18"): "Shaky Knees",
    ("The Strokes", "2026-09-20"): "Sea.Hear.Now",
    ("Gorillaz", "2026-06-05"): "We Love Green",
    ("Gorillaz", "2026-06-06"): "Primavera Sound Barcelona",
    ("Gorillaz", "2026-06-10"): "Rock for People",
    ("Gorillaz", "2026-06-12"): "Primavera Sound Porto",
    ("Gorillaz", "2026-06-14"): "Best Kept Secret",
    ("Gorillaz", "2026-06-23"): "INmusic",
    ("Gorillaz", "2026-06-25"): "Release Athens",
    ("Gorillaz", "2026-06-27"): "La Prima Estate",
    ("Gorillaz", "2026-07-02"): "Roskilde",
    ("Gorillaz", "2026-07-04"): "Rock Werchter",
    ("Gorillaz", "2026-07-09"): "Pohoda",
    ("Gorillaz", "2026-07-11"): "Musilac",
    ("Gorillaz", "2026-07-18"): "PhillGood",
    ("Gorillaz", "2026-07-23"): "Paléo",
    ("Gorillaz", "2026-08-13"): "BitterSweet",
    ("Gorillaz", "2026-08-15"): "Way Out West",
    ("Gorillaz", "2026-08-22"): "Park Live Almaty",
    ("Gorillaz", "2026-08-29"): "Electric Picnic",
    ("Gorillaz", "2026-09-20"): "Shaky Knees",
}
TODAY = time.strftime("%Y-%m-%d")


def api_key():
    key = os.environ.get("SETLISTFM_API_KEY")
    env = HERE / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("SETLISTFM_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("Missing SETLISTFM_API_KEY (environment or .env)")
    return key


def get(path, params, cache, refresh):
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"x-api-key": api_key(), "Accept": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                data = {}
                break
            if e.code == 429 and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            raise
    time.sleep(0.6)  # the API allows ~2 req/s
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def find_mbid(artist, refresh):
    data = get("/search/artists", {"artistName": artist, "sort": "relevance"},
               RAW / f"artist-{artist}.json", refresh)
    for a in data.get("artist", []):
        if a["name"].lower() == artist.lower():
            return a["mbid"]
    sys.exit(f"Artist {artist!r} not found on setlist.fm")


def iso(d):  # dd-MM-yyyy -> yyyy-MM-dd
    dd, mm, yy = d.split("-")
    return f"{yy}-{mm}-{dd}"


def fetch_setlists(artist, cfg, refresh):
    mbid = find_mbid(artist, refresh)
    page, out = 1, []
    while True:
        data = get(f"/artist/{mbid}/setlists", {"p": page}, RAW / f"{artist}-p{page:03d}.json", refresh)
        items = data.get("setlist", [])
        out += items
        if not items or iso(items[-1]["eventDate"]) < cfg["stop_before"]:
            return out
        if page * data["itemsPerPage"] >= data["total"]:
            return out
        page += 1


def section_name(s, encore_count):
    if not s.get("encore"):
        return "main"
    return "encore" if encore_count == 1 else f"encore_{encore_count}"


SCHEMA = """
DROP TABLE IF EXISTS performances; DROP TABLE IF EXISTS shows; DROP TABLE IF EXISTS missing;
CREATE TABLE shows(id TEXT PRIMARY KEY, artist TEXT, date TEXT, city TEXT, country TEXT, venue TEXT,
  tour TEXT, tour_role TEXT, is_festival INTEGER, set_minutes INTEGER, source_url TEXT);
CREATE TABLE performances(show_id TEXT REFERENCES shows(id), position INTEGER, song TEXT, section TEXT,
  is_cover INTEGER, is_tape INTEGER, notes TEXT, guest TEXT, PRIMARY KEY(show_id, position));
CREATE TABLE missing(id TEXT, artist TEXT, date TEXT, venue TEXT, tour TEXT, source_url TEXT, reason TEXT);
"""


def main():
    refresh = "--refresh" in sys.argv
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    for artist, cfg in ARTISTS.items():
        role_of = {t: role for role, tours in cfg["tours"].items() for t in tours}
        for s in fetch_setlists(artist, cfg, refresh):
            tour = s.get("tour", {}).get("name")
            if tour not in role_of:
                continue
            v = s["venue"]
            row = (s["id"], artist, iso(s["eventDate"]), v["city"]["name"], v["city"]["country"]["name"],
                   v["name"], tour)
            songs, encores = [], 0
            for st in s.get("sets", {}).get("set", []):
                if st.get("encore"):
                    encores += 1
                for song in st.get("song", []):
                    if not song.get("name"):
                        continue
                    notes = "; ".join(filter(None, [song.get("info"),
                                                    song.get("with") and f"with {song['with']['name']}"]))
                    songs.append((song["name"], section_name(st, encores), int("cover" in song),
                                  int(bool(song.get("tape"))), notes or None, (song.get("with") or {}).get("name")))
            if not songs:
                reason = "show hasn't happened yet" if row[2] >= TODAY else "empty setlist on setlist.fm"
                con.execute("INSERT INTO missing VALUES (?,?,?,?,?,?,?)",
                            (s["id"], artist, row[2], v["name"], tour, s["url"], reason))
                continue
            con.execute("INSERT INTO shows VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (*row, role_of[tour], int((artist, row[2]) in FESTIVALS), None, s["url"]))
            con.executemany("INSERT INTO performances VALUES (?,?,?,?,?,?,?,?)",
                            [(s["id"], i, *song) for i, song in enumerate(songs, 1)])
    con.commit()
    for artist, n, m in con.execute(
            "SELECT artist, COUNT(*), (SELECT COUNT(*) FROM missing x WHERE x.artist = s.artist) "
            "FROM shows s GROUP BY artist"):
        print(f"{artist}: {n} shows, {m} missing")


if __name__ == "__main__":
    main()
