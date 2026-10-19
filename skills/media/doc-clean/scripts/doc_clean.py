#!/usr/bin/env python3
"""Deterministic exam-paper cleanup primitives for the doc-clean skill.

Subcommands:
  ink     remove colored-pen handwriting via channel-dominance masking
  erase   erase regions given as a boxes JSON (vision_analyze boxes=true output)
  deskew  estimate and correct the page tilt of a photographed page
  rotate  rotate by an exact angle (180 for upside-down pages)
  split   cut a two-page spread into left/right pages at the gutter
  merge   merge page images into one PDF

Pillow only at the core (a Hermes base dependency); OpenCV is an optional
quality upgrade for ``--engine cv2`` (TELEA inpainting). EXIF orientation is
honored on every load, so camera photos need no manual pre-rotation.
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat


def _load(path):
    return ImageOps.exif_transpose(Image.open(path))


def _save(im, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path)
    return out_path


def _bin(img, threshold=0):
    """0/255 L-mask of pixels strictly above ``threshold`` (0 for a raw >0 test)."""
    return img.point(lambda v: 255 if v > threshold else 0)


# --- ink (colored handwriting removal) --------------------------------------

def ink_mask(im, hue="auto", tolerance=28):
    """L mask (255 = ink) of colored-pen strokes: a pixel is ink when its channel
    dominance (max band - min band) exceeds ``tolerance`` — printed black text and
    gray pencil have ~zero chroma and never match. ``hue`` narrows to one pen
    color; ``auto`` takes every chromatic pixel."""
    r, g, b = im.convert("RGB").split()
    chroma = ImageChops.subtract(
        ImageChops.lighter(ImageChops.lighter(r, g), b),
        ImageChops.darker(ImageChops.darker(r, g), b),
        offset=-tolerance)
    if hue == "auto":
        return _bin(chroma)
    # hue -> (dominant band, the two it must dominate): tint = dominant minus each minor.
    bands = {"red": (r, g, b), "green": (g, r, b), "blue": (b, r, g)}
    if hue not in bands:
        raise ValueError(f"unknown hue {hue!r} (auto|blue|red|green)")
    dominant, minor_a, minor_b = bands[hue]
    tint = ImageChops.multiply(
        ImageChops.subtract(dominant, minor_a, offset=1),
        ImageChops.subtract(dominant, minor_b, offset=1))
    return ImageChops.multiply(_bin(chroma), _bin(tint))


def _grow(mask, radius):
    """Dilate a mask by ``radius`` px so anti-aliased stroke edges are covered."""
    if radius <= 0:
        return mask
    return mask.filter(ImageFilter.MaxFilter(radius * 2 + 1))


def fill_mask(im, mask, radius=3):
    """Onion-peel fill: seed masked pixels with the median paper color, then
    repeatedly blur and paste the blurred values into the outermost ring of the
    masked area, closing inward — ring order lets real surrounding paper and
    print win over the seed guess near stroke edges. Thin strokes fill cleanly;
    large regions are better served by ``--engine cv2``."""
    im = im.convert("RGB")
    paper = tuple(ImageStat.Stat(im, ImageChops.invert(mask)).median)
    work = im.copy()
    work.paste(paper, mask)
    remaining = mask
    while True:
        if not remaining.getbbox():
            break
        eroded = remaining.filter(ImageFilter.MinFilter(radius * 2 + 1))
        boundary = ImageChops.subtract(remaining, eroded)
        blurred = work.filter(ImageFilter.GaussianBlur(radius))
        if boundary.getbbox():
            work.paste(blurred, (0, 0), boundary)
        remaining = eroded
    return work


def _try_cv2_inpaint(im, mask):
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    arr = np.asarray(im.convert("RGB"))
    return Image.fromarray(cv2.inpaint(arr, np.asarray(mask), 5, cv2.INPAINT_TELEA))


def _erase(im, mask, engine="auto"):
    if engine in ("auto", "cv2"):
        result = _try_cv2_inpaint(im, mask)
        if result is not None:
            return result
        if engine == "cv2":
            raise SystemExit(
                "engine cv2 requested but OpenCV is not installed (pip install opencv-python-headless)")
    return fill_mask(im, mask)


def cmd_ink(args):
    im = _load(args.input)
    mask = _grow(ink_mask(im, hue=args.hue, tolerance=args.tolerance), args.dilate)
    out = _erase(im, mask, engine=args.engine)
    _save(out, args.output)
    inked = mask.histogram()[255]
    print(json.dumps({"ok": True, "ink_pixels": inked,
                      "share": round(inked / (im.width * im.height), 4),
                      "output": str(args.output)}))


# --- erase (boxes from vision_analyze) ---------------------------------------

def load_boxes(path):
    """boxes list from a vision_analyze ``boxes=true`` result: accepts the whole
    result dict (``boxes`` + ``offset``), a bare {"boxes": [...]} or a bare list.
    The tool already maps boxes onto the full image (any region offset is baked
    in), so the ``offset`` field is informational only — coordinates pass through."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        boxes = data.get("boxes") or []
    elif isinstance(data, list):
        boxes = data
    else:
        raise ValueError("boxes file must be a list or a result object with a 'boxes' key")
    parsed = []
    for box in boxes:
        bbox = box.get("bbox") if isinstance(box, dict) else box
        if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
            raise ValueError(f"box without a 4-number bbox: {box!r}")
        x1, y1, x2, y2 = (float(v) for v in bbox)
        parsed.append([x1, y1, x2, y2])
    return parsed


