"""Tests for vision_analyze grounding mode (``boxes: true``) — prompt contract,
reply parsing, coordinate mapping back onto the original image, and result shaping.

Regression context: cleaning scanned exam pages needs machine-readable regions;
"describe the image" replies cannot drive an erase script. The tool must parse
the vision model's JSON and map 0-1000 normalized boxes onto pre-downscale,
pre-crop image pixels (see ``_convert_normalized_boxes``).
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.vision_tools import (
    VISION_ANALYZE_SCHEMA,
    _build_native_vision_tool_result,
    _convert_normalized_boxes,
    _finalize_boxes_result,
    _grounding_prompt,
    _handle_vision_analyze,
    _parse_boxes_payload,
    vision_analyze_tool,
)

_BOXES_JSON = '[{"label": "ink", "bbox": [100, 200, 300, 400]}]'


def _mock_vision_reply(text):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    return response


# ---------------------------------------------------------------------------
# _grounding_prompt — the wire instruction
# ---------------------------------------------------------------------------


class TestGroundingPrompt:
    def test_states_normalized_space_and_embeds_question(self):
        prompt = _grounding_prompt("find the ink")
        assert "0-1000" in prompt
        assert "JSON array" in prompt
        assert "find the ink" in prompt


# ---------------------------------------------------------------------------
# _parse_boxes_payload — defensive parsing of the vision reply
# ---------------------------------------------------------------------------


class TestParseBoxesPayload:
    def test_bare_array(self):
        assert _parse_boxes_payload(_BOXES_JSON) == [{"label": "ink", "bbox": [100.0, 200.0, 300.0, 400.0]}]

    def test_fenced_array(self):
        text = "Here are the regions:\n```json\n" + _BOXES_JSON + "\n```"
        assert _parse_boxes_payload(text)[0]["label"] == "ink"

    def test_embedded_in_prose(self):
        text = "Sure! " + _BOXES_JSON + " — let me know if you need more."
        assert len(_parse_boxes_payload(text)) == 1

    def test_defaults_missing_label(self):
        assert _parse_boxes_payload('[{"bbox": [1, 2, 3, 4]}]')[0]["label"] == "region"

    def test_empty_array_is_a_valid_nothing_found_reply(self):
        # The locator prompt tells the model to reply [] when nothing matches —
        # that must parse as an empty result, not as a failure.
        assert _parse_boxes_payload("[]") == []
        assert _parse_boxes_payload("```json\n[]\n```") == []

    def test_malformed_shapes_return_none(self):
        assert _parse_boxes_payload("") is None
        assert _parse_boxes_payload("no boxes here") is None
        assert _parse_boxes_payload('{"label": "ink"}') is None  # dict, not array
        assert _parse_boxes_payload('[{"bbox": [1, 2]}]') is None  # wrong arity
        assert _parse_boxes_payload('[{"bbox": "wide"}]') is None  # not numbers
        assert _parse_boxes_payload('[{"bbox": [1, 2, 3, true]}]') is None  # bool is not a number
        # Entries present but every one malformed is still a parse failure.
        assert _parse_boxes_payload('[{"bbox": [1, 2]}, "junk"]') is None


# ---------------------------------------------------------------------------
# _convert_normalized_boxes — 0-1000 space -> original-image pixels
# ---------------------------------------------------------------------------


class TestConvertNormalizedBoxes:
    def test_no_resize_maps_via_seen_size(self):
        boxes = [{"label": "a", "bbox": [0, 0, 500, 1000]}]
        converted, space, size, offset = _convert_normalized_boxes(boxes, None, None, (800, 400))
        assert converted[0]["bbox"] == [0, 0, 400, 400]
        assert size == [800, 400]
        assert offset == [0, 0]
        assert "original-image pixels" in space

    def test_scale_info_restores_presize_pixels(self):
        # Model saw a 1000x500 downscale of a 2000x1000 original.
        boxes = [{"label": "a", "bbox": [500, 500, 600, 600]}]
        scale = {"orig_width": 2000, "orig_height": 1000, "new_width": 1000, "new_height": 500}
        converted, _, size, offset = _convert_normalized_boxes(boxes, scale, None, None)
        assert converted[0]["bbox"] == [1000, 500, 1200, 600]
        assert size == [2000, 1000]
        assert offset == [0, 0]

    def test_crop_offset_shifts_to_full_image_coords(self):
        boxes = [{"label": "a", "bbox": [0, 0, 1000, 1000]}]
        converted, space, size, offset = _convert_normalized_boxes(
            boxes, {"orig_width": 400, "orig_height": 200, "new_width": 400, "new_height": 200},
            {"x": 100, "y": 50, "width": 400, "height": 200}, None)
        assert converted[0]["bbox"] == [100, 50, 500, 250]
        assert offset == [100, 50]
        # The values above already INCLUDE the offset — the space string must say so,
        # not tell consumers to add it again (a double add erases printed content).
        assert "already applied" in space
        assert "full-image pixels" in space

    def test_out_of_range_coordinates_clamp_to_plane(self):
        # Models occasionally emit coords beyond 0-1000; a negative pixel index would
        # wrap to the far side of the image in downstream erase ops.
        boxes = [{"label": "a", "bbox": [-100, 0, 1200, 1000]}]
        converted, _, _, _ = _convert_normalized_boxes(boxes, None, None, (1000, 500))
        assert converted[0]["bbox"] == [0, 0, 1000, 500]

    def test_inverted_bbox_edges_are_sorted(self):
        boxes = [{"label": "a", "bbox": [900, 100, 100, 900]}]
        converted, _, _, _ = _convert_normalized_boxes(boxes, None, None, (1000, 1000))
        x1, y1, x2, y2 = converted[0]["bbox"]
        assert x1 <= x2 and y1 <= y2

    def test_unknowable_plane_passes_boxes_through_normalized(self):
        boxes = [{"label": "a", "bbox": [10, 20, 30, 40]}]
        converted, space, size, offset = _convert_normalized_boxes(boxes, None, None, None)
        assert converted == boxes
        assert size is None
        assert offset == [0, 0]
        assert "normalized" in space


# ---------------------------------------------------------------------------
# _finalize_boxes_result — result shaping
# ---------------------------------------------------------------------------


class TestFinalizeBoxesResult:
    def test_success_result_gains_boxes_keys(self):
        result_json = json.dumps({"success": True, "analysis": _BOXES_JSON})
        captured = {"raw": _BOXES_JSON, "scale_info": None, "crop_offset": None, "seen_size": (1000, 500)}
        result = json.loads(_finalize_boxes_result(result_json, captured))
        # 0-1000 [100, 200, 300, 400] halves on the y axis of a 1000x500 plane.
        assert result["boxes"] == [{"label": "ink", "bbox": [100, 100, 300, 200]}]
        assert result["image_size"] == [1000, 500]
        assert result["offset"] == [0, 0]
        assert "original-image pixels" in result["coordinate_space"]

    def test_unparseable_reply_keeps_analysis_with_hint(self):
        result_json = json.dumps({"success": True, "analysis": "It is a cat."})
        captured = {"raw": "It is a cat.", "scale_info": None, "crop_offset": None, "seen_size": None}
        result = json.loads(_finalize_boxes_result(result_json, captured))
        assert result["boxes_parse_failed"] is True
        assert "It is a cat." in result["analysis"]
        assert "plainer question" in result["analysis"]

    def test_empty_reply_maps_to_empty_boxes_not_failure(self):
        result_json = json.dumps({"success": True, "analysis": "[]"})
        captured = {"raw": "[]", "scale_info": None, "crop_offset": None, "seen_size": (100, 100)}
        result = json.loads(_finalize_boxes_result(result_json, captured))
        assert result["boxes"] == []
        assert "boxes_parse_failed" not in result
        assert result["image_size"] == [100, 100]

    def test_scale_note_dropped_after_mapping(self):
        # _run_analysis prefixes the pre-mapping "[scale note]" — meaningless once
        # boxes are mapped, and misleading to a consumer feeding them to a script.
        result_json = json.dumps({
            "success": True, "analysis": "[Image downscaled from 10x10 to 5x5] " + _BOXES_JSON,
            "scale_note": "Image downscaled from 10x10 to 5x5"})
        captured = {"raw": _BOXES_JSON, "scale_info": None, "crop_offset": None, "seen_size": (1000, 500)}
        result = json.loads(_finalize_boxes_result(result_json, captured))
        assert result["analysis"] == _BOXES_JSON
        assert "scale_note" not in result

    def test_error_result_passes_through_untouched(self):
        result_json = json.dumps({"success": False, "error": "timed out", "analysis": "timed out"})
        assert _finalize_boxes_result(result_json, {"raw": None}) == result_json


# ---------------------------------------------------------------------------
# vision_analyze_tool(boxes=True) — end to end on the aux path
# ---------------------------------------------------------------------------


class TestVisionAnalyzeBoxesEndToEnd:
    @staticmethod
    def _page_png(path):
        from PIL import Image
        Image.new("RGB", (1000, 500), (250, 250, 250)).save(path, format="PNG")

    @pytest.mark.asyncio
    async def test_boxes_parsed_and_mapped_without_double_encoding(self, tmp_path):
        img = tmp_path / "page.png"
        self._page_png(img)
        with (
            patch("tools.vision_tools._image_to_base64_data_url",
                  return_value="data:image/png;base64,abc"),
            patch("tools.vision_tools.async_call_llm",
                  new_callable=AsyncMock, return_value=_mock_vision_reply("```json\n" + _BOXES_JSON + "\n```")) as mock_llm,
        ):
            result = json.loads(await vision_analyze_tool(str(img), "find the ink", "test/model", boxes=True))
        assert result["success"] is True
        # 0-1000 [100, 200, 300, 400] halves on the y axis of the 1000x500 plane.
        assert result["boxes"] == [{"label": "ink", "bbox": [100, 100, 300, 200]}]
        assert result["image_size"] == [1000, 500]
        # The analysis stays the raw model reply — parse results ride in `boxes`, not inside it.
        assert "```" in result["analysis"]
        # The wire prompt was the locator instruction, not the describe-everything wrapper.
        wire_text = mock_llm.await_args.kwargs["messages"][0]["content"][0]["text"]
        assert wire_text.startswith("You are a precise visual locator")
        assert "find the ink" in wire_text

    @pytest.mark.asyncio
    async def test_prose_reply_reports_parse_failure(self, tmp_path):
        img = tmp_path / "page.png"
        self._page_png(img)
        with (
            patch("tools.vision_tools._image_to_base64_data_url",
                  return_value="data:image/png;base64,abc"),
            patch("tools.vision_tools.async_call_llm",
                  new_callable=AsyncMock, return_value=_mock_vision_reply("A page of math exercises.")),
        ):
            result = json.loads(await vision_analyze_tool(str(img), "find the ink", "test/model", boxes=True))
        assert result["boxes_parse_failed"] is True
        assert "boxes" not in result


# ---------------------------------------------------------------------------
# _handle_vision_analyze — boxes flows through both routes
# ---------------------------------------------------------------------------


class TestHandleVisionAnalyzeBoxes:
    @pytest.mark.asyncio
    async def test_aux_route_sends_raw_question_with_boxes_flag(self):
        with (
            patch("tools.vision_tools._should_use_native_vision_fast_path", return_value=False),
            patch("tools.vision_tools.vision_analyze_tool", new_callable=AsyncMock) as mock_tool,
        ):
            await _handle_vision_analyze({"image_url": "img.png", "question": "find ink", "boxes": True})
        args, kwargs = mock_tool.await_args
        assert args[1] == "find ink"  # raw question; wrapper is added at wire time
        assert kwargs["boxes"] is True

    @pytest.mark.asyncio
    async def test_native_route_receives_boxes_flag(self):
        with (
            patch("tools.vision_tools._should_use_native_vision_fast_path", return_value=True),
            patch("tools.vision_tools._vision_analyze_native", new_callable=AsyncMock) as mock_native,
        ):
            await _handle_vision_analyze({"image_url": "img.png", "question": "find ink", "boxes": True})
        assert mock_native.await_args.kwargs["boxes"] is True

    def test_schema_declares_boxes(self):
        assert VISION_ANALYZE_SCHEMA["parameters"]["properties"]["boxes"]["type"] == "boolean"

    def test_native_envelope_carries_output_contract(self):
        envelope = _build_native_vision_tool_result(
            "img.png", "find ink", "data:image/png;base64,abc", 1024, boxes=True)
        text = envelope["content"][0]["text"]
        assert "JSON" in text and "bbox" in text


# ---------------------------------------------------------------------------
# EXIF orientation — one plane for provider, crop, scale info and erase
# ---------------------------------------------------------------------------


def _orientation_tagged_jpeg(path, orientation):
    from PIL import Image
    exif = Image.Exif()
    exif[274] = orientation
    Image.new("RGB", (400, 200), (200, 200, 200)).save(path, format="JPEG", exif=exif)
    return path


class TestExifOrientationBaked:
    def test_tagged_file_rewritten_to_upright_pixels(self, tmp_path):
        from PIL import Image
        from tools.vision_tools_image_prep import _bake_exif_orientation
        tagged = _orientation_tagged_jpeg(tmp_path / "photo.jpg", 6)  # 90° CW display
        out_path, out_mime = _bake_exif_orientation(tagged, "image/jpeg")
        assert out_path != tagged and out_mime == "image/jpeg"
        with Image.open(out_path) as img:
            assert img.size == (200, 400)  # stored plane now equals the display plane
            assert img.getexif().get(274, 1) == 1

    def test_untagged_file_passes_through_without_reencode(self, tmp_path):
        from PIL import Image
        from tools.vision_tools_image_prep import _bake_exif_orientation
        plain = tmp_path / "plain.png"
        Image.new("RGB", (40, 20)).save(plain)
        out_path, _ = _bake_exif_orientation(plain, "image/png")
        assert out_path == plain

    @pytest.mark.asyncio
    async def test_boxes_map_onto_the_display_plane(self, tmp_path):
        """End to end: an EXIF-rotated phone photo must yield boxes in the upright
        plane the provider renders — the same plane any PIL erase consumer sees
        after ``exif_transpose`` (doc-clean's loader does)."""
        tagged = _orientation_tagged_jpeg(tmp_path / "photo.jpg", 6)
        with (
            patch("tools.vision_tools._image_to_base64_data_url",
                  return_value="data:image/jpeg;base64,abc"),
            patch("tools.vision_tools.async_call_llm",
                  new_callable=AsyncMock,
                  return_value=_mock_vision_reply(_BOXES_JSON)),
        ):
            result = json.loads(await vision_analyze_tool(str(tagged), "find ink", "test/model", boxes=True))
        assert result["success"] is True
        assert result["image_size"] == [200, 400]  # upright plane, not the 400x200 stored one
