"""Writes REPORT.md and report.html: what plays for sure, what has high chances, what is possible and what from the
first 4 albums doesn't get played. Probabilities: the same as analyze.py (weighted by recency and festival).
Tracklists come from Spotify (spotify.album_tracks, cached in raw/albums.json).

The report's text is in Spanish on purpose: it was made for a festival-goer in Buenos Aires.
"""
import json
import re
import sqlite3
from pathlib import Path

import analyze
import spotify

HERE = Path(__file__).parent
ALBUMS = {artist: cfg["albums"] for artist, cfg in analyze.BANDS.items()}
key = spotify.key
SURE, HIGH, MIN = 0.9, 0.5, analyze.MIN_P
SECTION = {"opening": "apertura", "middle": "medio", "closing": "cierre", "encore": "bis"}


def tracklists():
    return {aid: [t["name"] for t in tracks] for aid, tracks in
            spotify.album_tracks([aid for albums in ALBUMS.values() for _, _, aid in albums]).items()}


def pct(p):
    return f"{p * 100:.0f}%"


DAYS = {"Gorillaz": "Sábado 28/11", "The Strokes": "Domingo 29/11"}
TIERS = [("Sí o sí", SURE, 2, f"Probabilidad de {pct(SURE)} o más: sonaron en prácticamente todos los shows recientes."),
         ("Altas chances", HIGH, SURE, f"Entre {pct(HIGH)} y {pct(SURE)}: más probable que suenen que no."),
         ("Posibles", MIN, HIGH, f"Entre {pct(MIN)} y {pct(HIGH)}: rotan; puede tocar cualquiera de estos.")]


def build(artist, shows, tracks, links):
    """All the report data for one band; REPORT.md and report.html are generated from here."""
    stats, dep = analyze.predict(shows, artist)
    raw = analyze.song_stats(shows)
    album_of = {key(t): name for name, _, aid in ALBUMS[artist] for t in tracks[aid]}
    by_key = {key(s): s for s in stats}
    last = {}
    for s in shows.values():
        for song, _ in s["songs"]:
            last[song] = s["date"]
    fest = [len(s["songs"]) for s in shows.values() if s["festival"]]

    def song(name):
        v = stats[name]
        return dict(song=name, album=album_of.get(key(name)), p=round(v["p"], 3), p_rep=round(v["p_rep"], 3), n=raw[name]["n"],
                    section=analyze.section_label(v), spotify=links.get(f"{artist}|{name}"))

    tiers = [dict(title=t, note=note, songs=[song(k) for k in sorted(
        (k for k, v in stats.items() if lo <= v["p"] < hi), key=lambda k: -stats[k]["p"])])
             for t, lo, hi, note in TIERS]
    albums, rare = [], []
    for name, year, aid in ALBUMS[artist]:
        played = [by_key[key(t)] for t in tracks[aid] if key(t) in by_key]
        albums.append(dict(name=name, year=year, total=len(tracks[aid]), played=len(played),
                           never=[re.split(r" - | \(feat\.", t)[0] for t in tracks[aid] if key(t) not in by_key]))
        rare += [dict(song=s, album=name, n=raw[s]["n"], last=last[s]) for s in played if stats[s]["p"] < MIN]
    cut = [song(k) for k in sorted((k for k, v in stats.items() if v["p_rep"] >= analyze.MIN_REP
                                    and v["fest_ratio"] < analyze.FEST_CUT), key=lambda k: -stats[k]["p_rep"])]
    must = [dict(song(k), reason=r) for k, r in analyze.BANDS[artist].get("must", {}).items()]
    guests = [dict(song=k, guest=g, n=raw[k]["n"]) for k, g in sorted(dep.items(), key=lambda kv: -raw[kv[0]]["n"])]
    return dict(artist=artist, day=DAYS[artist], cut=cut, must=must, guests=guests, shows=len(shows), festivals=len(fest),
                set_len=analyze.festival_length(shows), first=min(s["date"] for s in shows.values()),
                last=max(s["date"] for s in shows.values()), tiers=tiers, albums=albums, rare=rare)


