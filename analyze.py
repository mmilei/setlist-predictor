"""Reads setlists.db and writes RESULTS.md (METHOD.md + patterns, probable setlists, playlists, appendix) and
playlists.csv.

Tapes (recorded intros/outros) don't count as songs. Each band's model lives in BANDS.
"""
import csv
import spotify
import json
import re
import sqlite3
import statistics as st
import time
from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).parent
PREV_WEIGHT = 0.5  # previous tour (unused today: the two current tours have enough shows)
MIN_P = 0.15  # the playlist takes every song with at least this probability, with no length cap...
MIN_REP = 0.5  # ...and every song in the current repertoire, even if festivals usually cut it
# Filler (added 2026-10-11): songs from the albums in BANDS[...]["extra_albums"] that rotate in the last two legs.
# TARGET_MIN is a duration ceiling, not a goal.
TARGET_MIN = 150
FEST_CUT = 0.5  # festival factor below which a song "usually gets cut" at festivals
# Guests (added 2026-10-11, Gorillaz only): a song that almost always plays with an occasional guest (the leg's opening
# act, an artist on the same festival bill) is played because that guest was there; they won't be in Buenos Aires.
# Band guest = one who joins in at least BAND_GUEST_SHARE of the shows, plus BANDS[...]["local_guests"].
BAND_GUEST_SHARE = 0.75
DEP_SHARE = 0.75  # a song "depends on a guest" if at least this share of its plays are with an occasional guest
GUEST_WEIGHT = 0.25  # how much a play with an occasional guest weighs for those songs

# Per-band model (data as of 2026-10-10). Legs come from the tour's real dates.
# Show weight for the repertoire: "last" = the latest stretch, which rules; "leg" = the rest of the current leg;
# "prev" = the previous leg; "older" = everything else.
BANDS = {
    "Gorillaz": dict(
        legs=[("UK and Ireland, arenas", "2026-03-20", "2026-04-02"),
              ("Europe, summer festivals", "2026-06-05", "2026-08-29"),
              ("North America, arenas", "2026-09-17", "2026-10-08")],
        # After Shaky Knees (9/20) the set locked in: since Charlotte (9/23) there are 10 shows with the same ~23-song
        # core and 2 to 5 rotating slots. Cloud of Unknowing, Rock the House, Garage Palace and The Sad God came in.
        last_from="2026-09-23",
        weights=dict(last=4, leg=1, prev=0.5, older=0.1),
        extra_albums=["Demon Days", "Plastic Beach"],  # filler: not the debut album
        # Trueno sings on The Manifesto and joined in 8 of the 9 tour shows where it was played; he's from Buenos Aires.
        local_guests=["Trueno"],
        must={"The Manifesto": "with Trueno, a local"},  # goes into the playlist despite its low probability
        # First 4 albums (standard editions on Spotify, checked by hand on 2026-10-10).
        albums=[("Gorillaz", 2001, "4tUxQkrduOE8sfgwJ5BI2F"), ("Demon Days", 2005, "0bUTHlWbkSQysoM3VsWldT"),
                ("Plastic Beach", 2010, "2dIGnmEIy1WZIcZCFSj6i8"), ("The Fall", 2010, "5jJGGsAztgUEXUHHZ2zrah")]),
    "The Strokes": dict(
        legs=[("US, summer", "2026-06-12", "2026-07-23"),
              ("Japan and West Coast", "2026-08-08", "2026-08-28"),
              ("US, Southeast", "2026-09-12", "2026-09-20"),
              ("Queens and Europe", "2026-10-02", "2026-10-28")],
        # Since Queens (10/2) the repertoire changed: in came Under Control, This Is Not, Heart in a Cage, Meet Me in the
        # Bathroom and New York City Cops; out went What Ever Happened?, Ize of the World, Is This It and 12:51. As of
        # 10/10 that's only 3 shows, so the previous leg weighs more than for Gorillaz.
        last_from="2026-10-02",
        weights=dict(last=4, leg=1, prev=0.75, older=0.1),
        extra_albums=["Is This It", "Room on Fire", "First Impressions of Earth"],
        albums=[("Is This It", 2001, "2yNaksHgeMQM9Quse463b5"), ("Room on Fire", 2003, "3HFbH1loOUbqCyPsLuHLLh"),
                ("First Impressions of Earth", 2006, "1HQ61my1h3VWp2EBWKlp0n"),
                ("Angles", 2011, "6Jx4cGhWHewTcfKDJKguBQ")]),
}
LAST_MAX = 10  # within the latest stretch, only the last 10 shows get the "last" weight
FEST_LEG_WEIGHTS = [1, 0.5, 0.25]  # festivals of the most recent leg with festivals, the one before, the rest
FEST_PRIOR = 1  # how many "festivals" of evidence the band average is worth when estimating the festival factor


