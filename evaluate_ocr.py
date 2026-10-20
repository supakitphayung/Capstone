#!/usr/bin/env python3
"""Evaluate PP-OCRv5 Mobile against saved ground truth."""
import argparse
import hashlib
import json
import resource
import shutil
import sys
import time
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

from helpers.ocr_common import (ROOT, add_ocr_arguments, annotation_paths, build_engine,
                               config_from_args, describe_config, find_images, find_thai_font,
                               predict_regions, print_config, read_image, read_json,
                               save_framed, sha256_file, utc_now,
                               validate_annotations, validate_config, write_json)
from helpers.ocr_metrics import IOU_THRESHOLD, aggregate_metrics, evaluate_regions


def peak_rss_mb():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024 if sys.platform == "darwin" else 1024)


def freeze_dataset(records, gt_dir, destination):
    """Copy saved GT and original image bytes once for this comparison."""
    destination = Path(destination)
    if destination.exists():
        raise ValueError("A dataset snapshot must use a new directory")
    problems = []
    for record in records:
        gt_path, _ = annotation_paths(gt_dir, record["relative"])
        if not gt_path.is_file():
            problems.append(f"{record['relative']}: no saved GT")
    if problems:
        raise ValueError("Save GT in gt_editor.py before evaluation:\n" + "\n".join(problems))
    if not records:
        raise ValueError("No images with saved GT selected")
    samples = []
    for record in records:
        relative = Path(record["relative"])
        gt_path, _ = annotation_paths(gt_dir, relative)
        frozen_gt, _ = annotation_paths(destination / "GroundTruth", relative)
        frozen_image = destination / "images" / relative
        for source, target in ((record["image_path"], frozen_image), (gt_path, frozen_gt)):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        image = read_image(frozen_image)
        validate_annotations(read_json(frozen_gt), image.shape[1], image.shape[0])
        samples.append({"id": relative.stem, "relative": str(relative),
                        "group": record.get("group", relative.stem), "split": record.get("split", "all"),
                        "image": str(frozen_image.relative_to(destination)),
                        "gt": str(frozen_gt.relative_to(destination)),
                        "image_sha256": sha256_file(frozen_image), "gt_sha256": sha256_file(frozen_gt)})
    digest = hashlib.sha256(json.dumps(samples, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    manifest = {"dataset_id": digest, "created_utc": utc_now(), "samples": samples,
                "iou_threshold": IOU_THRESHOLD, "normalization": "Unicode NFC + strip; internal whitespace preserved"}
    write_json(destination / "manifest.json", manifest)
    return destination / "manifest.json"


def verify_sample(root, sample):
    for name in ("image", "gt"):
        if sha256_file(root / sample[name]) != sample[name + "_sha256"]:
            raise ValueError(f"Frozen {name} changed for {sample['relative']}; start a new comparison")


def run_evaluation(manifest_path, split, config, output, font=None, font_size=None):
    started = time.perf_counter()
    manifest_path, output = Path(manifest_path).resolve(), Path(output).resolve()
    manifest, config = read_json(manifest_path), validate_config(config)
    samples = [sample for sample in manifest["samples"] if split == "all" or sample["split"] == split]
    output.mkdir(parents=True, exist_ok=True)
    report = {"status": "running", "dataset_id": manifest["dataset_id"], "manifest": str(manifest_path),
              "split": split, "config": config, "parameter_details": describe_config(config),
              "expected_images": len(samples), "images": [], "model_load_seconds": None,
              "ocr_seconds": 0.0, "peak_rss_mb": peak_rss_mb(), "created_utc": utc_now()}
    write_json(output / "config.json", config)
    write_json(output / "report.json", report)
    successful = []
    try:
        if not samples:
            raise ValueError(f"No images in split {split}")
        font = find_thai_font(font)
        for sample in samples:
            verify_sample(manifest_path.parent, sample)
        report["versions"] = {name: version(name) for name in ("paddleocr", "paddlepaddle", "opencv-contrib-python")}
        engine, report["model_load_seconds"] = build_engine(config)
        for sample in samples:
            image_started = time.perf_counter()
            try:
                verify_sample(manifest_path.parent, sample)
                image = read_image(manifest_path.parent / sample["image"])
                gt = read_json(manifest_path.parent / sample["gt"])
                ignored = [key for key, value in gt.items() if value["ignore"]]
                detections, elapsed = predict_regions(engine, image, config)
                metrics, annotations = evaluate_regions(gt, detections, ignored)
                framed = Path("framed") / (sample["relative"] + ".evaluation.png")
                save_framed(output / framed, image, annotations, font, font_size)
                item = {"id": sample["id"], "filename": sample["relative"], "status": "completed",
                        "ocr_seconds": elapsed, "scan_time_seconds": elapsed,
                        "metrics": metrics, "detections": detections, "framed_image": str(framed),
                        "elapsed_seconds": time.perf_counter() - image_started}
                report["ocr_seconds"] += elapsed
                successful.append(metrics)
                print(f"{sample['relative']}: e2e F1={metrics['end_to_end']['f1']:.4f}, CER={metrics['matched_cer']}", flush=True)
            except Exception as error:
                item = {"id": sample["id"], "filename": sample["relative"], "status": "failed", "error": str(error)}
            report["images"].append(item)
            write_json(output / "images" / (sample["relative"] + ".json"), item)
            report["peak_rss_mb"] = peak_rss_mb()
            write_json(output / "report.json", report)
        report["status"] = "completed" if len(successful) == len(samples) else "failed"
    except Exception as error:
        report.update(status="failed", error=str(error))
    report["metrics"] = aggregate_metrics(successful)
    report["completed_images"] = len(successful)
    report["peak_rss_mb"] = peak_rss_mb()
    report["elapsed_seconds"] = time.perf_counter() - started
    write_json(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "images")
    parser.add_argument("--gt", type=Path, default=ROOT / "GroundTruth")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation_output")
    parser.add_argument("--ids", nargs="+", help="Optional image stems (e.g. 1 2 3 4 8 9)")
    add_ocr_arguments(parser)
    args = parser.parse_args()
    config = config_from_args(args)
    source = args.input.expanduser().resolve()
    images = find_images(source, recursive=True)
    source_root = source if source.is_dir() else source.parent
    if args.ids:
        missing = set(args.ids) - {path.stem for path in images}
        if missing:
            raise ValueError(f"Unknown image IDs: {sorted(missing)}")
        images = [path for path in images if path.stem in args.ids]
    records, skipped = [], []
    for path in images:
        relative = path.relative_to(source_root)
        gt, _ = annotation_paths(args.gt, relative)
        if not gt.is_file():
            skipped.append({"image": str(relative), "reason": "no saved GT"})
        else:
            records.append({"relative": str(relative), "image_path": path})
    if not records:
        raise ValueError(f"No saved GT found in {args.gt}. Open gt_editor.py and click 'บันทึก'.")
    run_dir = args.output.resolve() / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    manifest = freeze_dataset(records, args.gt, run_dir / "dataset")
    write_json(run_dir / "skipped.json", skipped)
    print_config(config)
    report = run_evaluation(manifest, "all", config, run_dir / "evaluation", args.font, args.font_size)
    print(f"Results: {run_dir}; skipped images without GT: {len(skipped)}")
    if report.get("error"):
        print(report["error"], file=sys.stderr)
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(2)