def cmd_erase(args):
    im = _load(args.input)
    mask = Image.new("L", im.size, 0)
    draw = ImageDraw.Draw(mask)
    for x1, y1, x2, y2 in load_boxes(args.boxes):
        draw.rectangle([x1 - args.pad, y1 - args.pad, x2 + args.pad, y2 + args.pad], fill=255)
    out = _erase(im, mask, engine=args.engine)
    _save(out, args.output)
    print(json.dumps({"ok": True, "erased_px": mask.histogram()[255],
                      "output": str(args.output)}))


# --- deskew -------------------------------------------------------------------

def _profile_sum(img, along):
    """Mean of each row (``along='rows'``) or column (``'cols'``) via BOX downsample."""
    size = (1, img.height) if along == "rows" else (img.width, 1)
    return list(img.resize(size, Image.BOX).tobytes())


def estimate_skew(path, max_angle=6.0, step=0.2):
    """The PIL ``rotate()`` angle (CCW, degrees) that straightens the page: the
    angle whose row-projection of the ink mask is sharpest, scanned on a thumbnail."""
    im = _load(path).convert("L")
    im.thumbnail((900, 900))
    ink = im.point(lambda v: 255 if v < 128 else 0)
    # 0.0 floor: a blank page scores 0 at every angle and must stay at 0°, not
    # inherit the first angle tried.
    best_angle, best_score = 0.0, 0.0
    angle = -max_angle
    while angle <= max_angle + 1e-9:
        rotated = ink.rotate(angle, expand=True)
        profile = _profile_sum(rotated, "rows")
        score = sum((a - b) ** 2 for a, b in zip(profile[1:], profile[:-1]))
        if score > best_score:
            best_score, best_angle = score, angle
        angle += step
    return round(best_angle, 2)


def cmd_deskew(args):
    angle = estimate_skew(args.input, max_angle=args.max_angle, step=args.step)
    im = _load(args.input).convert("RGB")
    out = im.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    _save(out, args.output)
    print(json.dumps({"ok": True, "angle": angle, "output": str(args.output)}))