def load(con, artist):
    shows = {}
    for sid, date, city, venue, tour, role, fest, url in con.execute(
            "SELECT id, date, city, venue, tour, tour_role, is_festival, source_url FROM shows "
            "WHERE artist = ? ORDER BY date", (artist,)):
        shows[sid] = dict(date=date, city=city, venue=venue, tour=tour, festival=bool(fest), url=url,
                          w=1.0 if role == "current" else PREV_WEIGHT, songs=[], guests={})
    for sid, song, section, guest in con.execute(
            "SELECT p.show_id, p.song, p.section, p.guest FROM performances p JOIN shows s ON s.id = p.show_id "
            "WHERE s.artist = ? AND p.is_tape = 0 ORDER BY p.show_id, p.position", (artist,)):
        shows[sid]["songs"].append((song, section))
        if guest:
            shows[sid]["guests"][song] = guest
    shows = {k: v for k, v in shows.items() if v["songs"]}
    cfg = BANDS[artist]
    legs, w = cfg["legs"], cfg["weights"]
    recent = [k for k, s in shows.items() if s["date"] >= cfg["last_from"]][-LAST_MAX:]  # shows are already by date
    for k, s in shows.items():
        s["leg"] = next((i for i, (_, a, b) in enumerate(legs) if a <= s["date"] <= b), None)
        if s["leg"] is None:
            raise SystemExit(f"{artist} {s['date']} {s['city']}: outside the legs in BANDS; add the new leg")
        s["last"] = k in recent
        role = ("last" if s["last"] else "leg" if s["leg"] == len(legs) - 1
                else "prev" if s["leg"] == len(legs) - 2 else "older")
        s["pw"] = s["w"] * w[role]
    return shows


def festival_ratio(shows, near=4):
    """Per song: how well it survives in a festival set. Each festival is compared with the `near` closest-in-date
    headline shows of the same leg (that moment's repertoire): ratio = festivals where it played / those expected from
    its frequency in those headline shows, smoothed toward the band average and capped at 1. Weighted by how recent the
    festival cuts are: festivals from the most recent leg that had festivals weigh more."""
    day = lambda s: date.fromisoformat(s["date"]).toordinal()
    own = [s for s in shows.values() if not s["festival"]]
    kept, expected = defaultdict(float), defaultdict(float)
    fest_legs = sorted({s["leg"] for s in shows.values() if s["festival"]}, reverse=True)
    for f in (s for s in shows.values() if s["festival"]):
        fw = FEST_LEG_WEIGHTS[min(fest_legs.index(f["leg"]), len(FEST_LEG_WEIGHTS) - 1)]
        pool = [s for s in own if s["leg"] == f["leg"]] or own  # the repertoire changes between legs
        ref = sorted(pool, key=lambda s: abs(day(s) - day(f)))[:near]
        freq = Counter(x for s in ref for x in {y for y, _ in s["songs"]})
        played = {y for y, _ in f["songs"]}
        for song, n in freq.items():
            expected[song] += fw * n / len(ref)
            kept[song] += fw * (song in played)
    mean = sum(kept.values()) / sum(expected.values())
    return {song: min(1.0, (kept[song] + FEST_PRIOR * mean) / (expected[song] + FEST_PRIOR)) for song in expected}, mean


