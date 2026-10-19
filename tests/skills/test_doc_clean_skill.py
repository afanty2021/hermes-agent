"""Tests for the doc-clean skill: scripts/doc_clean.py primitives and CLI wiring.

Contracts pinned on synthetic images (no network, no fixture photos):
- ``ink_mask`` keys on channel chroma — colored pens caught, printed black text
  and gray pencil spared.
- ``fill_mask`` restores paper tone where strokes were masked.
- ``estimate_skew`` / ``find_gutter`` recover known tilts and fold positions.
- ``load_boxes`` accepts every vision_analyze ``boxes=true`` result shape;
  boxes arrive already mapped to full-image coordinates (offset applied by the
  tool, never added again here).
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

_SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "media" / "doc-clean"
_script = importlib.util.spec_from_file_location(
    "doc_clean", _SKILL_DIR / "scripts" / "doc_clean.py")
doc_clean = importlib.util.module_from_spec(_script)
_script.loader.exec_module(doc_clean)

PAPER = (246, 245, 242)


def _paper(width=300, height=220):
    img = Image.new("RGB", (width, height), PAPER)
    return img, ImageDraw.Draw(img)


def _px(img, x, y):
    return img.getpixel((x, y))


# ---------------------------------------------------------------------------
# ink_mask — chroma gating
# ---------------------------------------------------------------------------


class TestInkMask:
    def _page(self):
        img, draw = _paper()
        draw.rectangle([20, 20, 260, 32], fill=(20, 20, 20))     # printed black text
        draw.rectangle([20, 100, 260, 112], fill=(30, 60, 200))  # blue pen stroke
        draw.rectangle([20, 160, 60, 170], fill=(200, 40, 40))   # red pen stroke
        return img

    def test_auto_catches_pens_and_spares_print(self):
        mask = doc_clean.ink_mask(self._page())
        assert _px(mask, 140, 106) == 255  # blue stroke
        assert _px(mask, 40, 165) == 255   # red stroke
        assert _px(mask, 140, 26) == 0     # printed black text
        assert _px(mask, 290, 10) == 0     # paper

    def test_gray_pencil_is_never_ink(self):
        img, draw = _paper()
        draw.rectangle([20, 100, 260, 112], fill=(110, 110, 110))
        assert _px(doc_clean.ink_mask(img), 140, 106) == 0

    def test_hue_narrows_to_one_pen(self):
        mask = doc_clean.ink_mask(self._page(), hue="blue")
        assert _px(mask, 140, 106) == 255
        assert _px(mask, 40, 165) == 0     # red stroke not selected

    def test_unknown_hue_rejected(self):
        with pytest.raises(ValueError):
            doc_clean.ink_mask(self._page(), hue="purple")


# ---------------------------------------------------------------------------
# fill_mask — paper restoration
# ---------------------------------------------------------------------------


class TestFillMask:
    def test_strokes_fill_back_to_paper(self):
        img, draw = _paper(300, 220)
        draw.rectangle([20, 20, 260, 32], fill=(20, 20, 20))      # printed black text
        draw.rectangle([20, 100, 260, 112], fill=(30, 60, 200))   # blue pen stroke
        mask = doc_clean.ink_mask(img)
        filled = doc_clean.fill_mask(img, mask)
        center = _px(filled, 140, 106)
        assert min(center) > 190, f"stroke center still dark: {center}"
        assert max(abs(a - b) for a, b in zip(center, PAPER)) < 40
        assert _px(filled, 140, 26) == (20, 20, 20)  # untouched pixels keep print

    def test_big_box_fills_without_dark_creep(self):
        img, draw = _paper(300, 220)
        draw.rectangle([100, 60, 200, 160], fill=(40, 40, 190))
        filled = doc_clean.fill_mask(img, doc_clean.ink_mask(img))
        assert min(_px(filled, 150, 110)) > 160


# ---------------------------------------------------------------------------
# estimate_skew / find_gutter — geometry recovery
# ---------------------------------------------------------------------------


class TestGeometry:
    def test_estimate_skew_recovers_known_tilt(self, tmp_path):
        img, draw = _paper(600, 400)
        for y in range(40, 380, 60):
            draw.rectangle([20, y, 580, y + 6], fill=(10, 10, 10))
        path = tmp_path / "tilted.png"
        img.rotate(-3.0, expand=True, fillcolor=(255, 255, 255)).save(path)  # tilt 3° clockwise
        angle = doc_clean.estimate_skew(path, max_angle=6.0, step=0.2)
        assert abs(angle - 3.0) <= 1.0

    def test_find_gutter_lands_in_clean_center(self, tmp_path):
        img, draw = _paper(600, 400)
        draw.rectangle([190, 20, 270, 380], fill=(10, 10, 10))  # page-one text block
        draw.rectangle([330, 20, 410, 380], fill=(10, 10, 10))  # page-two text block
        path = tmp_path / "spread.png"
        img.save(path)
        gutter = doc_clean.find_gutter(path)
        assert 250 <= gutter <= 350

    def test_blank_page_stays_at_zero_degrees(self, tmp_path):
        # Every angle scores 0 on a blank page; the 0.0 score floor must keep the
        # answer at 0° instead of letting the first angle tried (-max) win.
        path = tmp_path / "blank.png"
        _paper(600, 400)[0].save(path)
        assert doc_clean.estimate_skew(path) == 0.0

    def test_split_writes_both_pages(self, tmp_path):
        img, draw = _paper(600, 400)
        draw.rectangle([290, 20, 310, 380], fill=(10, 10, 10))  # dark fold line
        path = tmp_path / "spread.png"
        img.save(path)
        outdir = tmp_path / "pages"
        result = json.loads(subprocess.run(
            [sys.executable, str(_SKILL_DIR / "scripts" / "doc_clean.py"),
             "split", "--in", str(path), "--outdir", str(outdir), "--gutter", "300"],
            capture_output=True, text=True, check=True).stdout)
        assert result["gutter"] == 300
        left, right = (Path(p) for p in result["pages"])
        assert left.exists() and right.exists()
        assert Image.open(left).size == (300, 400)
        assert Image.open(right).size == (300, 400)


# ---------------------------------------------------------------------------
# load_boxes — every vision_analyze boxes=true result shape
# ---------------------------------------------------------------------------


class TestLoadBoxes:
    def test_full_result_dict_coordinates_pass_through(self, tmp_path):
        """The tool already bakes the region offset into the bbox values; the
        result's ``offset`` field is informational — adding it again here would
        erase printed content two offsets away from the real ink."""
        path = tmp_path / "boxes.json"
        path.write_text(json.dumps({
            "boxes": [{"label": "ink", "bbox": [110, 210, 150, 250]}],
            "offset": [100, 200]}), encoding="utf-8")
        assert doc_clean.load_boxes(path) == [[110.0, 210.0, 150.0, 250.0]]

    def test_bare_list_and_bare_object(self, tmp_path):
        bare = tmp_path / "bare.json"
        bare.write_text(json.dumps([{"bbox": [0, 0, 5, 5]}]), encoding="utf-8")
        assert doc_clean.load_boxes(bare) == [[0.0, 0.0, 5.0, 5.0]]
        wrapped = tmp_path / "wrapped.json"
        wrapped.write_text(json.dumps({"boxes": [{"bbox": [1, 1, 2, 2]}]}), encoding="utf-8")
        assert doc_clean.load_boxes(wrapped) == [[1.0, 1.0, 2.0, 2.0]]

    def test_malformed_entries_rejected(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"boxes": [{"bbox": [1, 2]}]}), encoding="utf-8")
        with pytest.raises(ValueError):
            doc_clean.load_boxes(path)


# ---------------------------------------------------------------------------
# merge + CLI wiring
# ---------------------------------------------------------------------------


class TestMergeAndCli:
    def test_merge_writes_multi_page_pdf(self, tmp_path):
        pages = []
        for i in range(2):
            page = tmp_path / f"p{i}.png"
            Image.new("RGB", (200, 100), PAPER).save(page)
            pages.append(page)
        out = tmp_path / "exam.pdf"
        result = json.loads(subprocess.run(
            [sys.executable, str(_SKILL_DIR / "scripts" / "doc_clean.py"),
             "merge", str(pages[0]), str(pages[1]), "--out", str(out)],
            capture_output=True, text=True, check=True).stdout)
        assert result["pages"] == 2
        data = out.read_bytes()
        assert data.startswith(b"%PDF") and len(data) > 1000

    def test_cli_ink_end_to_end(self, tmp_path):
        img, draw = _paper()
        draw.rectangle([20, 100, 260, 112], fill=(30, 60, 200))
        src = tmp_path / "page.jpg"
        img.save(src, format="JPEG")
        out = tmp_path / "clean.png"
        result = json.loads(subprocess.run(
            [sys.executable, str(_SKILL_DIR / "scripts" / "doc_clean.py"),
             "ink", "--in", str(src), "--out", str(out)],
            capture_output=True, text=True, check=True).stdout)
        assert result["ok"] is True and result["ink_pixels"] > 0
        cleaned = Image.open(out).convert("RGB")
        assert min(_px(cleaned, 140, 106)) > 160

    def test_cli_rotate_flips_upside_down_page(self, tmp_path):
        img, draw = _paper(300, 220)
        draw.rectangle([20, 20, 60, 40], fill=(10, 10, 10))  # corner mark, top-left
        src = tmp_path / "upside.png"
        img.save(src)
        out = tmp_path / "right.png"
        result = json.loads(subprocess.run(
            [sys.executable, str(_SKILL_DIR / "scripts" / "doc_clean.py"),
             "rotate", "--in", str(src), "--out", str(out), "--angle", "180"],
            capture_output=True, text=True, check=True).stdout)
        assert result["ok"] is True and result["size"] == [300, 220]
        # 180° maps the [20..60]x[20..40] mark to [239..279]x[179..199]; sample its center.
        assert _px(Image.open(out).convert("RGB"), 259, 189) == (10, 10, 10)
