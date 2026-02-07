# Documentation Improvements Analysis

Based on the comparison between `docs/API.md` and `app/schemas/`, the following discrepancies were found and need to be corrected:

## 1. Response Structure
**Issue:** The documentation states valid responses are wrapped in `{"success": true, "data": ...}`.
**Actual:** The API returns Pydantic models directly (e.g., `TaskResponse`, `UserResponse`), without the wrapper.
**Fix:** Remove the wrapper from all successful response examples in `API.md`.

## 2. /tasks/video-overlay
**Issue:** Documentation shows flat/incorrect nesting for positioning.
**Actual:** `VideoOverlayRequest` expects:
```json
{
  "base_video_file_id": ...,
  "overlay_video_file_id": ...,
  "config": {
    "x": 10, "y": 10, "width": ..., "height": ..., "shape": "rectangle", ...
  },
  "border": { ... },
  "shadow": { ... }
}
```
**Fix:** Update request body example to match `VideoOverlayRequest`.

## 3. /tasks/audio-overlay
**Issue:** Parameter name mismatches.
**Actual:** `AudioOverlayRequest` uses:
- `offset` instead of `start_offset`
- `overlay_volume` instead of `mix_volume`
- `original_volume` (new field)
**Fix:** Update parameter names and include `original_volume`.

## 4. /tasks/text-overlay
**Issue:** Style object structure mismatch.
**Actual:** `TextStyle` uses `font_family`, `font_size`, `color` directly, not inside a `font` sub-object.
```json
"style": {
  "font_family": "Arial",
  "font_size": 24,
  "color": "#FFFFFF"
}
```
**Fix:** Flatten the `font` object inside `style` in the documentation.

## 5. /tasks/subtitles
**Issue:** Mostly correct, but double check `subtitle_text` item fields.
**Actual:** `start`, `end`, `text` are correct.
**Fix:** Ensure example reflects list of dicts.

## 6. Detailed Descriptions
**Issue:** Missing detailed constraints (e.g. min/max values).
**Fix:** Add descriptions from Pydantic `Field` arguments (e.g. `ge=0`, `le=1.0` for opacity).