def guest_songs(shows, local):
    """Songs that depend on an occasional guest ({song: most frequent guest}) and the band's own guests.
    See BAND_GUEST_SHARE and DEP_SHARE."""
    on_stage = Counter(g for s in shows.values() for g in set(s["guests"].values()))
    band = {g for g, n in on_stage.items() if n >= BAND_GUEST_SHARE * len(shows)} | set(local)
    plays, guested = Counter(), defaultdict(Counter)
    for s in shows.values():
        for song, _ in s["songs"]:
            plays[song] += 1
            if s["guests"].get(song) not in band | {None}:
                guested[song][s["guests"][song]] += 1
    return {k: c.most_common(1)[0][0] for k, c in guested.items() if c.total() >= DEP_SHARE * plays[k]}, band


def predict(shows, artist):
    """Probability of hearing each song in Buenos Aires: current repertoire (weighted by leg) x festival factor.
    For songs that depend on an occasional guest, their plays with that guest weigh GUEST_WEIGHT."""
    stats = song_stats(shows, key="pw")
    cfg = BANDS[artist]
    dep, band = guest_songs(shows, cfg["local_guests"]) if "local_guests" in cfg else ({}, set())
    total = sum(s["pw"] for s in shows.values())
    for song in dep:
        stats[song]["p"] = sum(s["pw"] * (GUEST_WEIGHT if s["guests"].get(song) not in band | {None} else 1)
                               for s in shows.values() if any(x == song for x, _ in s["songs"])) / total
    ratio, mean = festival_ratio(shows)
    for song, v in stats.items():
        v["p_rep"], v["fest_ratio"] = v["p"], ratio.get(song, mean)
        v["p"] = v["p_rep"] * v["fest_ratio"]
    return stats, dep


def festival_length(shows):
    """Festival set length: median of the festivals in the last two legs that had festivals."""
    legs = sorted({s["leg"] for s in shows.values() if s["festival"]})[-2:]
    return round(st.median(len(s["songs"]) for s in shows.values() if s["festival"] and s["leg"] in legs))


def song_stats(shows, key="w"):
    total_w = sum(s[key] for s in shows.values())
    acc = defaultdict(lambda: dict(w=0.0, n=0, rel=[], opens=0, closes_main=0, opens_encore=0,
                                   closes_show=0, in_encore=0))
    for s in shows.values():
        songs = s["songs"]
        main = [x for x, sec in songs if sec == "main"]
        enc = [x for x, sec in songs if sec != "main"]
        for i, (song, sec) in enumerate(songs):
            a = acc[song]
            a["w"] += s[key]
            a["n"] += 1
            a["rel"].append(((i + 1) / len(songs), s[key]))
            a["in_encore"] += s[key] * (sec != "main")
        acc[songs[0][0]]["opens"] += 1
        acc[songs[-1][0]]["closes_show"] += 1
        if main and enc:
            acc[main[-1]]["closes_main"] += 1
            acc[enc[0]]["opens_encore"] += 1
    out = {}
    for song, a in acc.items():
        rel = sum(r * w for r, w in a["rel"]) / a["w"]
        sd = (sum(w * (r - rel) ** 2 for r, w in a["rel"]) / a["w"]) ** 0.5
        out[song] = dict(p=a["w"] / total_w, n=a["n"], rel=rel, sd=sd, opens=a["opens"], closes_main=a["closes_main"],
                         opens_encore=a["opens_encore"], closes_show=a["closes_show"],
                         p_encore=a["in_encore"] / a["w"])
    return out


def section_label(s):
    if s["p_encore"] > 0.5:
        return "encore"
    if s["rel"] < 0.15:
        return "opening"
    if s["rel"] > 0.8:
        return "closing"
    return "middle"


def transitions(shows, stats, min_n=4, min_share=0.75):
    pairs = Counter()
    for s in shows.values():
        names = [x for x, _ in s["songs"]]
        pairs.update(zip(names, names[1:]))
    return sorted(((a, b, n, n / stats[a]["n"]) for (a, b), n in pairs.items()
                   if n >= min_n and n / stats[a]["n"] >= min_share), key=lambda t: -t[2])


