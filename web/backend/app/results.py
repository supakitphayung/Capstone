"""Read existing reports and serve only explicitly allowed project artifacts."""
import hashlib
import json
from pathlib import Path

from .config import Settings
from helpers.ocr_common import validate_config

ARTIFACT_ROOTS = (
    "images",
    "GroundTruth",
    "GroundTruthDraft",
    "evaluation_output",
    "experiment_output",
)

ARTIFACT_SUFFIXES = {
    ".json",
    ".md",
    ".log",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


def read_optional(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class Results:
    def __init__(self, settings: Settings):
        self.settings = settings

    def artifact(self, relative):
        path = self.settings.within(
            relative,
            ARTIFACT_ROOTS,
            exists=True,
        )

        if not path.is_file() or path.suffix.lower() not in ARTIFACT_SUFFIXES:
            raise ValueError("ไฟล์นี้ไม่ใช่ผลลัพธ์ที่เปิดผ่านเว็บได้")

        return path

    def index(self):
        found = []
        root = self.settings.root

        patterns = (
            ("experiment_output", "comparison.json", "experiment"),
            ("evaluation_output", "report.json", "evaluation"),
        )

        for folder, filename, kind in patterns:
            directory = root / folder

            if not directory.is_dir():
                continue

            for path in directory.rglob(filename):
                if not path.resolve().is_relative_to(directory):
                    continue

                if kind == "evaluation" and path.parent.name != "evaluation":
                    continue

                report = read_optional(path)

                if not isinstance(report, dict):
                    continue

                relative = self.settings.relative(path)
                result_id = hashlib.sha256(relative.encode()).hexdigest()[:20]

                found.append(
                    {
                        "id": result_id,
                        "kind": kind,
                        "name": str(path.parent.relative_to(directory)),
                        "path": relative,
                        "status": report.get("status", "unknown"),
                        "created_utc": report.get("created_utc"),
                        "best_trial": report.get("best_trial"),
                        "_modified": path.stat().st_mtime,
                    }
                )

        ordered = sorted(
            found,
            key=lambda item: item["_modified"],
            reverse=True,
        )

        return [
            {
                key: value
                for key, value in item.items()
                if key != "_modified"
            }
            for item in ordered
        ]

    def _image(self, item, folder):
        item = dict(item)
        framed = item.get("framed_image")
        item["framed_path"] = None

        if framed:
            try:
                path = self.artifact(
                    self.settings.relative(folder / framed)
                )
                item["framed_path"] = self.settings.relative(path)
            except (ValueError, OSError):
                pass

        return item

    def _report(self, report, folder):
        if not isinstance(report, dict):
            return report

        return {
            **report,
            "images": [
                self._image(item, folder)
                for item in report.get("images", [])
            ],
        }

    def get(self, result_id):
        entry = next(
            (item for item in self.index() if item["id"] == result_id),
            None,
        )

        if not entry:
            raise FileNotFoundError("ไม่พบรายงานนี้")

        path = self.artifact(entry["path"])
        report = read_optional(path)

        if report is None:
            raise FileNotFoundError("รายงานกำลังอัปเดตหรือยังอ่านไม่ได้ กรุณาลองอีกครั้ง")

        if entry["kind"] == "experiment":
            trials = [
                self._report(
                    trial,
                    path.parent / "trials" / trial["name"],
                )
                for trial in report.get("trials", [])
            ]
            report = {
                **report,
                "trials": trials,
                "holdout": self._report(
                    report.get("holdout"),
                    path.parent / "holdout",
                ),
            }
        else:
            report = self._report(report, path.parent)

        selected = path.parent / "selected_config.json"

        if selected.is_file():
            selected_config_path = self.settings.relative(selected)
        else:
            selected_config_path = None

        return {
            **entry,
            "report": report,
            "selected_config_path": selected_config_path,
        }

    def presets(self):
        items = []

        for entry in self.index():
            if entry["kind"] != "experiment":
                continue

            path = self.settings.root / entry["path"]
            selected = read_optional(path.parent / "selected_config.json")

            if not isinstance(selected, dict):
                continue

            try:
                config = validate_config(selected)
            except ValueError:
                continue

            if entry["best_trial"]:
                best_trial = entry["best_trial"]
            else:
                best_trial = "selected"

            items.append(
                {
                    "id": entry["id"],
                    "name": f"{entry['name']} · {best_trial}",
                    "config": config,
                }
            )

        return items
