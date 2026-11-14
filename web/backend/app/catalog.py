"""Adapters to the existing CLI and its shared, model-free configuration."""
import shlex
import subprocess
from functools import cache
from pathlib import Path

from .config import Settings
from .schemas import JobRequest
from experiment_ocr import automatic_trials, load_records
from helpers.ocr_common import (
    BASELINE,
    DEVICE_HELP,
    IMAGE_EXTENSIONS,
    PARAMETER_HELP,
    annotation_paths,
    validate_config,
    write_json,
)

SCRIPTS = {
    "create_gt": {
        "title": "สร้าง Draft",
        "file": "create_gt.py",
        "step": 1,
    },
    "gt_editor": {
        "title": "ตรวจแก้ Ground Truth",
        "file": "gt_editor.py",
        "step": 2,
    },
    "evaluate_ocr": {
        "title": "ประเมิน OCR",
        "file": "evaluate_ocr.py",
        "step": 3,
    },
    "experiment_ocr": {
        "title": "ทดลอง Parameter",
        "file": "experiment_ocr.py",
        "step": 4,
    },
}

GPU_PROBE = (
    "import importlib.metadata as m\n"
    "try: m.version('paddlepaddle-gpu')\n"
    "except m.PackageNotFoundError: raise SystemExit(1)"
)


