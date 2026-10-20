#!/usr/bin/env python3
"""Run isolated PP-OCRv5 Mobile parameter trials on a frozen saved GT dataset."""
import argparse
import math
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from evaluate_ocr import freeze_dataset, run_evaluation
from helpers.ocr_common import (BASELINE, ROOT, print_config, read_json,
                               utc_now, validate_config, write_json)
from helpers.ocr_metrics import ranking_key

SWEEP = {
    "text_det_limit_side_len": [1280, 1920],
    "text_det_thresh": [0.2, 0.4],
    "text_det_box_thresh": [0.3, 0.5],
    "text_det_unclip_ratio": [2.0, 2.5],
}


def automatic_trials():
    trials = [{"name": "baseline", "config": validate_config()}]
    for key, values in SWEEP.items():
        for value in values:
            trials.append({"name": f"{key}-{value}", "config": validate_config({key: value})})
    return trials


def load_trials(path):
    payload = read_json(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("experiments"), list) or not payload["experiments"]:
        raise ValueError('Expected {"experiments": [{"name": "...", "parameters": {...}}]}')
    names, trials = set(), []
    for entry in payload["experiments"]:
        if not isinstance(entry, dict):
            raise ValueError("Each experiment must be an object with name and parameters")
        name = entry.get("name", "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", name) or name in names:
            raise ValueError(f"Invalid or duplicate trial name: {name!r}")
        if set(entry) - {"name", "parameters"}:
            raise ValueError(f"Unexpected fields in trial {name}")
        names.add(name)
        trials.append({"name": name, "config": validate_config(entry.get("parameters", {}))})
    return trials


def load_records(split_file, images_dir, tune_only=False):
    payload = read_json(split_file)
    samples = payload.get("samples", [])
    if not samples:
        raise ValueError("Dataset split has no samples")
    groups, ids, files, records = {}, set(), set(), []
    images_dir = Path(images_dir).resolve()
    for sample in samples:
        key, group, split, relative = sample["id"], sample["group"], sample["split"], Path(sample["file"])
        if split not in ("tune", "holdout"):
            raise ValueError(f"Invalid split: {split}")
        if key in ids or str(relative) in files:
            raise ValueError("Duplicate sample ID or image in split")
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Split filenames must be relative to the images folder")
        if group in groups and groups[group] != split:
            raise ValueError(f"Product group {group} leaks between tune and holdout")
        groups[group] = split
        # IDs are explicit to avoid accidental renaming changing the split.
        if relative.stem != str(key):
            raise ValueError(f"Sample ID {key} does not match {relative}")
        ids.add(key)
        files.add(str(relative))
        if tune_only and split == "holdout":
            continue
        image = images_dir / relative
        if not image.is_file():
            raise FileNotFoundError(image)
        records.append({"image_path": image, "relative": str(relative), "group": group, "split": split})
    if not any(record["split"] == "tune" for record in records):
        raise ValueError("Dataset needs tuning images")
    if not tune_only and not any(record["split"] == "holdout" for record in records):
        raise ValueError("Dataset needs holdout images, or use --tune-only")
    return records


def run_trial(trial, manifest_path, split, output, timeout=1800, font=None, font_size=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = read_json(manifest_path)
    expected = sum(split == "all" or sample["split"] == split for sample in manifest["samples"])
    job = {"manifest": str(Path(manifest_path).resolve()), "split": split,
           "config": trial["config"], "output": str(output),
           "font": str(font) if font else None, "font_size": font_size}
    write_json(output / "job.json", job)
    print(f"\nTrial {trial['name']} ({split})", flush=True)
    print_config(trial["config"])
    report = {"status": "failed", "config": trial["config"], "dataset_id": manifest["dataset_id"], "split": split}
    try:
        with (output / "worker.log").open("w", encoding="utf-8") as log:
            completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(output / "job.json")],
                                       stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        if (output / "report.json").exists():
            report = read_json(output / "report.json")
        valid = (completed.returncode == 0 and report.get("status") == "completed"
                 and report.get("dataset_id") == manifest["dataset_id"]
                 and report.get("config") == trial["config"] and report.get("split") == split
                 and report.get("expected_images") == expected and report.get("completed_images") == expected
                 and len(report.get("images", [])) == expected and expected > 0
                 and all(item.get("status") == "completed" for item in report.get("images", [])))
        report["returncode"] = completed.returncode
        if not valid:
            report.update(status="failed", error=report.get("error", "Worker did not complete the entire requested dataset"))
    except subprocess.TimeoutExpired:
        report.update(status="failed", error=f"Worker timed out after {timeout} seconds")
    except (OSError, ValueError, KeyError) as error:
        report.update(status="failed", error=str(error))
    report.update(name=trial["name"], output=str(output))
    write_json(output / "report.json", report)
    print(f"Trial {trial['name']}: {report['status']}", flush=True)
    return report


def combined_trial(reports):
    """Combine the winning one-factor values, using tuning results exclusively."""
    completed = [report for report in reports if report["status"] == "completed" and report.get("split") == "tune"]
    baseline = next((report for report in completed if report["config"] == BASELINE), None)
    if baseline is None:
        return None
    combined = dict(BASELINE)
    for key in SWEEP:
        candidates = [report for report in completed if all(
            report["config"][other] == BASELINE[other] for other in BASELINE if other != key)]
        winner = min(candidates, key=ranking_key)
        combined[key] = winner["config"][key]
    if any(report["config"] == combined for report in reports):
        return None
    return {"name": "combined-winners", "config": validate_config(combined)}