def rotations(shows, stats):
    """Pairs of songs with a similar position that almost never play in the same show."""
    together = Counter()
    for s in shows.values():
        together.update(combinations(sorted({x for x, _ in s["songs"]}), 2))
    cand = [k for k, v in stats.items() if 0.15 <= v["p"] <= 0.85 and v["n"] >= 3]
    out = []
    for a, b in combinations(sorted(cand), 2):
        if abs(stats[a]["rel"] - stats[b]["rel"]) > 0.12:
            continue
        both = together[(a, b)]
        if both <= 0.1 * min(stats[a]["n"], stats[b]["n"]):
            out.append((a, b, both))
    return out


def tour_changes(shows, min_shows=6):
    ordered = list(shows.values())
    if len(ordered) < min_shows:
        return []
    cut = len(ordered) * 2 // 3
    early, late = ordered[:cut], ordered[cut:]
    freq = lambda group: Counter(x for s in group for x in {y for y, _ in s["songs"]})
    fe, fl = freq(early), freq(late)
    out = []
    for song in set(fe) | set(fl):
        pe, pl = fe[song] / len(early), fl[song] / len(late)
        if abs(pl - pe) >= 0.4:
            out.append((song, pe, pl))
    return sorted(out, key=lambda t: t[2] - t[1]), early[-1]["date"]


def recent_transitions(shows, min_share=0.75, min_n=3):
    """A → B pairs repeated in the latest stretch (BANDS[...]["last_from"]): what is played back to back today."""
    after, total, n = defaultdict(float), defaultdict(float), Counter()
    for s in (s for s in shows.values() if s["last"]):
        names = [x for x, _ in s["songs"]]
        for a in names:
            total[a] += s["pw"]
        for a, b in zip(names, names[1:]):
            after[(a, b)] += s["pw"]
            n[(a, b)] += 1
    best = {}  # if two songs usually precede the same B, the heavier one wins
    for (a, b), w in after.items():
        if n[(a, b)] >= min_n and w / total[a] >= min_share and w > best.get(b, ("", 0))[1]:
            best[b] = (a, w)
    return {a: b for b, (a, _) in best.items()}


def order(stats, shows):
    """Copeland order: A goes before B if, in the shows where both play, A comes first with more weight.
    Then the recent fixed transitions are glued in (B right after A)."""
    keys = list(stats)
    before = defaultdict(float)
    for s in shows.values():
        pos = {x: i for i, (x, _) in enumerate(s["songs"])}
        for a, b in combinations([k for k in keys if k in pos], 2):
            before[(a, b) if pos[a] < pos[b] else (b, a)] += s["pw"]
    # Normalized Copeland: share of comparisons won, so a song that shares few shows doesn't sink to the bottom.
    met = {a: [b for b in keys if b != a and before[(a, b)] + before[(b, a)] > 0] for a in keys}
    wins = {a: sum(before[(a, b)] > before[(b, a)] for b in met[a]) / max(len(met[a]), 1) for a in keys}
    nxt = {a: b for a, b in recent_transitions(shows).items() if a in stats and b in stats}
    prev = {b: a for a, b in nxt.items()}
    out = []
    for k in sorted(keys, key=lambda k: (-wins[k], stats[k]["rel"])):
        while k in prev and prev[k] not in out:  # the chain A → B → C goes in whole where its first song lands
            k = prev[k]
        while k and k not in out:
            out.append(k)
            k = nxt.get(k)
    closer = max(out, key=lambda k: stats[k]["closes_show"])  # the block that closes the show always goes last
    block = [closer]
    while block[0] in prev and prev[block[0]] in out:
        block.insert(0, prev[block[0]])
    out = [k for k in out if k not in block] + block
    return [(k, stats[k]) for k in out]


