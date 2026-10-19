---
name: doc-clean
description: Clean photographed exam pages and merge them into one PDF.
version: 1.0.0
author: "Berton (github: afanty2021), Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Documents, Image Cleanup, PDF, Handwriting, Worksheets]
    category: media
---

# doc-clean Skill

Turn photographed exam papers or worksheets into a clean electronic PDF: straighten each shot, remove handwritten marks, and merge the pages. Printed content is preserved pixel-for-pixel — only handwriting is erased.

## When to Use

- A user sends photos of exam papers / worksheets and wants the handwriting gone and one merged electronic copy back.
- First decide which "electronic" the user means:
  - **Clean-image PDF** (original layout preserved): this skill's pipeline.
  - **Editable text rebuild**: transcribe each page with `vision_analyze` (prose mode) instead, assemble the text, and skip image cleanup entirely.

## Prerequisites

- Python with Pillow (the Hermes environment ships it) — `scripts/doc_clean.py` needs nothing else.
- Optional: `pip install opencv-python-headless` upgrades large-region fills (auto-detected; `--engine cv2` forces it).
- `vision_analyze` with `boxes: true` for pencil / black-pen marks. Colored pens need no vision call.

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

## Procedure

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

## Verification

- `merge` prints the page count — compare with the number of physical pages before delivering.
- Open one cleaned page with `vision_analyze`: "Is any handwritten mark visible?" must answer no, and printed text must read correctly.
- Confirm the delivered PDF is the merged file reported by `merge` (path + page count), not an intermediate page image.
