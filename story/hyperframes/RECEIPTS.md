# Receipts: HyperFrames build

Engine: HyperFrames 0.8.146 CLI, installed locally in `story/hyperframes/` (no Claude Code plugin). GSAP 3.15.0 and CustomEase vendored, fonts shipped as local woff2. Telemetry off: `HYPERFRAMES_NO_TELEMETRY=1` on every command, plus `hyperframes telemetry disable` (status: disabled, source: config). Snapshots run with `--describe false`, so no frame ever goes to the Gemini vision API.

## The prompt

`story/PROMPT.md`, as is, with this OUTPUT line:

> [HyperFrames] one HyperFrames composition (HTML + CSS + GSAP timeline), rendered with the HyperFrames CLI. Both: 1280x720, H.264 yuv420p, CRF tuned so the file is 10 MB or less, no audio.

Brief correction before the first build (data, not creative): playlist 148 min, not 144; Garage Palace drains 31% → 8%, not to 0.

## Creative follow-ups, exactly as acted on

Round 1, after stills at frames 0, 120, 255, 405, 585, 735 (`snapshot --at`, contact sheet):

1. Frame 0 is the poster and reads empty: the right 55% is bare paper. Draw the wall's 77 slots as dashed outlines in line color from frame 0, so the cards land into a grid that is already there, and scale the ticket to 1.15x.
2. Frame 255: both session sheets are half empty below the content. Cut them to 400 tall, start them at 160, and set the SPEC.md lines at 17 px.
3. Frame 405: the pipeline sits in a thin strip at mid-height with 60% of the frame empty, and "Spotify playlists + report" wraps to three lines. Nodes 250x150, names 28 px, centers on the same line; widen the last node to 270.
4. Frame 585: the strike-through crosses the "8%" so the number the scene is about can't be read. Strike only the song name and keep 8% legible, and point the "guest discount" note at the row with a 14-frame pen arrow.
5. Frame 585: the draft sheet's bottom third is empty. Height 470.
6. Frame 735: the bottom fade never shows anything, because the 10 rows end above it. Add rows 11 to 14 (El Mañana, On Melancholy Hill, Orange County, O Green World) so the fade implies the rest of the 37.

Round 2, after a 5x5 contact sheet (one still per second, 0 to 24 s):

7. Frames 0 and 120: the scaled ticket overlaps the wall's first column. Ticket scale 1.1.
8. Frame 405: the pipeline still sits in a thin strip with the top half empty. Add a marker headline at 64, 120, 48 px: "77 shows in. Two playlists out." It fades with the nodes at 412.
9. Frames 135, 270 and 600 cut to bare paper, because each new scene's sheets fade in from 0. On a hard cut the main sheets are on screen on the cut frame: start them at full opacity with a 16 px settle on the 0.75 spring, and fade only the secondary elements.

Round 3, after stills on both sides of every cut (4.5, 9, 13.9, 14.2 and 20 s): no notes. Every cut lands on content, and the match cut reads from the model node into the draft sheet.

Round 4, the human's note after watching the first finished render (the plain HTML build was compared against this one and dropped here, mostly for its weaker motion):

10. "It's missing the most important thing: the playlist." Shot 5 showed one setlist sheet and a "report published" stamp, so the product never appeared and The Strokes vanished after frame 134. Rebuild 600 to 749 as the product: two playlist sheets on screen at the cut, "GORILLAZ · 37 songs · 148 min" (rotated -1) and "THE STROKES · 32 songs · 118 min" (rotated 1, settling 4 frames later). Each shows its first 8 songs in show order with a mono section tag, rows 2 frames apart (Gorillaz from 604, The Strokes from 616), and a bottom fade over rows 7 and 8. At 650, "Two playlists. Listen" in pen marker, with a pen arrow drawing down from 660 to 678 toward the Spotify links in the README under the video. Drop the stamp and the "v1 in under an hour" line: the README already says it.

Round 5, stills at 20, 20.5, 22 and 24.5 s: no notes.

Round 6, two more notes from the human:

11. "Add a closing aside at the end, with very little weight and only a few frames: something like 'and by the way, I tested a new motion design tool making this video'." Mono 14 px in muted, right-aligned in a 380 px box at the bottom right, fading in over 6 frames from frame 705 and held to the end: "P.S. This video doubled as a test of HyperFrames, motion design in code." The first still put it right against the Listen arrow, so it wraps to two lines and right-aligns.
12. "Make the video twice as long: each frame should last what 2 frames last today." Done as true slow motion, not frame doubling: one `SLOW = 2` factor scales every storyboard frame and duration, and the spring is evaluated on the storyboard clock so its shape stretches too. Clip windows and the root duration were doubled to 50 s. Rendered at 30 fps: 1,500 distinct frames, none duplicated.

Round 7, stills at 1, 16, 40 and 49.8 s: no notes. Motion runs at half speed with the same composition.

## Technical fixes (not counted as creative)

- The render flagged frames 418 to 420 as "blank-frame suspect" and re-captured them. They are correct: that is the match cut, with only the model node and then the small draft sheet on screen. Checked on a 6-frame strip decoded from the MP4.
- `hyperframes lint`: 0 errors and 6 structure warnings (it suggests splitting scenes into sub-compositions). Left monolithic on purpose: a single 25 s file is easier to diff and to print in this receipt.

## Not used

The CLI also offers `feedback` (sends a report to HeyGen), `usage` (reads your Claude Code credentials to report quota), `snapshot --describe` (sends frames to Gemini) and `cloud render`. None of them ran.

## Counts

| | |
|---|---|
| Review rounds | 7 (four with notes, three clean) |
| Creative follow-ups | 12 (9 from Claude reviewing its own frames, 3 from the human) |
| Brief corrections (data) | 1 |
| Frames | 1,500 (50 s at 30 fps; storyboard frame numbers above are at the original 25 s timing) |
| Final MP4 | 1.61 MB, H.264 yuv420p, CRF 20, 1280x720 |
| Final render time | 22 s on a Ryzen 9 5900X (final MP4 written 03:47:38) |
| Wall time, install to first finished MP4 | 6 min 44 s (package.json created 03:30:18, MP4 written 03:37:02) |
| Wall time, the human's note to the final MP4 | under 4 min 44 s (last clock read before the note 03:39:37, MP4 rewritten 03:44:21) |

Outputs: `docs/hyperframes/setlist-predictor.mp4` and `docs/hyperframes/scene-1.png` to `scene-5.png` (at 8, 17, 27, 39 and 49 s of the 50 s cut).