def cmd_rotate(args):
    im = _load(args.input).convert("RGB")
    out = im.rotate(args.angle, expand=True, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    _save(out, args.output)
    print(json.dumps({"ok": True, "angle": args.angle,
                      "size": [out.width, out.height], "output": str(args.output)}))


# --- split (two-page spreads) ---------------------------------------------------

def find_gutter(path, scan=0.35):
    """X column with the least ink density in the central band — the fold between
    the two pages of a spread (works for white gutters and for shadowed folds,
    where the clean column sits beside the shadow)."""
    im = _load(path).convert("L")
    ink = im.point(lambda v: 255 if v < 160 else 0)
    w = im.width
    lo, hi = int(w * (1 - scan) / 2), int(w * (1 + scan) / 2)
    band = _profile_sum(ink.crop((lo, 0, hi, im.height)), "cols")
    k = max(3, (hi - lo) // 50) | 1
    smooth = [sum(band[max(0, i - k // 2):i + k // 2 + 1]) / len(band[max(0, i - k // 2):i + k // 2 + 1])
              for i in range(len(band))]
    return lo + smooth.index(min(smooth))


def cmd_split(args):
    gutter = find_gutter(args.input) if args.gutter == "auto" else int(args.gutter)
    im = _load(args.input).convert("RGB")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.input).stem
    suffix = Path(args.input).suffix or ".png"
    written = []
    for side, box in (("left", (0, 0, gutter, im.height)), ("right", (gutter, 0, im.width, im.height))):
        out_path = outdir / f"{stem}_{side}{suffix}"
        im.crop(box).save(out_path)
        written.append(str(out_path))
    print(json.dumps({"ok": True, "gutter": gutter, "pages": written}))


# --- merge (pages -> one PDF) ---------------------------------------------------

def cmd_merge(args):
    pages = [_load(p).convert("RGB") for p in args.inputs]
    if not pages:
        raise SystemExit("no input pages given")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(out, format="PDF", save_all=True, append_images=pages[1:],
                  resolution=float(args.dpi))
    print(json.dumps({"ok": True, "pages": len(pages), "output": str(out)}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ink", help="remove colored-pen handwriting")
    p.add_argument("--in", dest="input", required=True)
    p.add_argument("--out", dest="output", required=True)
    p.add_argument("--hue", choices=("auto", "blue", "red", "green"), default="auto")
    p.add_argument("--tolerance", type=int, default=28,
                   help="channel-dominance threshold; raise to spare faded print colors")
    p.add_argument("--dilate", type=int, default=2, help="mask growth in px")
    p.add_argument("--engine", choices=("auto", "cv2"), default="auto")
    p.set_defaults(func=cmd_ink)

    p = sub.add_parser("erase", help="erase regions from a boxes JSON")
    p.add_argument("--in", dest="input", required=True)
    p.add_argument("--out", dest="output", required=True)
    p.add_argument("--boxes", required=True, help="vision_analyze boxes=true result file")
    p.add_argument("--pad", type=int, default=3, help="grow each box by this many px")
    p.add_argument("--engine", choices=("auto", "cv2"), default="auto")
    p.set_defaults(func=cmd_erase)

    p = sub.add_parser("deskew", help="straighten a photographed page")
    p.add_argument("--in", dest="input", required=True)
    p.add_argument("--out", dest="output", required=True)
    p.add_argument("--max-angle", type=float, default=6.0)
    p.add_argument("--step", type=float, default=0.2)
    p.set_defaults(func=cmd_deskew)

    p = sub.add_parser("rotate", help="rotate by an exact angle (180 for upside-down pages)")
    p.add_argument("--in", dest="input", required=True)
    p.add_argument("--out", dest="output", required=True)
    p.add_argument("--angle", type=float, required=True, help="counter-clockwise degrees")
    p.set_defaults(func=cmd_rotate)

    p = sub.add_parser("split", help="cut a two-page spread at the gutter")
    p.add_argument("--in", dest="input", required=True)
    p.add_argument("--outdir", required=True)
    p.add_argument("--gutter", default="auto", help="'auto' or an explicit X column")
    p.set_defaults(func=cmd_split)

    p = sub.add_parser("merge", help="merge page images into one PDF")
    p.add_argument("inputs", nargs="+")
    p.add_argument("--out", dest="output", required=True)
    p.add_argument("--dpi", type=int, default=200)
    p.set_defaults(func=cmd_merge)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
