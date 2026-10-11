# Directed prompt (shared by both engines)

The same brief drove two builds, plain HTML and HyperFrames; only the OUTPUT line changed. After comparing both renders the HTML build was discarded: its motion was clearly weaker. Every follow-up after this prompt is in `story/hyperframes/RECEIPTS.md`.

```text
GOAL: a README hook for setlist-predictor. In 25 s the viewer gets the story: 77 tour setlists nobody can read by hand → a two-session Claude method → a data pipeline → a human catches what the model missed → a real playlist. They should leave thinking "this person directs AI with judgment".

OUTPUT: [HTML] one self-contained HTML file, no libraries; window.renderAt(t) draws exactly time t; rendered with Playwright + ffmpeg.
        [HyperFrames] one HyperFrames composition (HTML + CSS + GSAP timeline), rendered with the HyperFrames CLI.
        Both: 1280x720, H.264 yuv420p, CRF tuned so the file is 10 MB or less, no audio.

TIME: 25 s x 30 fps = 750 frames (0 to 749). Not a loop. Frame 0 is a finished composition (it is the poster). Last 90 frames hold the final card.

LOOK: a printed setlist sheet taped to a stage floor.
  Palette: paper F5F6F3 (background), sheet FFFFFF (cards, 1 px DCDDD8 border, 6 px radius), ink 17181C, muted 5D606B, line DCDDD8, highlighter FFE35A (behind text only, slightly skewed, 92% opacity), pen 2C55D6 (hand-drawn arrows, margin notes, underlines), strike C8342B (strike-throughs only).
  Type: Permanent Marker for headlines (56 to 72 px, tracking 0); Instrument Sans 500/600 for labels and body (20 to 28 px); IBM Plex Mono 500 for numbers, file names and eyebrows (16 to 20 px, uppercase eyebrows, tracking 0.08 em).
  Layout: 64 px safe margin on every side; left-aligned compositions, never centered-everything; one sheet per scene, rotated -1.5 to 1.5 degrees like paper on a floor.
  All on-screen text in English.

MOTION:
  Easing: enter cubic-bezier(0.16, 1, 0.3, 1) (ease-out-expo); move cubic-bezier(0.76, 0, 0.24, 1); exit cubic-bezier(0.7, 0, 0.84, 0), exits 40% shorter than entrances.
  Springs: position and scale only, damping ratio 0.75 at 2.2 Hz; opacity and color never bounce.
  Durations: hero reveal 18 frames; secondary 12 frames starting 4 to 6 frames after the hero at 60% of its travel; list items 2 frames apart.
  Pen strokes draw on (stroke-dashoffset) over 14 frames, ease-in-out. Highlighter swipes left to right over 10 frames. Strike-through draws over 8 frames.
  Text holds at least 0.3 s per word + 0.5 s before it moves or leaves.
  Scene handoff: hard cut on the frame listed, except 3 → 4 where the "model" node becomes the scene-4 sheet (match cut, 12 frames).

SHOTS (frame ranges at 30 fps):
  1. The problem, 0 to 134. Frame 0: a festival wristband/ticket card "PRIMAVERA SOUND · BUENOS AIRES · 2026" with "GORILLAZ" and "THE STROKES" on it. 6 to 24: headline in marker "What will they play?" types in by word (4 frames per word). 30 to 100: behind it, a wall of 77 tiny setlist cards fills in (47 tinted for Gorillaz, 30 for The Strokes, 1 frame apart, left to right, top to bottom), each card covered in unreadable mono lines. 100 to 134: a pen counter in the margin: "77 shows. Unreadable by hand."
  2. The method, 135 to 269. Two sheets side by side: "SESSION A" (left) and "SESSION B" (right), eyebrow labels in mono. 140 to 190: on A, lines of a file named SPEC.md write in (2 frames per line, 8 lines). 195 to 215: a pen arrow draws from A to B with the label "hands off SPEC.md". 215 to 260: on B, a checklist ticks (build_db.py, analyze.py, spotify.py, report.py), one tick every 8 frames, pen color.
  3. The pipeline, 270 to 419. Four nodes on one horizontal line, connected by a pen path that draws left to right: "setlist.fm API" → "SQLite" → "model" (sub-label in mono: "batches × festival factor") → "Spotify playlists + report". Each node lands 14 frames after the previous one. 340 to 400: small ink dots travel the path (constant speed, linear), 6 dots, 8 frames apart. Hold to 419.
  4. The human in the loop, 420 to 599. Match cut: the model node grows into a setlist sheet. 430 to 460: a margin note in pen, handwritten style (Permanent Marker, pen color): "what about the feats?". 465 to 520: a card slides in: "TRUENO · 8 of the 9 shows with The Manifesto · from Buenos Aires"; then a new row "The Manifesto" inserts into the setlist with a highlighter swipe. 530 to 590: row "Garage Palace · with Little Simz in 14 of 14 plays" shows a 31% bar; a "guest discount" label appears; the bar and its number drain from 31% to 8% over 20 frames, then a red strike-through draws across the row; mono tag "out of the playlist".
  5. The result, 600 to 749. A clean final setlist sheet: header "GORILLAZ · predicted setlist", meta in mono "37 songs · 148 min"; 10 visible song rows (fade in 2 frames apart), the rest implied by a fade-out at the sheet's bottom edge. 625: stamp "report published" in pen, rotated -6 degrees, scale spring from 1.15 to 1. 660 to 749: final line in Instrument Sans 600, 32 px: "v1 working in under an hour; the rest was iteration." held to the last frame.

BANNED: purple or blue gradients, glow, bloom, lens flares, particles as decoration, dark backgrounds, centered-everything layouts, fade-and-slide-up on every element, everything entering at once, text moving while being read, emoji, stock icons, fake UI chrome (browser bars, macOS window dots), any logo of Gorillaz, The Strokes, Primavera Sound, Spotify or setlist.fm (names in type only).

QA: renderAt(t) is a pure function of t, no Date.now, timers or unseeded random; fonts loaded (document.fonts.ready) before frame 0. Stills at frames 0, 120, 255, 405, 585, 735 before the full render. Contact sheet of every 30th frame (25 tiles, 5x5). Fix, then render the full MP4. Deliver 5 PNG stills (one per scene: 120, 255, 405, 585, 735) at 1280x720.
```

## Brief corrections (before any build feedback)

1. Data fix, checked against the results: the Gorillaz playlist is 148 min (144 was before real Spotify durations), and Garage Palace drops from 31% to 8% after the guest discount, not to 0. Applied to SHOTS 4 and 5 above.
