"""Validated public inputs; the browser cannot supply shell commands."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Script = Literal["create_gt", "gt_editor", "evaluate_ocr", "experiment_ocr"]


class Experiment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$")
    parameters: dict[str, Any] = Field(default_factory=dict)


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    script: Script
    input: str = "images"
    gt: str = "GroundTruth"
    drafts: str = "GroundTruthDraft"
    output: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    ids: list[str] = Field(default_factory=list)
    recursive: bool = False
    overwrite: bool = False
    font: str | None = None
    font_size: int | None = Field(default=None, gt=0)
    timeout: float = Field(default=1800, gt=0)
    tune_only: bool = False
    combine: bool = True
    dry_run: bool = False
    split_file: str = "experiments/dataset_split.json"
    experiment_mode: Literal["automatic", "custom"] = "automatic"
    experiments: list[Experiment] = Field(default_factory=list)