@cache
def gpu_build(python: str):
    """Whether the scripts' Python has the GPU build of paddlepaddle, checked without importing paddle.

    CUDA itself is verified by build_engine() when a run starts.
    """
    try:
        result = subprocess.run(
            [python, "-c", GPU_PROBE],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def catalog(settings: Settings):
    scripts = [
        {"id": key, **value}
        for key, value in SCRIPTS.items()
    ]

    return {
        "scripts": scripts,
        "baseline": BASELINE,
        "parameter_help": PARAMETER_HELP,
        "automatic_trials": automatic_trials(),
        "device": {
            "gpu_build": gpu_build(settings.python),
            "help": DEVICE_HELP,
        },
    }


def image_relative_paths(folder):
    paths = []

    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue

        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        if not path.resolve().is_relative_to(folder):
            continue

        paths.append(path)

    return paths


def dataset(settings: Settings):
    folder = settings.root / "images"
    images = []

    if folder.is_dir():
        for path in image_relative_paths(folder):
            relative = path.relative_to(folder)

            draft, preview = annotation_paths(
                settings.root / "GroundTruthDraft",
                relative,
            )
            gt, gt_preview = annotation_paths(
                settings.root / "GroundTruth",
                relative,
            )

            if preview.is_file():
                draft_preview = settings.relative(preview)
            else:
                draft_preview = None

            if gt_preview.is_file():
                gt_preview_path = settings.relative(gt_preview)
            else:
                gt_preview_path = None

            images.append(
                {
                    "id": path.stem,
                    "file": str(relative),
                    "path": settings.relative(path),
                    "draft": draft.is_file(),
                    "gt": gt.is_file(),
                    "draft_preview": draft_preview,
                    "gt_preview": gt_preview_path,
                }
            )

    folder_names = (
        "images",
        "GroundTruthDraft",
        "GroundTruth",
        "evaluation_output",
        "experiment_output",
    )
    folders = {
        name: (settings.root / name).is_dir()
        for name in folder_names
    }

    return {
        "images": images,
        "folders": folders,
    }


def find_request_images(request, source):
    if source.is_file():
        return [source]

    if request.recursive or request.script != "create_gt":
        candidates = source.rglob("*")
    else:
        candidates = source.iterdir()

    return sorted(
        path
        for path in candidates
        if path.is_file()
        and path.suffix.lower() in IMAGE_EXTENSIONS
        and path.resolve().is_relative_to(source)
    )


def append_experiment_options(command, request):
    if request.device:
        command += ["--device", request.device]

    options = (
        (request.tune_only, "--tune-only"),
        (not request.combine, "--no-combine"),
        (request.dry_run, "--dry-run"),
    )

    for enabled, flag in options:
        if enabled:
            command.append(flag)

    return command


def build_command(settings: Settings, request: JobRequest, job_id: str, persist=False):
    script = SCRIPTS[request.script]["file"]

    if not (settings.root / script).is_file():
        raise ValueError(f"ไม่พบ script {script}")

    source = settings.within(request.input, ("images",), exists=True)

    if source.is_file() and source.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("Input ต้องเป็นไฟล์ภาพที่รองรับ")

    images = find_request_images(request, source)

    if not images:
        raise ValueError("ไม่พบภาพต้นฉบับใน input ที่เลือก")

    gt = settings.within(request.gt, ("GroundTruth",))
    drafts = settings.within(request.drafts, ("GroundTruthDraft",))

    overrides = dict(request.config)
    if request.device:
        overrides["device"] = request.device
    config = validate_config(overrides)

    job_dir = settings.jobs_dir / job_id
    command = [
        settings.python,
        "-u",
        str(settings.root / script),
        "--input",
        str(source),
    ]
    files = {}
    output = None

    if request.script in ("create_gt", "evaluate_ocr"):
        files["config.json"] = config
        command += ["--config", str(job_dir / "config.json")]

    if request.script == "create_gt":
        output = settings.within(
            request.output or request.drafts,
            ("GroundTruthDraft",),
        )
        command += ["--output", str(output)]

        for flag in ("recursive", "overwrite"):
            if getattr(request, flag):
                command.append("--" + flag)

    elif request.script == "gt_editor":
        command += ["--drafts", str(drafts), "--gt", str(gt)]

    elif request.script == "evaluate_ocr":
        selected = [
            image
            for image in images
            if not request.ids or image.stem in request.ids
        ]

        if set(request.ids) - {image.stem for image in images}:
            raise ValueError("มี ID ภาพที่ไม่อยู่ใน input")

        if source.is_file():
            source_root = source.parent
        else:
            source_root = source

        has_gt = any(
            annotation_paths(gt, image.relative_to(source_root))[0].is_file()
            for image in selected
        )

        if not has_gt:
            raise ValueError(
                "ภาพที่เลือกยังไม่มีเฉลย กรุณาตรวจแก้และกดบันทึกในขั้นที่ 2 ก่อน"
            )

        output = settings.within(
            request.output or "evaluation_output",
            ("evaluation_output",),
        ) / f"web-{job_id}"
        command += ["--gt", str(gt), "--output", str(output)]

        if request.ids:
            command += ["--ids", *request.ids]

    elif request.script == "experiment_ocr":
        if not source.is_dir():
            raise ValueError("Experiment ต้องใช้ input เป็นโฟลเดอร์")

        split = settings.within(
            request.split_file,
            ("experiments",),
            exists=True,
        )

        try:
            records = load_records(split, source, request.tune_only)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            raise ValueError(f"ไฟล์ split ไม่ถูกต้อง: {error}") from error

        if not request.dry_run:
            missing = [
                record["relative"]
                for record in records
                if not annotation_paths(gt, record["relative"])[0].is_file()
            ]

            if missing:
                raise ValueError("ยังไม่มีเฉลยของภาพ: " + ", ".join(missing))

        output = settings.within(
            request.output or "experiment_output",
            ("experiment_output",),
        ) / f"web-{job_id}"
        command += [
            "--gt",
            str(gt),
            "--split-file",
            str(split),
            "--output",
            str(output),
            "--timeout",
            str(request.timeout),
        ]

        if request.experiment_mode == "custom":
            if not request.experiments:
                raise ValueError("กรุณากำหนดชุดทดลองอย่างน้อย 1 ชุด")

            names = [entry.name for entry in request.experiments]
            if len(set(names)) != len(names):
                raise ValueError("ชื่อชุดทดลองต้องไม่ซ้ำกัน")

            files["experiments.json"] = {
                "experiments": [
                    {
                        "name": entry.name,
                        "parameters": validate_config(entry.parameters),
                    }
                    # --device below overrides each trial's device
                    for entry in request.experiments
                ]
            }
            command += ["--experiments", str(job_dir / "experiments.json")]

        command = append_experiment_options(command, request)

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

    if output:
        relative_output = settings.relative(output)
    else:
        relative_output = None

    return {
        "args": command,
        "command": shlex.join(command),
        "output": relative_output,
        "config": config,
    }
