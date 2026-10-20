---
name: doc-clean
description: Clean photographed exam pages and merge them into one PDF.
version: 1.1.0
author: "Berton (github: afanty2021), Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Documents, Image Cleanup, PDF, Handwriting, Worksheets]
    category: media
---

# doc-clean Skill

Turn photographed exam papers or worksheets into a clean electronic PDF. Two routes: **re-typeset** the printed content into a fresh vector PDF (default — no erasure artifacts at all), or **photo-repair** the original images (erases handwriting, keeps the exact original layout). Printed content is never altered on either route.

## When to Use

- A user sends photos of exam papers / worksheets and wants the handwriting gone and one merged electronic copy back.
- Decide the route:
  - **Route B, re-typeset — DEFAULT for math/text worksheets.** Vector pages, print-quality, and the entire defect class of photo repair (smudge patches, print damage, leftover strokes) cannot occur. Choose this unless an exception below applies.
  - **Route A, photo-repair — this skill's erase pipeline.** Choose when ANY of: the user needs the ORIGINAL sheet layout preserved (teacher requires the exact page); pages carry complex/photographic figures that cannot be redrawn; speed matters more than finish (minutes vs an hour+ of vision calls); or no XeLaTeX is available.
  - Confirm the choice in one line when delivering either route.

## Prerequisites

- Python with Pillow (the Hermes environment ships it) — `scripts/doc_clean.py` needs nothing else.
- Optional: `pip install opencv-python-headless` upgrades large-region fills (auto-detected; `--engine cv2` forces it).
- `vision_analyze` with `boxes: true` for pencil / black-pen marks. Colored pens need no vision call.
- Route B additionally needs `xelatex` with the `ctex` package (TeX Live). Check with `xelatex --version`; absent → fall back to Route A.

## How to Run

