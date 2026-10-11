# Probable setlists: The Strokes and Gorillaz at Primavera Sound Argentina

> The original brief, written by one Claude session and handed to another that built the project. Translated from
> Spanish; references to private tooling removed. The deliverables later grew past it (see RESULTS.md).

Brief (2026-10-10). The user has a ticket for Primavera Sound Argentina (late November; check the date, venue and which
day each band plays on the web). They want the most probable setlist for each band and two 30-song playlists, one per
band, in show order.

## Decisions already made (don't ask again)

- **Data:** each band's current tour, every show. If the current tour has few shows, add the previous one, tagged
  separately and with less weight. **ALL the data, no summarizing or sampling:** every show with its full setlist.
- **Source:** setlist.fm (web or API; the API needs a free key: if needed, ask the user for it in a single line).
  Every show keeps its source URL. If a show can't be downloaded, it is recorded as missing, never made up.
- **Spotify:** design the playlists with a link for each song. Creating the playlists on Spotify is the **last step,
  and only with the user's OK**: before that, find the best route (Spotify MCP or API) and propose it.
- Anything that can be found on the web (date, festival set lengths, tours) is looked up, not asked.

## Deliverables, all in this folder

1. **`setlists.db`** (SQLite, the stdlib's `sqlite3`):
   - `shows(id, artist, date, city, country, venue, tour, is_festival, set_minutes, source_url)`
   - `performances(show_id, position, song, section, is_cover, is_tape, notes)`, where `section` is `main` or `encore`
     (and `encore_2` if there is one), and `position` is the real order within the show.
   - The script that fills it (`build_db.py`), re-runnable.
2. **`analyze.py`**: per song, how many shows it appears in (%), mean relative position (`position / show length`)
   with its spread, and how many times it opens, closes the main set, opens the encore or closes the show. Everything
   split into **festival shows and headline shows**, because a festival set is shorter and that's what they'll see.
3. **Patterns**: a fixed opener, a fixed encore block, songs that always go together in the same order (repeated A→B
   transitions), songs rotating in the same slot, and changes along the tour (something that came in or out lately).
4. **Most probable setlist** for each band, with the typical length of their festival set: the songs in the order they
   will probably play, each with its probability.
5. **Two 30-song playlists** (one per band): the probable setlist in order, plus the next most probable songs up to
   30, each placed in its typical position (if a song usually closes, it goes at or near the end). Columns: order,
   song, probability, section (opening, middle, closing, encore), Spotify link.
6. **`README.md`**: method, sources, number of shows per band and tour, missing shows, patterns, probable setlists
   and the two playlists.

## How to work

- Python with the stdlib and `sqlite3`; dependencies only if truly needed.
- Run `date` before writing down any time. If the user asks how it's going, answer in a fixed status format (what is
  running, what advanced, what it's waiting on, what's left, last update).
- Questions to the user: only the essential ones, all together in a single batch (4 at most).
- When done: a usage table (tokens per subagent if any were used, and the session total).
