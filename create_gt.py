#!/usr/bin/env python3
"""Generate OCR drafts only; use gt_editor.py to review and save GroundTruth."""
import argparse
import sys
from pathlib import Path

from helpers.ocr_common import (
    ROOT,
    add_ocr_arguments,
    annotation_paths,
    build_engine,
    config_from_args,
    find_images,
    find_thai_font,
    predict_regions,
    print_config,
    read_image,
    save_framed,
    sha256_file,
    utc_now,
    write_json,
)


def build_draft(path, source_root, output, engine, config, font, font_size, load_seconds):
    relative = path.relative_to(source_root)
    image = read_image(path)
    regions, elapsed = predict_regions(engine, image, config)

    gt_path, preview_path = annotation_paths(output, relative)
    data = {
        f"pos{index}": {
            "text": region["text"],
            "bbox": region["bbox"],
        }
        for index, region in enumerate(regions, 1)
    }

    write_json(gt_path, data)

    draft_report = {
        "status": "draft",
        "source": str(path),
        "image_sha256": sha256_file(path),
        "config": config,
        "model_load_seconds": load_seconds,
        "ocr_seconds": elapsed,
        "created_utc": utc_now(),
        "confidences": {
            f"pos{index}": region["confidence"]
            for index, region in enumerate(regions, 1)
        },
    }

    write_json(gt_path.with_name(gt_path.stem + ".draft.json"), draft_report)
    save_framed(preview_path, image, regions, font, font_size)

    print(f"Draft: {gt_path} ({len(regions)} regions)", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "images")
    parser.add_argument("--output", type=Path, default=ROOT / "GroundTruthDraft")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing OCR drafts")
    add_ocr_arguments(parser)
    args = parser.parse_args()

    config = config_from_args(args)
    args.input = args.input.expanduser().resolve()
    args.output = args.output.expanduser().resolve()

    gt_dir = ROOT / "GroundTruth"
    if args.output == gt_dir or gt_dir in args.output.parents:
        raise ValueError("Draft output cannot be GroundTruth")

    images = find_images(args.input, args.output, recursive=args.recursive)

    if not images:
        raise ValueError("No source images found")

    source_root = args.input if args.input.is_dir() else args.input.parent

    pending = []

    for path in images:
        draft_path, _ = annotation_paths(
            args.output,
            path.relative_to(source_root),
        )

        if args.overwrite or not draft_path.exists():
            pending.append(path)

    if not pending:
        print("All drafts already exist; use --overwrite to regenerate drafts.")
        return 0

    font = find_thai_font(args.font)
    print_config(config)

    engine, load_seconds = build_engine(config)
    failures = []

    for path in pending:
        try:
            build_draft(
                path,
                source_root,
                args.output,
                engine,
                config,
                font,
                args.font_size,
                load_seconds,
            )
        except Exception as error:
            failures.append({"image": str(path), "error": str(error)})
            print(f"Failed: {path}: {error}", file=sys.stderr)

    run_report = {
        "status": "failed" if failures else "completed",
        "config": config,
        "model_load_seconds": load_seconds,
        "processed": len(pending) - len(failures),
        "failures": failures,
    }
    write_json(args.output / "draft_run.json", run_report)

    if failures:
        return 1

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(2)
