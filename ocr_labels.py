#!/usr/bin/env python3
"""Read Thai/English labels with PP-OCRv5 Mobile and save framed images and JSON."""
import argparse
import logging
import sys
import time
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

from helpers.ocr_common import (CACHE, ROOT, TEXT_DETECTION_MODEL, TEXT_RECOGNITION_MODEL,
                               add_ocr_arguments, build_engine, config_from_args, find_images,
                               find_thai_font, frame_regions, languages_in, predict_regions,
                               print_config, read_image, save_framed, utc_now, write_json)

LOGGER = logging.getLogger("label_ocr")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "images")
    parser.add_argument("--output", type=Path, default=ROOT / "ocr_output")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--min-confidence", type=float, default=None,
                        help="Optional display/output filter; default uses shared rec-score-thresh (0)")
    parser.add_argument("--roi", type=int, nargs=4, metavar=("X", "Y", "WIDTH", "HEIGHT"))
    add_ocr_arguments(parser)
    args = parser.parse_args()
    if args.min_confidence is not None and not 0 <= args.min_confidence <= 1:
        parser.error("--min-confidence must be between 0 and 1")
    return args


def scan_image(path, relative, engine, args, run_dir, config):
    started = time.perf_counter()
    image = read_image(path)
    height, width = image.shape[:2]
    regions, response_seconds = predict_regions(engine, image, config, args.roi, args.min_confidence)
    framed_relative = Path("framed") / relative.parent / (relative.name + ".framed.png")
    json_relative = Path("json") / relative.parent / (relative.name + ".json")
    save_framed(run_dir / framed_relative, image, regions, args.font, args.font_size, roi=args.roi)
    record = {
        "source": str(path), "filename": str(relative),
        "status": "success" if regions else "no_text", "image": {"width": width, "height": height},
        "roi": args.roi or [0, 0, width, height], "ocr_scale": config["scale"],
        "languages": ["th", "en"], "coordinate_system": "original_image_pixels",
        "bbox_format": "[left, top, right, bottom]", "config": config,
        "region_count": len(regions), "text": "\n".join(region["text"] for region in regions),
        "regions": regions, "framed_image": str(framed_relative),
        "text_rendering": {"font": str(args.font), "font_size": args.font_size,
                           "layout": "text_labels_on_original_image"},
        "elapsed_seconds": time.perf_counter() - started,
        "response_time_seconds": response_seconds, "timestamp_utc": utc_now(),
    }
    write_json(run_dir / json_relative, record)
    return {key: record[key] for key in ("filename", "status", "region_count", "framed_image",
                                         "response_time_seconds", "elapsed_seconds")} | {"json": str(json_relative)}


def main():
    started = time.perf_counter()
    args = parse_args()
    config = config_from_args(args)
    args.input = args.input.expanduser().resolve()
    args.output = args.output.expanduser().resolve()
    images = find_images(args.input, args.output, CACHE, args.recursive)
    if not images:
        raise ValueError(f"No images found in {args.input}")
    args.font = find_thai_font(args.font)
    run_dir = args.output / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir.mkdir(parents=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(run_dir / "run.log", encoding="utf-8")])
    summary = {"status": "running", "input": str(args.input), "config": config, "files": [],
               "languages": ["th", "en"], "ocr_version": f"{TEXT_DETECTION_MODEL} + {TEXT_RECOGNITION_MODEL}",
               "min_confidence": args.min_confidence}
    write_json(run_dir / "run.json", summary)
    print_config(config)
    try:
        summary["versions"] = {name: version(name) for name in ("paddleocr", "paddlepaddle", "opencv-contrib-python")}
        engine, summary["model_load_seconds"] = build_engine(config)
        source_root = args.input if args.input.is_dir() else args.input.parent
        for path in images:
            relative = path.relative_to(source_root)
            image_started = time.perf_counter()
            try:
                LOGGER.info("Scanning %s", relative)
                item = scan_image(path, relative, engine, args, run_dir, config)
            except Exception as error:
                LOGGER.exception("Failed to scan %s", relative)
                item = {"filename": str(relative), "status": "error", "error": str(error),
                        "response_time_seconds": None, "elapsed_seconds": time.perf_counter() - image_started}
                write_json(run_dir / "json" / relative.parent / (relative.name + ".json"), item)
            summary["files"].append(item)
            write_json(run_dir / "run.json", summary)
        summary["failed"] = sum(item["status"] == "error" for item in summary["files"])
        summary["processed"] = len(images) - summary["failed"]
        summary["status"] = "completed" if not summary["failed"] else "completed_with_errors"
    except Exception as error:
        LOGGER.exception("OCR could not start")
        summary.update(status="error", error=str(error))
    summary["response_time_seconds"] = time.perf_counter() - started
    write_json(run_dir / "run.json", summary)
    LOGGER.info("Results: %s", run_dir)
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(2)
