"""Adapters to the existing CLI and its shared, model-free configuration."""
import shlex
from pathlib import Path

from .config import Settings
from .schemas import JobRequest
from experiment_ocr import automatic_trials, load_records
from helpers.ocr_common import BASELINE, IMAGE_EXTENSIONS, PARAMETER_HELP, annotation_paths, validate_config, write_json

SCRIPTS = {
    "create_gt": {"title": "สร้าง Draft", "file": "create_gt.py", "step": 1},
    "gt_editor": {"title": "ตรวจแก้ Ground Truth", "file": "gt_editor.py", "step": 2},
    "evaluate_ocr": {"title": "ประเมิน OCR", "file": "evaluate_ocr.py", "step": 3},
    "experiment_ocr": {"title": "ทดลอง Parameter", "file": "experiment_ocr.py", "step": 4},
}


def catalog():
    return {"scripts": [{"id": key, **value} for key, value in SCRIPTS.items()],
            "baseline": BASELINE, "parameter_help": PARAMETER_HELP,
            "automatic_trials": automatic_trials()}


def dataset(settings: Settings):
    folder = settings.root / "images"
    images = []
    if folder.is_dir():
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS or not path.resolve().is_relative_to(folder):
                continue
            relative = path.relative_to(folder)
            draft, preview = annotation_paths(settings.root / "GroundTruthDraft", relative)
            gt, gt_preview = annotation_paths(settings.root / "GroundTruth", relative)
            images.append({"id": path.stem, "file": str(relative), "path": settings.relative(path),
                           "draft": draft.is_file(), "gt": gt.is_file(),
                           "draft_preview": settings.relative(preview) if preview.is_file() else None,
                           "gt_preview": settings.relative(gt_preview) if gt_preview.is_file() else None})
    return {"images": images, "folders": {name: (settings.root / name).is_dir() for name in
            ("images", "GroundTruthDraft", "GroundTruth", "evaluation_output", "experiment_output")}}


def build_command(settings: Settings, request: JobRequest, job_id: str, persist=False):
    script = SCRIPTS[request.script]["file"]
    if not (settings.root / script).is_file():
        raise ValueError(f"ไม่พบ script {script}")
    source = settings.within(request.input, ("images",), exists=True)
    if source.is_file() and source.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("Input ต้องเป็นไฟล์ภาพที่รองรับ")
    images = [source] if source.is_file() else sorted(
        p for p in (source.rglob("*") if request.recursive or request.script != "create_gt" else source.iterdir())
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS and p.resolve().is_relative_to(source))
    if not images:
        raise ValueError("ไม่พบภาพต้นฉบับใน input ที่เลือก")
    gt = settings.within(request.gt, ("GroundTruth",))
    drafts = settings.within(request.drafts, ("GroundTruthDraft",))
    config = validate_config(request.config)
    job_dir = settings.jobs_dir / job_id
    command = [settings.python, "-u", str(settings.root / script), "--input", str(source)]
    files = {}
    output = None
    if request.script in ("create_gt", "evaluate_ocr"):
        files["config.json"] = config
        command += ["--config", str(job_dir / "config.json")]
    if request.script == "create_gt":
        output = settings.within(request.output or request.drafts, ("GroundTruthDraft",))
        command += ["--output", str(output)]
        for flag in ("recursive", "overwrite"):
            if getattr(request, flag):
                command.append("--" + flag)
    elif request.script == "gt_editor":
        command += ["--drafts", str(drafts), "--gt", str(gt)]
    elif request.script == "evaluate_ocr":
        selected = [image for image in images if not request.ids or image.stem in request.ids]
        if set(request.ids) - {image.stem for image in images}:
            raise ValueError("มี ID ภาพที่ไม่อยู่ใน input")
        source_root = source.parent if source.is_file() else source
        if not any(annotation_paths(gt, image.relative_to(source_root))[0].is_file() for image in selected):
            raise ValueError("ยังไม่มี saved GT สำหรับภาพที่เลือก กรุณาบันทึกจาก GT Editor ก่อน")
        output = settings.within(request.output or "evaluation_output", ("evaluation_output",)) / f"web-{job_id}"
        command += ["--gt", str(gt), "--output", str(output)]
        if request.ids:
            command += ["--ids", *request.ids]
    elif request.script == "experiment_ocr":
        if not source.is_dir():
            raise ValueError("Experiment ต้องใช้ input เป็นโฟลเดอร์")
        split = settings.within(request.split_file, ("experiments",), exists=True)
        try:
            records = load_records(split, source, request.tune_only)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            raise ValueError(f"ไฟล์ split ไม่ถูกต้อง: {error}") from error
        if not request.dry_run:
            missing = [record["relative"] for record in records if not annotation_paths(gt, record["relative"])[0].is_file()]
            if missing:
                raise ValueError("ยังไม่มี saved GT: " + ", ".join(missing))
        output = settings.within(request.output or "experiment_output", ("experiment_output",)) / f"web-{job_id}"
        command += ["--gt", str(gt), "--split-file", str(split), "--output", str(output), "--timeout", str(request.timeout)]
        if request.experiment_mode == "custom":
            if not request.experiments:
                raise ValueError("กรุณากำหนดชุดทดลองอย่างน้อย 1 ชุด")
            names = [entry.name for entry in request.experiments]
            if len(set(names)) != len(names):
                raise ValueError("ชื่อชุดทดลองต้องไม่ซ้ำกัน")
            files["experiments.json"] = {"experiments": [
                {"name": entry.name, "parameters": validate_config(entry.parameters)} for entry in request.experiments]}
            command += ["--experiments", str(job_dir / "experiments.json")]
        for enabled, flag in ((request.tune_only, "--tune-only"), (not request.combine, "--no-combine"), (request.dry_run, "--dry-run")):
            if enabled:
                command.append(flag)
    if request.font:
        font = settings.within(request.font, ("fonts",), exists=True)
        if font.suffix.lower() not in (".ttf", ".otf", ".ttc"):
            raise ValueError("Font ต้องเป็น .ttf, .otf หรือ .ttc")
        command += ["--font", str(font)]
    if request.font_size:
        command += ["--font-size", str(request.font_size)]
    if persist:
        job_dir.mkdir(parents=True, exist_ok=False)
        for filename, value in files.items():
            write_json(job_dir / filename, value)
    return {"args": command, "command": shlex.join(command),
            "output": settings.relative(output) if output else None, "config": config}