Everything runs through `terminal` with `scripts/doc_clean.py` (path relative to this skill's directory). EXIF orientation is honored automatically, so camera photos need no manual pre-rotation.

```bash
python scripts/doc_clean.py deskew --in page.jpg --out page_straight.jpg
python scripts/doc_clean.py ink   --in page_straight.jpg --out page_clean.png --hue blue
python scripts/doc_clean.py erase --in page_clean.png --out page_clean.png --boxes page_boxes.json
python scripts/doc_clean.py split --in spread.jpg --outdir pages/
python scripts/doc_clean.py merge p1.png p2.png p3.png p4.png --out exam.pdf
```

## Quick Reference

| Command | Effect | When |
|---|---|---|
| `deskew` | straighten page tilt (prints the angle it applied) | photographed, not scanned pages |
| `rotate` | rotate by an exact angle (`--angle 180`) | upside-down pages; `deskew` cannot fix 180° |
| `ink` | erase colored-pen strokes (channel-chroma test) | blue/red/green pens; `--hue` narrows |
| `erase` | erase rectangles from a boxes JSON | pencil / black-pen marks, big blobs |
| `split` | cut a two-page spread at the fold | one photo holds two pages |
| `merge` | page images → one PDF | final step |

Each command prints one JSON status line (`ok`, counts, output path). If a page is upside down, `rotate --angle 180` it first and confirm the orientation with one `vision_analyze` call.

## Route B — Re-typeset (default for math worksheets)

Transcribe the PRINTED content only, rebuild as LaTeX, and compile. Model-driven: every vision call below is `vision_analyze` (prose mode), issued serially with ~6s gaps (the aux vision endpoint rate-limits under concurrency).

1. **Inventory** — one call per full page: "list the printed problems in order: number, first words of each stem, sub-items, any table/grid/figure". This is the completeness baseline every later step checks against.
2. **Transcribe** — per page, TOP/BOTTOM half-crops resized to ≤1300px width (full pages time out): "transcribe ONLY printed content as LaTeX; ignore ALL handwriting and smudges; blanks as `\blank`; number grids and figures as `\GRID{...}`/`\FIGURE{...}` placeholders". Use a half-page `region` crop when a whole half times out.
3. **Resolve every ambiguity with a dedicated zoomed crop** — one question per crop, 2x resize. Conflicting reads (a sign, a numerator, a bracket) are normal where handwriting overlaps print; NEVER pick between conflicting reads without a tie-breaker. Prefer arithmetic validation: substitute the candidate reading into the expression — the printed problem usually evaluates to a clean number. Reject any reading that makes a leading mixed number ugly (`2 2/4` is a misread of `2 3/4` or `2 1/2`).
4. **Assemble and compile** — `ctexart`, `zihao=5`, one `\clearpage` per Day/section so no section straddles pages. Redraw each `\FIGURE` placeholder from its own figure crop via TikZ (flowcharts, grids, number lines are all feasible; a figure you cannot describe structurally is a Route-A signal). Typeset the whole document, then fix compile errors.
5. **Glyph gate (before any visual check)** — the compile log MUST have zero `Missing character` lines. Circled digits ①②③ default to the Latin font and are silently dropped; fix with `\xeCJKDeclareCharClass{CJK}{"2460 -> "24FF}` in the preamble. Also grep the extracted text for spot-check numbers.
6. **Fidelity loop** — `pdftoppm -png` the PDF, build side-by-side ORIGINAL|RENDER sheets, and ask `vision_analyze` per page: "report ONLY concrete discrepancies (题号 + what differs)… end with DISCREPANCY COUNT: N". **Half-page strips only** — full-page comparison sheets time out. Fix and re-check until zero, distinguishing real defects from page-alignment artifacts.
7. **Deliver** the compiled PDF and name the two or three low-confidence readings in the delivery message.

## Procedure — Route A (photo repair)

1. **Orient and split.** Run `deskew` then `split` per photo into a working directory. Batch all independent page commands in ONE tool batch — they run concurrently.
2. **Colored pens first** (cheap, no vision): `ink` with `--hue auto`. Check the `share` value it prints: near 0 means the handwriting is not colored — skip to step 3; a large share on a page with only faint color print means lower `--tolerance` or a specific `--hue`.
3. **Pencil / black pen** (vision-guided): call `vision_analyze` with `boxes: true` and a locator question, e.g. "all handwritten strokes, answers, and teacher marks — exclude all printed text". Issue ALL pages' calls in ONE tool batch (they run concurrently; never one page per turn). Save each result JSON to a file. Boxes arrive in original-image pixel coordinates, ready to use as-is — any region-crop offset is already applied (`offset` in the result is informational only).
4. **Erase**: `erase --boxes <file>.json` per page. Review each box's `label` before erasing — a wrong label means printed content gets filled over.
5. **Verify** before merging: one cheap `vision_analyze` per cleaned page — "Is any handwriting still visible? Answer yes/no and where." — again batched. Re-run step 3 on pages that fail with tighter boxes.
6. **Merge** in page order and deliver the PDF.

Long vision calls: a page that times out once should be retried as `region` crops (left/right half), not re-sent whole. The vision timeout itself is `auxiliary.vision.timeout` in config.yaml.

## Pitfalls

- Pencil and black pen have ~zero color chroma: `ink` cannot see them — that is what `vision_analyze boxes: true` + `erase` are for.
- Colored print (maps, stamps, color figures) is chromatic too: on such pages use `--hue` matching the pen, raise `--tolerance`, and verify the page afterwards.
- `image_generate` must NOT be used to "redraw" a clean page — generative models alter the printed text, which is unacceptable for papers.
- Photos taken at a steep angle need re-shooting; `deskew` only fixes small tilts, not perspective.
- Route B: handwriting overlapping print is the dominant misread source — a stroke through a fraction turns `3/4` into `1/4`-looking glyphs. Anything not confirmed by two consistent reads or an arithmetic tie-break is a low-confidence item for the delivery note.
- Route B: an all-negative or all-identical number grid usually means a sign was misread — real worksheet puzzles are solvable as stated. Re-check with a zoomed crop when a transcribed problem is degenerate.
- Route B: a VLM fidelity pass hallucinates on downscaled sheets ("extra problem 13" that exists nowhere). A claimed discrepancy in content you transcribed and arithmetically validated is disproven by the extracted PDF text (`pdftotext`) — trust that over the vision read.

## Verification

- `merge` prints the page count — compare with the number of physical pages before delivering.
- Open one cleaned page with `vision_analyze`: "Is any handwritten mark visible?" must answer no, and printed text must read correctly.
- Confirm the delivered PDF is the merged file reported by `merge` (path + page count), not an intermediate page image.
- Route B: zero `Missing character` lines in the compile log; fidelity loop ended at DISCREPANCY COUNT: 0 (or every remaining item is a named low-confidence reading in the delivery message); page count matches the section layout (one section per page, or a stated reason).
