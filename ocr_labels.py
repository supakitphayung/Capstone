#!/usr/bin/env python3
"""Frame detected text with OpenCV and log Thai/English PaddleOCR as JSON."""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
LOGGER = logging.getLogger("label_ocr")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).parent,
                        help="Image file or folder (default: this script's folder)")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "ocr_output",
                        help="Output folder; each run gets a separate subfolder")
    parser.add_argument("--recursive", action="store_true", help="Scan nested folders")
    parser.add_argument("--min-confidence", type=float, default=0.5,
                        help="Keep text at or above this confidence (default: 0.5)")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="Resize before OCR; boxes are mapped back to the original image")
    parser.add_argument("--roi", type=int, nargs=4, metavar=("X", "Y", "WIDTH", "HEIGHT"),
                        help="Only scan this rectangle, in original-image pixels")
    parser.add_argument("--det-max-side", type=int, default=2560,
                        help="Maximum detection image side length (default: 2560)")
    parser.add_argument("--cpu-threads", type=int, default=4)
    parser.add_argument("--font", type=Path,
                        help="Thai/English TrueType or OpenType font; detected automatically by default")
    parser.add_argument("--font-size", type=int,
                        help="OCR label font size in pixels (default: based on image width)")
    args = parser.parse_args()
    if not 0 <= args.min_confidence <= 1:
        parser.error("--min-confidence must be between 0 and 1")
    if args.scale <= 0 or args.det_max_side <= 0 or args.cpu_threads <= 0:
        parser.error("--scale, --det-max-side and --cpu-threads must be positive")
    if args.roi and (min(args.roi[:2]) < 0 or min(args.roi[2:]) <= 0):
        parser.error("--roi needs nonnegative X/Y and positive WIDTH/HEIGHT")
    if args.font_size is not None and args.font_size <= 0:
        parser.error("--font-size must be positive")
    return args


def write_json(path, data):
    # Preserve readable Thai characters instead of escaping them as \uXXXX.
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
                         + "\n", encoding="utf-8")
    temporary.replace(path)


def languages_in(text):
    """Identify scripts in the transcription, rather than ask OCR to detect language."""
    languages = []
    if re.search(r"[\u0e00-\u0e7f]", text):
        languages.append("th")
    if re.search(r"[A-Za-z]", text):
        languages.append("en")
    return languages


def find_images(source, output, cache, recursive):
    if source.is_file():
        if source.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported image format: {source.suffix}")
        return [source]
    if not source.is_dir():
        raise FileNotFoundError(f"Input does not exist: {source}")
    candidates = source.rglob("*") if recursive else source.iterdir()
    return sorted(p for p in candidates
                  if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
                  and not any(p.is_relative_to(excluded)
                              for excluded in (output, cache, Path(__file__).parent / ".venv")))