def choose_best(reports):
    completed = [report for report in reports if report["status"] == "completed" and report.get("split") == "tune"]
    return min(completed, key=ranking_key) if completed else None


def write_comparison(run_dir, summary):
    write_json(run_dir / "comparison.json", summary)
    lines = [f"Dataset: {summary['dataset_id']}",
             "Selection: tuning end-to-end F1 (descending), matched CER, OCR seconds, peak RSS (ascending).",
             "", "| Trial | Status | E2E F1 | Detection F1 | Matched CER | Accuracy % | OCR s | Peak RSS MB |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for report in summary["trials"]:
        if report["status"] != "completed":
            lines.append(f"| {report['name']} | failed | — | — | — | — | — | — |")
            continue
        metrics = report["metrics"]
        cer = "n/a" if metrics["matched_cer"] is None else f"{metrics['matched_cer']:.4f}"
        lines.append(f"| {report['name']} | completed | {metrics['end_to_end']['f1']:.4f} | "
                     f"{metrics['detection']['f1']:.4f} | {cer} | {metrics['accuracy_percent']:.2f} | "
                     f"{report['ocr_seconds']:.3f} | {report['peak_rss_mb']:.1f} |")
    lines.extend(["", f"Selected using tune only: {summary.get('best_trial') or 'none'}"])
    holdout = summary.get("holdout")
    if holdout:
        lines.extend(["", f"Holdout status: {holdout['status']} (never used for selection)."])
        if holdout["status"] == "completed":
            lines.append(f"Holdout E2E F1: {holdout['metrics']['end_to_end']['f1']:.4f}; matched CER: {holdout['metrics']['matched_cer']}")
    (run_dir / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def worker(job_path):
    job = read_json(job_path)
    report = run_evaluation(job["manifest"], job["split"], job["config"], job["output"], job.get("font"), job.get("font_size"))
    return 0 if report["status"] == "completed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "images")
    parser.add_argument("--gt", type=Path, default=ROOT / "GroundTruth")
    parser.add_argument("--split-file", type=Path, default=ROOT / "experiments/dataset_split.json")
    parser.add_argument("--experiments", type=Path, help="JSON with one or more named parameter sets; otherwise use the 9-trial sweep")
    parser.add_argument("--output", type=Path, default=ROOT / "experiment_output")
    parser.add_argument("--timeout", type=float, default=1800, help="Seconds per isolated trial")
    parser.add_argument("--tune-only", action="store_true", help="Do not run holdout or require its GT yet")
    parser.add_argument("--no-combine", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Explain actual settings without loading OCR or requiring GT")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--font-size", type=int)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker)
    if not math.isfinite(args.timeout) or args.timeout <= 0 or (args.font_size is not None and args.font_size <= 0):
        raise ValueError("Timeout and font size must be positive")
    trials = load_trials(args.experiments) if args.experiments else automatic_trials()
    records = load_records(args.split_file, args.input, args.tune_only)
    if args.dry_run:
        print(f"{len(trials)} initial trials; images: {[record['relative'] for record in records]}")
        for trial in trials:
            print(f"\n{trial['name']}")
            print_config(trial["config"])
        return 0
    run_dir = args.output.resolve() / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    manifest_path = freeze_dataset(records, args.gt, run_dir / "dataset")
    # Store the split and requested trial settings alongside the exact GT copy.
    write_json(run_dir / "requested_trials.json", trials)
    write_json(run_dir / "dataset_split.json", read_json(args.split_file))
    summary = {"status": "running", "dataset_id": read_json(manifest_path)["dataset_id"],
               "manifest": str(manifest_path), "created_utc": utc_now(), "trials": [],
               "best_trial": None, "holdout": None}
    write_comparison(run_dir, summary)
    for trial in trials:
        report = run_trial(trial, manifest_path, "tune", run_dir / "trials" / trial["name"], args.timeout, args.font, args.font_size)
        summary["trials"].append(report)
        write_comparison(run_dir, summary)
    if not args.experiments and not args.no_combine:
        combined = combined_trial(summary["trials"])
        if combined:
            summary["trials"].append(run_trial(combined, manifest_path, "tune", run_dir / "trials" / combined["name"],
                                                args.timeout, args.font, args.font_size))
    best = choose_best(summary["trials"])
    summary["best_trial"] = best["name"] if best else None
    # Persist the selection before accessing any holdout score.
    if best:
        write_json(run_dir / "selected_config.json", best["config"])
    write_comparison(run_dir, summary)
    if best and not args.tune_only:
        summary["holdout"] = run_trial({"name": best["name"], "config": best["config"]}, manifest_path, "holdout",
                                       run_dir / "holdout", args.timeout, args.font, args.font_size)
    failed = any(report["status"] != "completed" for report in summary["trials"])
    failed = failed or bool(summary["holdout"] and summary["holdout"]["status"] != "completed")
    summary["status"] = "failed" if not best else "completed_with_errors" if failed else "completed"
    write_comparison(run_dir, summary)
    print(f"Results: {run_dir}; best tuning trial: {summary['best_trial']}")
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(2)