def markdown(bands):
    md = ["# Informe: qué vas a escuchar en Primavera Sound Buenos Aires 2026", "",
          "Set de festival esperado: ~1,5 h. Las probabilidades salen de toda la gira actual en setlist.fm (pesan más "
          "los shows recientes y los festivales); el método completo está en RESULTS.md. Generado por `report.py`.", ""]
    for b in bands:
        md += [f"## {b['artist']} ({b['day']})", "",
               f"{b['shows']} shows de la gira ({b['festivals']} festivales), {b['first']} a {b['last']}. "
               f"Set de festival típico: {b['set_len']} temas.", ""]
        for t in b["tiers"]:
            md += [f"### {t['title']} ({len(t['songs'])})", "", t["note"], "",
                   "| Tema | Disco (primeros 4) | Probabilidad | Sonó en la gira | Sección |", "|---|---|---|---|---|"]
            md += [f"| {s['song']} | {s['album'] or ''} | {pct(s['p'])} | {s['n']} de {b['shows']} | {SECTION[s['section']]} |"
                   for s in t["songs"]] + [""]
        md += ["### Suenan en sus shows, pero en festival se suelen caer", "",
               "En el repertorio actual, pero los recortaron en los festivales recientes. Si el set de BA es largo, entran.", "",
               "| Tema | En el repertorio actual | Probabilidad en festival |", "|---|---|---|"]
        md += [f"| {s['song']} | {pct(s['p_rep'])} | {pct(s['p'])} |" for s in b["cut"]] + [""]
        if b["must"] or b["guests"]:
            md += ["### Invitados", ""]
            md += [f"- **{s['song']}** entra a la playlist igual: {pct(s['p'])} por la gira, pero el invitado es de acá."
                   for s in b["must"]]
            md += [f"- Se descuentan porque casi siempre sonaron con un invitado que no va a estar: " + "; ".join(
                f"{g['song']} ({g['guest']}, {g['n']} de {b['shows']} shows)" for g in b["guests"]) + "."] if b["guests"] else []
            md.append("")
        md += ["### Primeros 4 discos: qué no se toca", "",
               "**No sonaron en ningún show de la gira** (o sea, muy improbables):", ""]
        md += [f"- **{a['name']}** ({a['year']}), {a['played']} de {a['total']} se tocaron. No sonaron: "
               + (", ".join(a["never"]) or "ninguno") + "." for a in b["albums"]]
        md += ["", f"**Sonaron alguna vez pero hoy están por debajo del {pct(MIN)}** (sorpresas posibles, no esperables):", ""]
        md += [f"- {r['song']} ({r['album']}): {r['n']} de {b['shows']} shows, la última el {r['last']}."
               for r in b["rare"]] or ["- ninguno"]
        md.append("")
    return "\n".join(md)


def main():
    con = sqlite3.connect(HERE / "setlists.db")
    tracks = tracklists()
    load = lambda f: json.loads((HERE / f).read_text(encoding="utf-8")) if (HERE / f).exists() else {}
    links, playlists = load("spotify_links.json"), load("spotify_playlists.json")
    bands = [build(a, analyze.load(con, a), tracks, links) for a in ALBUMS]
    for b in bands:
        b["playlist"] = playlists.get(b["artist"])
    (HERE / "REPORT.md").write_text(markdown(bands), encoding="utf-8")
    data = json.dumps(dict(bands=bands, min_p=MIN, generated=analyze.time.strftime("%Y-%m-%d")), ensure_ascii=False)
    html = (HERE / "report_template.html").read_text(encoding="utf-8").replace("/*DATA*/null", data.replace("</", "<\\/"))
    (HERE / "report.html").write_text(html, encoding="utf-8")
    print("REPORT.md and report.html written")


if __name__ == "__main__":
    main()