def fill_to_target(artist, playlist, stats, shows, links):
    """Adds songs from the band's filler albums that played in the last two legs (the ones rotating in the free slots
    today), most probable first, without going over TARGET_MIN. Each one goes into its typical relative position,
    before the closing block and without breaking a fixed transition. Returns (playlist, minutes)."""
    ids = [aid for name, _, aid in BANDS[artist]["albums"] if name in BANDS[artist]["extra_albums"]]
    albums = spotify.album_tracks(ids)
    tracks = {spotify.key(t["name"]): t for aid in ids for t in albums[aid]}
    ms = lambda name: links.get(f"ms|{artist}|{name}") or tracks.get(spotify.key(name), {}).get("ms") or 240_000
    last_leg = max(s["leg"] for s in shows.values())
    recent = {x for s in shows.values() if s["leg"] >= last_leg - 1 for x, _ in s["songs"]}
    have = {k for k, _ in playlist}
    cands = sorted((k for k in recent if k not in have and spotify.key(k) in tracks), key=lambda k: -stats[k]["p"])
    seq, vals = [k for k, _ in playlist], dict(playlist)
    nxt = {a: b for a, b in recent_transitions(shows).items() if a in vals and b in vals}
    prev = {b: a for a, b in nxt.items()}
    close = len(seq) - 1  # the closing block (the chain ending in the last song) is left alone
    while close > 0 and prev.get(seq[close]) == seq[close - 1]:
        close -= 1
    total = sum(ms(k) for k in seq)
    for k in cands:
        if total + ms(k) > TARGET_MIN * 60_000:
            continue
        v = dict(stats[k], extra=True)
        i = next((j for j, x in enumerate(seq[:close]) if vals[x]["rel"] > v["rel"]), close)
        while 0 < i < close and nxt.get(seq[i - 1]) == seq[i]:  # don't split a fixed block: go after it
            i += 1
        seq.insert(i, k)
        vals[k] = v
        close += 1
        total += ms(k)
    return [(k, vals[k]) for k in seq], total / 60_000


def probable(stats, length, shows):
    top = dict(sorted(stats.items(), key=lambda kv: -kv[1]["p"])[:length])
    return order(top, shows)


def pct(x):
    return f"{x * 100:.0f}%"


def table(rows, head):
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    return lines + ["| " + " | ".join(map(str, r)) + " |" for r in rows]


