"""Editable GT document with undo/redo, independent of Qt."""
from copy import deepcopy
from pathlib import Path

from PIL import Image

from .ocr_common import (GRAY, GREEN, annotation_paths, read_image, read_json,
                        save_framed, validate_annotations, write_json)


class GTDocument:
    def __init__(self, image_path, relative, draft_root, gt_root):
        self.image_path = Path(image_path).resolve()
        self.relative = Path(relative)
        self.gt_path, self.preview_path = annotation_paths(gt_root, relative)
        draft_path, _ = annotation_paths(draft_root, relative)
        with Image.open(self.image_path) as image:
            self.width, self.height = image.size
        if self.gt_path.exists():
            self.data = read_json(self.gt_path)
        else:
            draft = read_json(draft_path) if draft_path.exists() else {}
            self.data = {key: {"text": value["text"], "bbox": value["bbox"], "ignore": False}
                         for key, value in draft.items()}
        validate_annotations(self.data, self.width, self.height)
        self.undo_stack, self.redo_stack = [], []
        self.saved_state = self.state()

    def state(self):
        return deepcopy(self.data)

    @property
    def ignored(self):
        return {key for key, value in self.data.items() if value["ignore"]}

    @property
    def dirty(self):
        return self.state() != self.saved_state

    def commit(self, data):
        validate_annotations(data, self.width, self.height)
        state = deepcopy(data)
        if state == self.state():
            return
        self.undo_stack.append(self.state())
        self.undo_stack = self.undo_stack[-200:]
        self.redo_stack.clear()
        self.data = state

    def update(self, key, text=None, bbox=None, ignore=None):
        data = deepcopy(self.data)
        if text is not None:
            data[key]["text"] = text
        if bbox is not None:
            data[key]["bbox"] = list(bbox)
        if ignore is not None:
            data[key]["ignore"] = ignore
        self.commit(data)

    def add(self, bbox, text=""):
        key = f"pos{1 + max((int(key[3:]) for key in self.data), default=0)}"
        data = deepcopy(self.data)
        data[key] = {"text": text, "bbox": list(bbox), "ignore": False}
        self.commit(data)
        return key

    def delete(self, key):
        data = deepcopy(self.data)
        del data[key]
        self.commit(data)

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.state())
            self.data = self.undo_stack.pop()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.state())
            self.data = self.redo_stack.pop()

    def save(self, font=None, font_size=None):
        validate_annotations(self.data, self.width, self.height)
        annotations = []
        for key, value in self.data.items():
            ignored = value["ignore"]
            label = f"{key} [ignore] {value['text']}" if ignored else f"{key}: {value['text']}"
            annotations.append({**value, "color": GRAY if ignored else GREEN, "label": label})
        save_framed(self.preview_path, read_image(self.image_path), annotations, font, font_size)
        write_json(self.gt_path, self.data)
        self.saved_state = self.state()
