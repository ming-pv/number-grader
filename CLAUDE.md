# POSN Grader — Project Context

## What this project is
A single-file web app (`index.html`) that automatically grades answer sheets for problems 11–15 using live camera + OCR. No server, no paid API. Built for a Thai science olympiad (POSN) grading workflow.

## How to run
Open `index.html` directly in a browser **OR** for live camera (requires HTTPS/localhost):
```
python -m http.server 8000
```
Then open `http://localhost:8000` on the device with the camera.

For a phone with live camera, host on Netlify Drop (drag-and-drop) or GitHub Pages — both give free HTTPS.

## Correct answers (problems 11–15)
| Problem | Answer | Notes |
|---|---|---|
| 11 | 36 | |
| 12 | 9/20 = 0.45 | accepts either form |
| 13 | 48000 | accepts 48,000 with comma |
| 14 | 24 | |
| 15 | 480 | |

Each scores 0 or 1. Output: `[1,0,1,1,1]  sum = 4/5`

## Answer sheet format (critical for detection)
- The sheet has **two side-by-side tables**: left table = P1–15, right table = P16–30
- Each table has: narrow left column (printed problem number) | wide right column (handwritten answer)
- Camera frame usually shows **rows 4–15 or 8–15** (not just 11–15)
- Problems 11–15 are always the **bottom 5 rows** of the left table
- Numbers "11."–"15." are **printed** in the left column — these are the detection anchors
- Numbers "26."–"30." in the right table share the same y-positions and are used as backup
- Rows are always horizontal (portrait or landscape camera hold)
- Student answers can include Thai text alongside numbers (e.g. "36 ตัว", "480 สถานีเมตร")
- Answers may be written with strikethroughs, corrections, unit labels — match only the numeric part

## How detection works (two-pass OCR)

### Live loop (every 250ms)
- Runs `autoDetect()` on each camera frame for the overlay boxes
- Uses **longest-continuous-neutral-dark-run** per row (not average darkness)
  - Neutral-dark = gray < 145 AND color saturation < 55 (ignores red/blue pen marks)
- Scans only **left 65% of image** to ignore the right table
- Takes the **last 6 detected lines** → always bounds P11–P15 (bottom of table)
- Triggers OCR when stable for ~1.5 s (6 × 250ms frames)

### OCR pass (every 4 s when stable)
**Pass 1**: Crops left 26% of image (number column only), runs Tesseract with digit whitelist, finds bounding boxes of "11"–"15" (and "26"–"30" as backup). Uses y-positions to define exact row centers and spacing.

**Pass 2**: For each of the 5 rows, crops the answer area (x: 27%–63% of image width) at 3× upscale with white padding, runs Tesseract with number whitelist (`0123456789./,= -`).

### Answer matching
```javascript
// Fraction: "9/20" → 0.45
// Decimal: "0.45", ".45"
// With commas: "48,000" → 48000
// With Thai text: extracts first number found
// Tolerance: ±0.001 for decimals, ±1 for large integers
```

## Key files
- `index.html` — the entire app (single file, ~700 lines)
- `answer sheet blank.jpg` — blank answer sheet (shows layout)
- `answer sheet corner 1.jpg` — example camera frame (portrait, rows 4–15 visible)
- `answer sheet corner 2.jpg` — example camera frame (landscape, rows 8–15 visible)
- `answer sheet example.jpg` — example with actual student answers written in

## Known issues / what still needs work
1. **OCR accuracy on handwriting** — Tesseract struggles with messy handwriting, Thai text mixed in, strikethroughs, and fraction notation (9 over 20). The manual score flip (tap any chip) is the main workaround.
2. **Detection when camera is at an angle** — geometric detection assumes horizontal lines; perspective-corrected images would help but haven't been implemented.
3. **P13 answer confusion** — student wrote "240,000" (wrong) or "24,000" but correct is 48000; OCR sometimes reads partial digits. May need larger answer region.
4. **First OCR load** — Tesseract.js downloads ~14 MB language data on first use (internet required once, then cached in browser).
5. **Live camera on file://** — blocked by browsers; use localhost or HTTPS hosting.

## Tech stack
- Pure HTML/CSS/JS, no build step
- **Tesseract.js v4** via `https://cdn.jsdelivr.net/npm/tesseract.js@4/dist/tesseract.min.js`
- No framework, no backend, no API key

## Detection tuning parameters (in `autoDetect()`)
```javascript
const DARK      = 145;    // pixel darkness threshold
const LSCAN     = W*0.65; // scan left 65% of image (ignores right table)
const MIN_H_RUN = W*0.10; // line must span ≥10% of width to count
// saturation limit for neutral-dark filter: 55 (rejects colored ink)
```

## Answer region x-coordinates (in `buildAnswerRegions()`)
```javascript
const ansX = imgW * 0.27;  // right edge of number column
const ansW = imgW * 0.36;  // width (covers ~27%–63% of image)
```
These are tuned for the specific sheet format. Adjust if the sheet is photographed at a different zoom level.

## UX flow
1. Camera opens automatically (back camera on mobile)
2. Colored dashed boxes appear on detected P11–P15 regions in real time
3. When stable for 1.5 s → OCR fires automatically (no button press needed)
4. Scores appear: `P11 P12 P13 P14 P15` chips show 1 (green) / 0 (red) / ? (orange)
5. Tap any chip to manually flip its score
6. Point at next sheet → motion resets stability counter → re-grades in ~1.5 s
7. Reset button clears scores without restarting camera

## Conversation history summary
The app was built iteratively:
1. Started as upload-based grader → switched to live camera
2. Added auto-detect (geometric) → poor results with two-table sheet and red scribble
3. Switched to OCR-based row detection (find printed "11"–"15" first) → much better
4. Added neutral-dark pixel filter to ignore red/colored pen marks
5. Still open: improve accuracy for messy handwriting, perspective correction
