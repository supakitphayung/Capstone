"""OCR output filtering and selection tests without loading model weights."""
import argparse
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image

import evaluate_ocr
import experiment_ocr
from helpers.ocr_common import (BASELINE, add_ocr_arguments, build_engine,
                               config_from_args, predict_regions, read_json,
                               validate_config, write_json)


def fake_engine(texts, scores=None, polygons=None):
    if polygons is None:
        polygons = [[[10, 20], [70, 20], [70, 40], [10, 40]] for _ in texts]
    return SimpleNamespace(predict=Mock(return_value=[{
        "rec_texts": texts, "rec_scores": scores if scores is not None else [.99] * len(texts),
        "rec_polys": polygons,
    }]))


class OCRFilteringTests(unittest.TestCase):
    def test_filters_single_characters_and_detached_marks_preserving_thai_words(self):
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        engine = fake_engine(["่", "9", " N ", " \t ", "่้", "ยา", "ก้", "100 ml", "A B", "A \t", "e\u0301"])
        regions, _ = predict_regions(engine, image, validate_config())
        self.assertEqual([region["text"] for region in regions], ["ยา", "ก้", "100 ml", "A B"])
        self.assertEqual([region["id"] for region in regions], [1, 2, 3, 4])

    def test_filter_retains_roi_mapping_and_confidence_threshold(self):
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        polygon = [[20, 10], [100, 10], [100, 50], [20, 50]]
        engine = fake_engine(["9", "ยา", "low"], [.99, .95, .2], [polygon] * 3)
        config = validate_config({"scale": 2.0})
        regions, _ = predict_regions(engine, image, config, roi=(10, 20, 80, 30), min_confidence=.9)
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0]["text"], "ยา")
        self.assertEqual(regions[0]["bbox"], [20, 25, 60, 45])
        self.assertEqual(regions[0]["id"], 1)
        self.assertEqual(engine.predict.call_args.args[0].shape[:2], (60, 160))

    def test_minimum_length_can_be_changed_without_accepting_mark_only_text(self):
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        regions, _ = predict_regions(fake_engine(["N", "่", "่้"]), image,
                                     validate_config({"min_text_length": 1}))
        self.assertEqual([region["text"] for region in regions], ["N"])
        parser = argparse.ArgumentParser()
        add_ocr_arguments(parser)
        args = parser.parse_args(["--min-text-length", "3"])
        self.assertEqual(config_from_args(args)["min_text_length"], 3)
        for invalid in (0, -1, 2.5, True, "2", None):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                validate_config({"min_text_length": invalid})

    def test_application_filters_are_not_passed_to_paddleocr_constructor(self):
        constructor = Mock(return_value=object())
        with patch.dict(sys.modules, {"paddleocr": SimpleNamespace(PaddleOCR=constructor)}), patch.dict(os.environ):
            engine, _ = build_engine(validate_config({"min_text_length": 3, "scale": .5}))
        self.assertIs(engine, constructor.return_value)
        self.assertNotIn("min_text_length", constructor.call_args.kwargs)
        self.assertNotIn("scale", constructor.call_args.kwargs)
        self.assertEqual(constructor.call_args.kwargs["text_detection_model_name"], BASELINE["text_detection_model_name"])

    def test_evaluation_scores_filtered_predictions_and_keeps_single_character_gt(self):
        with tempfile.TemporaryDirectory(prefix="ocr-filter-test-") as temporary:
            root = Path(temporary)
            image_path = root / "1.png"
            Image.new("RGB", (200, 100), "white").save(image_path)
            write_json(root / "gt/1_gt.json", {
                "pos1": {"text": "ยา", "bbox": [10, 20, 70, 40], "ignore": False},
                "pos2": {"text": "N", "bbox": [100, 20, 130, 40], "ignore": False},
            })
            manifest = evaluate_ocr.freeze_dataset([
                {"relative": "1.png", "image_path": image_path, "split": "tune"},
            ], root / "gt", root / "dataset")
            polygons = [[[10, 20], [70, 20], [70, 40], [10, 40]],
                        [[100, 20], [130, 20], [130, 40], [100, 40]]]
            with patch("evaluate_ocr.build_engine", return_value=(fake_engine(["ยา", "N"], polygons=polygons), .1)), \
                    patch("evaluate_ocr.find_thai_font", return_value=root / "unused.ttf"), \
                    patch("evaluate_ocr.save_framed"), contextlib.redirect_stdout(io.StringIO()):
                report = evaluate_ocr.run_evaluation(manifest, "tune", validate_config(), root / "result")
            self.assertEqual(report["status"], "completed")
            self.assertEqual(report["metrics"]["total_detections"], 1)
            self.assertEqual(report["metrics"]["total_gt_positions"], 2)
            self.assertEqual(report["metrics"]["missed_positions"], 1)
            self.assertEqual(report["metrics"]["accuracy_percent"], 50)
            self.assertEqual(read_json(root / "result/config.json")["min_text_length"], 2)


class ExperimentSelectionTests(unittest.TestCase):
    def test_focused_winner_can_be_selected_without_contaminating_one_factor_combination(self):
        def report(name, overrides, f1, split="tune"):
            return {"name": name, "config": validate_config(overrides), "status": "completed", "split": split,
                    "metrics": {"end_to_end": {"f1": f1}, "matched_cer": .1},
                    "ocr_seconds": 1, "peak_rss_mb": 100}

        reports = [report("baseline", {}, .5),
                   report("resolution", {"text_det_limit_side_len": 3200}, .8),
                   report("padding", {"text_det_unclip_ratio": 1.2}, .7),
                   report("tight-thai-lines", experiment_ocr.FOCUSED_TRIALS["tight-thai-lines"], .9),
                   report("holdout", {"text_det_thresh": .2}, 1, split="holdout")]
        combined = experiment_ocr.combined_trial(reports)
        self.assertEqual(combined["config"], validate_config({
            "text_det_limit_side_len": 3200, "text_det_unclip_ratio": 1.2,
        }))
        self.assertEqual(experiment_ocr.choose_best(reports)["name"], "tight-thai-lines")

    def test_dry_run_lists_focused_configs_without_gt_or_loading_ocr(self):
        with tempfile.TemporaryDirectory(prefix="ocr-dry-run-test-") as temporary:
            root = Path(temporary)
            Image.new("RGB", (200, 100), "white").save(root / "1.png")
            write_json(root / "split.json", {"samples": [
                {"id": "1", "group": "product", "file": "1.png", "split": "tune"},
            ]})
            argv = ["experiment_ocr.py", "--dry-run", "--tune-only", "--input", str(root),
                    "--split-file", str(root / "split.json"), "--gt", str(root / "missing-gt")]
            stdout = io.StringIO()
            with patch.object(sys, "argv", argv), patch("evaluate_ocr.build_engine") as build, \
                    contextlib.redirect_stdout(stdout):
                self.assertEqual(experiment_ocr.main(), 0)
            build.assert_not_called()
            output = stdout.getvalue()
            for name in ("tight-thai-lines", "thai-diacritics", "large-touching-text"):
                self.assertIn(name, output)
            self.assertIn("min_text_length = 2", output)


if __name__ == "__main__":
    unittest.main()