def read_image(path, cv2, np):
    # imdecode handles paths containing Thai characters consistently.
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Cannot decode image: {path}")
    if image.dtype != np.uint8:
        raise ValueError("Only 8-bit images are supported; convert this image before scanning")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        # Composite transparency onto white so label backgrounds remain readable.
        alpha = image[:, :, 3:4].astype(np.float32) / 255
        return np.rint(image[:, :, :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)
    return image


def find_thai_font(requested=None):
    if requested is not None:
        font = requested.expanduser().resolve()
        if not font.is_file():
            raise FileNotFoundError(f"Font does not exist: {font}")
        return font
    candidates = [
        Path(__file__).parent / "fonts" / "NotoSansThai-Regular.ttf",
        Path("/System/Library/Fonts/Supplemental/Thonburi.ttc"),
        Path("/System/Library/Fonts/ThonburiUI.ttc"),
        Path.home() / "Library/Fonts/THSarabunNew.ttf",
        Path("C:/Windows/Fonts/tahoma.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
        Path("/usr/share/fonts/truetype/tlwg/Garuda.ttf"),
    ]
    for font in candidates:
        if font.is_file():
            return font
    raise FileNotFoundError("No Thai font found. Supply --font /path/to/a/Thai-font.ttf")


def frame_regions(image, regions, font_path, font_size, cv2, np, roi=None):
    """Draw polygons with OpenCV and real Thai/English labels with Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    height, width = image.shape[:2]
    framed = image.copy()
    thickness = max(1, round(max(width, height) / 1000))
    for index, region in enumerate(regions, 1):
        region["id"] = index
        color = (0, 150, 0) if region["confidence"] >= 0.8 else (0, 130, 255)
        cv2.polylines(framed, [np.array(region["polygon"], dtype=np.int32)], True,
                      color, thickness, cv2.LINE_AA)
    if roi:
        x, y, roi_width, roi_height = roi
        cv2.rectangle(framed, (x, y), (x + roi_width - 1, y + roi_height - 1),
                      (255, 100, 0), thickness)
    canvas = Image.fromarray(cv2.cvtColor(framed, cv2.COLOR_BGR2RGB)).convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    base_size = font_size or max(16, min(32, round(width / 60)))
    fonts = {}
    occupied = []
    padding = 3
    for region in regions:
        label = f"{region['id']}: {region['text']} ({region['confidence']:.2f})"
        size = base_size
        while True:
            if size not in fonts:
                fonts[size] = ImageFont.truetype(str(font_path), size=size)
            font = fonts[size]
            bounds = draw.textbbox((0, 0), label, font=font)
            label_width = bounds[2] - bounds[0] + 2 * padding
            label_height = bounds[3] - bounds[1] + 2 * padding
            if label_width <= width or size == 1:
                break
            size -= 1
        left, top, _, bottom = region["bbox"]
        label_x = max(0, min(left, width - label_width))
        # Prefer above the detection; shift labels if they collide with earlier labels.
        candidates = [top - label_height - 2, bottom + 2, top]
        candidates.extend(top - (step + 1) * (label_height + 2) for step in range(1, 5))
        def position_cost(label_y):
            overlap = sum(max(0, min(label_x + label_width, r) - max(label_x, l))
                          * max(0, min(label_y + label_height, b) - max(label_y, t))
                          for l, t, r, b in occupied)
            return overlap, abs(label_y - (top - label_height - 2))
        candidates = [max(0, min(candidate, height - label_height)) for candidate in candidates]
        label_y = min(candidates, key=position_cost)
        rectangle = (label_x, label_y, label_x + label_width, label_y + label_height)
        occupied.append(rectangle)
        color = (0, 125, 0, 255) if region["confidence"] >= 0.8 else (190, 85, 0, 255)
        draw.rectangle(rectangle, fill=(255, 255, 255, 235), outline=color)
        # Offset by the glyph bounds so Thai vowels and tone marks are not clipped.
        draw.text((label_x + padding - bounds[0], label_y + padding - bounds[1]),
                  label, font=font, fill=color)
    canvas = Image.alpha_composite(canvas, overlay).convert("RGB")
    return cv2.cvtColor(np.asarray(canvas), cv2.COLOR_RGB2BGR)


def scan_image(path, relative, engine, args, run_dir, cv2, np):
    started = time.perf_counter()
    image = read_image(path, cv2, np)
    height, width = image.shape[:2]
    x, y, roi_width, roi_height = args.roi or (0, 0, width, height)
    if x + roi_width > width or y + roi_height > height:
        raise ValueError(f"ROI exceeds image dimensions {width} x {height}")
    cropped = image[y:y + roi_height, x:x + roi_width]
    scan_width = max(1, round(roi_width * args.scale))
    scan_height = max(1, round(roi_height * args.scale))
    scan = cv2.resize(cropped, (scan_width, scan_height),
                      interpolation=cv2.INTER_CUBIC if args.scale > 1 else cv2.INTER_AREA)
    results = engine.predict(scan)
    if len(results) != 1:
        raise RuntimeError(f"Expected one image result, received {len(results)}")
    result = results[0]
    texts = result["rec_texts"]
    scores = result["rec_scores"]
    polygons = result["rec_polys"]
    if not len(texts) == len(scores) == len(polygons):
        raise RuntimeError("PaddleOCR returned mismatched text, score and polygon counts")
    regions = []
    for text, score, polygon in zip(texts, scores, polygons):
        confidence = float(score)
        if not text.strip() or not np.isfinite(confidence) or confidence < args.min_confidence:
            continue
        points = np.asarray(polygon, dtype=np.float64).copy()
        points[:, 0] = np.clip(points[:, 0] * roi_width / scan_width + x, 0, width - 1)
        points[:, 1] = np.clip(points[:, 1] * roi_height / scan_height + y, 0, height - 1)
        points = np.rint(points).astype(np.int32)
        regions.append({
            "text": str(text), "confidence": confidence,
            "languages": languages_in(text), "polygon": points.tolist(),
            "bbox": [int(points[:, 0].min()), int(points[:, 1].min()),
                     int(points[:, 0].max()), int(points[:, 1].max())],
        })
    # Approximate top-to-bottom order; complex multi-column layouts may need review.
    regions.sort(key=lambda region: (region["bbox"][1], region["bbox"][0]))
    framed = frame_regions(image, regions, args.font, args.font_size, cv2, np, args.roi)
    # Include the original extension to avoid collisions between e.g. label.png/label.jpg.
    framed_relative = Path("framed") / relative.parent / (relative.name + ".framed.png")
    json_relative = Path("json") / relative.parent / (relative.name + ".json")
    framed_path = run_dir / framed_relative
    json_path = run_dir / json_relative
    framed_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", framed)
    if not ok:
        raise RuntimeError("OpenCV could not encode the framed image")
    encoded.tofile(framed_path)
    record = {
        "source": str(path), "filename": str(relative),
        "status": "success" if regions else "no_text",
        "image": {"width": width, "height": height},
        "roi": [x, y, roi_width, roi_height], "ocr_scale": args.scale,
        "languages": ["th", "en"], "coordinate_system": "original_image_pixels",
        "bbox_format": "[left, top, right, bottom]",
        "region_count": len(regions), "text": "\n".join(r["text"] for r in regions),
        "regions": regions, "framed_image": str(framed_relative),
        "text_rendering": {"font": str(args.font), "font_size": args.font_size,
                           "layout": "text_labels_on_original_image"},
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(json_path, record)
    return {"filename": str(relative), "status": record["status"],
            "region_count": len(regions), "json": str(json_relative),
            "framed_image": str(framed_relative)}


def main():
    args = parse_args()
    args.input = args.input.expanduser().resolve()
    args.output = args.output.expanduser().resolve()
    cache = Path(__file__).resolve().parent / ".ocr_cache"
    images = find_images(args.input, args.output, cache, args.recursive)
    if not images:
        raise ValueError(f"No images found in {args.input}")
    run_dir = args.output / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir.mkdir(parents=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(),
                                  logging.FileHandler(run_dir / "run.log", encoding="utf-8")])
    # Keep downloaded models and library caches in the project folder.
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(cache / "paddlex"))
    os.environ.setdefault("PADDLE_HOME", str(cache / "paddle"))
    os.environ.setdefault("HF_HOME", str(cache / "huggingface"))
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")
    summary = {"status": "running", "input": str(args.input),
               "languages": ["th", "en"], "ocr_version": "PP-OCRv5",
               "min_confidence": args.min_confidence, "files": []}
    summary_path = run_dir / "run.json"
    write_json(summary_path, summary)
    try:
        import cv2
        import numpy as np
        from paddleocr import PaddleOCR

        args.font = find_thai_font(args.font)
        LOGGER.info("OCR text font: %s", args.font)
        summary["versions"] = {name: version(name) for name in
                               ("paddleocr", "paddlepaddle", "opencv-contrib-python")}
        LOGGER.info("Loading Thai/English OCR; first run downloads model weights")
        engine = PaddleOCR(
            lang="th", ocr_version="PP-OCRv5", device="cpu",
            use_doc_orientation_classify=False, use_doc_unwarping=False,
            use_textline_orientation=False, enable_mkldnn=False,
            cpu_threads=args.cpu_threads, text_rec_score_thresh=0.0,
            text_det_limit_type="max", text_det_limit_side_len=args.det_max_side,
        )
        source_root = args.input if args.input.is_dir() else args.input.parent
        for index, path in enumerate(images, 1):
            relative = path.relative_to(source_root)
            LOGGER.info("[%d/%d] Scanning %s", index, len(images), relative)
            try:
                item = scan_image(path, relative, engine, args, run_dir, cv2, np)
                LOGGER.info("Saved %d text regions", item["region_count"])
            except Exception as error:
                LOGGER.exception("Failed to scan %s", relative)
                item = {"filename": str(relative), "source": str(path),
                        "status": "error", "error": str(error)}
                error_path = run_dir / "json" / relative.parent / (relative.name + ".json")
                error_path.parent.mkdir(parents=True, exist_ok=True)
                write_json(error_path, item)
                item["json"] = str(error_path.relative_to(run_dir))
            summary["files"].append(item)
            write_json(summary_path, summary)
        summary["failed"] = sum(item["status"] == "error" for item in summary["files"])
        summary["processed"] = len(images) - summary["failed"]
        summary["status"] = "completed" if not summary["failed"] else "completed_with_errors"
    except Exception as error:
        LOGGER.exception("OCR could not start")
        summary.update(status="error", error=str(error))
    write_json(summary_path, summary)
    LOGGER.info("Results: %s", run_dir)
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(2)