def report(artist, shows, links):
    fest = {k: v for k, v in shows.items() if v["festival"]}
    own = {k: v for k, v in shows.items() if not v["festival"]}
    all_stats = song_stats(shows)
    base_stats, dep = predict(shows, artist)
    must = BANDS[artist].get("must", {})
    length = festival_length(shows)
    med = lambda g: round(st.median(len(s["songs"]) for s in g.values())) if g else "n/a"
    md = [f"## {artist}", "",
          f"{len(shows)} shows with a setlist ({len(fest)} festivals, {len(own)} headline shows), "
          f"{min(s['date'] for s in shows.values())} to {max(s['date'] for s in shows.values())}. "
          f"Median length: {med(fest)} songs at festivals, {med(own)} at headline shows.", ""]

    md += ["### Patterns", ""]
    opener = max(all_stats.items(), key=lambda kv: kv[1]["opens"])
    md.append(f"- **Opener:** {opener[0]} opens {opener[1]['opens']} of {len(shows)} shows.")
    closer = max(all_stats.items(), key=lambda kv: kv[1]["closes_show"])
    md.append(f"- **Closer:** {closer[0]} closes {closer[1]['closes_show']} of {len(shows)} shows.")
    enc = sorted(((k, v) for k, v in all_stats.items() if v["p_encore"] > 0.5 and v["p"] >= 0.5),
                 key=lambda kv: kv[1]["rel"])
    md.append("- **Usual encore block:** " + (", ".join(f"{k} ({pct(v['p'])})" for k, v in enc) or "none"))
    tr = transitions(shows, all_stats)
    md.append("- **Fixed transitions (A → B):** " + ("; ".join(
        f"{a} → {b} ({n} times, {pct(share)} of the times {a} plays)" for a, b, n, share in tr) or "none"))
    rot = rotations(shows, all_stats)
    md.append("- **Rotate in the same slot:** " + ("; ".join(
        f"{a} / {b} (together {n} times)" for a, b, n in rot) or "none"))
    md.append("- **Fixed transitions in the latest stretch** (the playlists keep them): " + "; ".join(
        f"{a} → {b}" for a, b in recent_transitions(shows).items()))
    ch = tour_changes(shows)
    if ch:
        changes, cut_date = ch
        md.append(f"- **Tour changes** (first 2/3 up to {cut_date} vs last third): " + ("; ".join(
            f"{s} {pct(a)} → {pct(b)}" for s, a, b in changes) or "no strong changes"))
    if dep:
        md.append(f"- **Depend on an occasional guest** (those plays weigh {pct(GUEST_WEIGHT)}): " + "; ".join(
            f"{k} ({g})" for k, g in sorted(dep.items(), key=lambda kv: -all_stats[kv[0]]["n"])))
    md.append("")

    plan = probable(base_stats, length, shows)
    md += [f"### Most probable setlist ({length} songs)", ""]
    md += table([(i, k, pct(v["p"]), section_label(v)) for i, (k, v) in enumerate(plan, 1)],
                ["#", "Song", "Probability", "Section"])
    md.append("")

    likely = {k: v for k, v in base_stats.items() if v["p"] >= MIN_P or v["p_rep"] >= MIN_REP} | dict(plan)
    likely |= {k: base_stats[k] for k in must}
    playlist, minutes = fill_to_target(artist, probable(likely, len(likely), shows), base_stats, shows, links)
    prob = lambda k, v: pct(v["p"]) + (" (filler)" if v.get("extra") else f" ({must[k]})" if k in must else "")
    rows = [(i, k, prob(k, v), section_label(v), links.get(f"{artist}|{k}", ""))
            for i, (k, v) in enumerate(playlist, 1)]
    md += [f"### Playlist: {len(rows)} songs, {minutes:.0f} min", "",
           f"Every song with at least {pct(MIN_P)} probability or in {pct(MIN_REP)} of the current repertoire, plus filler "
           f"from {', '.join(BANDS[artist]['extra_albums'])} rotating in the last two legs (up to {TARGET_MIN} min).", ""]
    md += table(rows, ["Order", "Song", "Probability", "Section", "Spotify"])
    md.append("")

    appendix = []
    for name, group in (("festivals", fest), ("headline shows", own)):
        if not group:
            continue
        appendix += [f"### {artist}: {name} ({len(group)} shows)", ""]
        appendix += table([(song, pct(v["p"]), f"{v['rel']:.2f} ± {v['sd']:.2f}", v["opens"], v["closes_main"],
                            v["opens_encore"], v["closes_show"])
                           for song, v in sorted(song_stats(group).items(), key=lambda kv: -kv[1]["p"])],
                          ["Song", "Played", "Rel. position", "Opens", "Closes main", "Opens encore", "Closes show"])
        appendix.append("")
    return md, appendix, [(artist, *r) for r in rows]


def main():
    con = sqlite3.connect(HERE / "setlists.db")
    links_file = HERE / "spotify_links.json"
    links = json.loads(links_file.read_text(encoding="utf-8")) if links_file.exists() else {}
    md = (HERE / "METHOD.md").read_text(encoding="utf-8").rstrip().splitlines() + [""]
    md += ["## Shows per band", ""]
    md += table(con.execute("SELECT artist, tour, tour_role, SUM(is_festival), COUNT(*) - SUM(is_festival), "
                            "MIN(date), MAX(date) FROM shows GROUP BY artist, tour").fetchall(),
                ["Band", "Tour", "Role", "Festivals", "Headline", "From", "To"])
    missing = con.execute("SELECT artist, date, venue, reason, source_url FROM missing").fetchall()
    md += ["", "**Missing:** " + ("; ".join(f"{a} {d} {v} ({r}, {u})" for a, d, v, r, u in missing)
                                  or "none"), ""]
    appendix, rows = ["## Appendix: per-song statistics", "",
                      "Played = % of the group's shows. Rel. position = position / show length (mean ± std. dev.). "
                      "Opens / closes = number of shows.", ""], []
    for (artist,) in con.execute("SELECT DISTINCT artist FROM shows ORDER BY artist"):
        part, app, r = report(artist, load(con, artist), links)
        md += part
        appendix += app
        rows += r
    (HERE / "RESULTS.md").write_text("\n".join(md + appendix), encoding="utf-8")
    with open(HERE / "playlists.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["artist", "order", "song", "probability", "section", "spotify_url"])
        w.writerows(rows)
    print("RESULTS.md and playlists.csv written")


if __name__ == "__main__":
    main()
