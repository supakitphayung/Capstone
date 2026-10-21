"""Local application settings; importing this module never loads OCR models."""
import os
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class Settings:
    root: Path = PROJECT_ROOT
    python: str | None = None

    def __post_init__(self):
        self.root = self.root.resolve()
        # Preserve the venv executable symlink: resolving it loses venv context.
        candidate = self.root / ".venv/bin/python"
        self.python = self.python or os.environ.get("OCR_PYTHON") or str(candidate if candidate.is_file() else sys.executable)

    @property
    def jobs_dir(self):
        return self.root / ".webui/jobs"

    @property
    def frontend(self):
        return PROJECT_ROOT / "web/frontend/dist"

    def within(self, relative: str, folders: tuple[str, ...], exists=False):
        path = (self.root / relative).resolve()
        if not any(path.is_relative_to(self.root / folder) for folder in folders):
            raise ValueError(f"เส้นทางต้องอยู่ภายใน {', '.join(folders)}")
        if exists and not path.exists():
            raise ValueError(f"ไม่พบไฟล์หรือโฟลเดอร์: {relative}")
        return path

    def relative(self, path: Path):
        return str(path.resolve().relative_to(self.root))
