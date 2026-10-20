"""Regression tests for drawing boxes and evaluating saved GT without review flags."""
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolButton

import evaluate_ocr
from gt_editor import Editor
from helpers.gt_document import GTDocument
from helpers.ocr_common import annotation_paths, read_json, write_json


class GTWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gt-workflow-test-")
        self.root = Path(self.temporary.name)
        self.images, self.drafts, self.gt = (self.root/name for name in ("images", "drafts", "GroundTruth"))
        self.images.mkdir()
        for name in ("1.png", "2.png"):
            Image.new("RGB", (400, 300), "white").save(self.images/name)
            path, _ = annotation_paths(self.drafts, name)
            write_json(path, {"pos1": {"text": "ยา", "bbox": [40, 80, 180, 110]}})
        self.editor = Editor(SimpleNamespace(input=self.images, drafts=self.drafts, gt=self.gt,
                                             font=None, font_size=None))
        self.editor.show()
        self.app.processEvents()

    def tearDown(self):
        self.editor.doc.saved_state = self.editor.doc.state()
        self.editor.close()
        self.app.processEvents()
        self.temporary.cleanup()

    def toolbar_button(self, name):
        action = self.editor.actions[name]
        return next(button for button in self.editor.findChildren(QToolButton) if button.defaultAction() == action)

    def draw_box(self, start=(220, 170), end=(330, 230)):
        before = set(self.editor.doc.data)
        QTest.mouseClick(self.toolbar_button("เพิ่มกรอบ"), Qt.MouseButton.LeftButton)
        self.assertTrue(self.editor.view.add_mode)
        self.assertEqual(self.editor.view.dragMode(), self.editor.view.DragMode.NoDrag)
        view = self.editor.view
        first, last = view.mapFromScene(QPointF(*start)), view.mapFromScene(QPointF(*end))
        self.assertTrue(view.viewport().rect().contains(first))
        self.assertTrue(view.viewport().rect().contains(last))
        QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, first)
        QTest.mouseMove(view.viewport(), last, 10)
        self.assertIsNotNone(view.preview)
        QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, last)
        self.app.processEvents()
        created = set(self.editor.doc.data)-before
        self.assertEqual(len(created), 1)
        self.assertFalse(view.add_mode)
        self.assertFalse(self.editor.actions["เพิ่มกรอบ"].isChecked())
        self.assertIsNone(view.preview)
        return created.pop()

    def test_toolbar_adds_box_and_selects_text_field(self):
        key = self.draw_box()
        self.assertEqual(self.editor.view.active, key)
        self.assertEqual(self.editor.doc.data[key]["text"], "")
        self.assertFalse(self.editor.doc.data[key]["ignore"])
        self.assertTrue(self.editor.text_edit.hasFocus())
        self.editor.undo()
        self.assertNotIn(key, self.editor.doc.data)
        self.editor.redo()
        self.assertIn(key, self.editor.doc.data)

    def test_lost_space_release_does_not_block_drawing(self):
        view = self.editor.view
        view.setFocus()
        self.app.processEvents()
        QTest.keyPress(view, Qt.Key.Key_Space)
        self.assertTrue(view.space_down)
        self.editor.text_edit.setFocus()
        self.app.processEvents()
        QTest.keyRelease(self.editor.text_edit, Qt.Key.Key_Space)
        self.assertFalse(view.space_down)
        self.draw_box()

    def test_checked_action_enables_drawing_without_a_trigger_signal(self):
        self.editor.actions["เพิ่มกรอบ"].setChecked(True)
        self.assertTrue(self.editor.view.add_mode)
        self.assertEqual(self.editor.view.viewport().cursor().shape(), Qt.CursorShape.CrossCursor)
        self.editor.actions["เพิ่มกรอบ"].setChecked(False)
        self.assertFalse(self.editor.view.add_mode)

    def test_reverse_drag_after_zoom_uses_original_image_coordinates(self):
        self.editor.view.scale(1.5, 1.5)
        self.editor.view.centerOn(260, 190)
        self.editor.view.refresh()
        key = self.draw_box((320, 230), (220, 160))
        for got, expected in zip(self.editor.doc.data[key]["bbox"], [220, 160, 320, 230]):
            self.assertAlmostEqual(got, expected, delta=1)
        self.editor.text_edit.setText("100 mL")
        self.assertTrue(self.editor.save())
        reopened = GTDocument(self.images/"1.png", "1.png", self.drafts, self.gt)
        self.assertEqual(reopened.data, self.editor.doc.data)

    def test_space_temporarily_pans_in_drawing_mode(self):
        view = self.editor.view
        self.editor.actions["เพิ่มกรอบ"].setChecked(True)
        QTest.keyPress(view, Qt.Key.Key_Space)
        self.assertEqual(view.dragMode(), view.DragMode.ScrollHandDrag)
        QTest.keyRelease(view, Qt.Key.Key_Space)
        self.assertEqual(view.dragMode(), view.DragMode.NoDrag)
        self.assertFalse(view.space_down)
        self.editor.actions["เพิ่มกรอบ"].setChecked(False)
        self.draw_box()

    def test_move_and_resize_after_zoom(self):
        view = self.editor.view
        view.scale(1.5, 1.5)
        view.centerOn(160, 120)
        view.active = "pos1"
        view.refresh()
        start, end = view.mapFromScene(QPointF(110, 95)), view.mapFromScene(QPointF(135, 110))
        QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
        QTest.mouseMove(view.viewport(), end, 10)
        QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
        moved = self.editor.doc.data["pos1"]["bbox"][:]
        for got, expected in zip(moved, [65, 95, 205, 125]):
            self.assertAlmostEqual(got, expected, delta=1)
        right, bottom = moved[2:]
        start, end = view.mapFromScene(QPointF(right, bottom)), view.mapFromScene(QPointF(right+15, bottom+20))
        QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
        QTest.mouseMove(view.viewport(), end, 10)
        QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
        resized = self.editor.doc.data["pos1"]["bbox"]
        self.assertAlmostEqual(resized[2], right+15, delta=1)
        self.assertAlmostEqual(resized[3], bottom+20, delta=1)
        self.editor.undo()
        self.assertEqual(self.editor.doc.data["pos1"]["bbox"], moved)

    def test_switch_image_clears_drawing_state_and_preview(self):
        self.editor.actions["เพิ่มกรอบ"].setChecked(True)
        view = self.editor.view
        start, end = view.mapFromScene(QPointF(220, 170)), view.mapFromScene(QPointF(330, 230))
        QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
        QTest.mouseMove(view.viewport(), end, 10)
        self.assertIsNotNone(view.preview)
        self.editor.image_picker.setCurrentIndex(1)
        QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
        self.assertEqual(self.editor.doc.relative.name, "2.png")
        self.assertFalse(view.add_mode)
        self.assertIsNone(view.gesture)
        self.assertIsNone(view.preview)
        self.assertFalse(self.editor.actions["เพิ่มกรอบ"].isChecked())
        self.draw_box()

    def test_save_writes_ignore_in_gt_without_review_metadata(self):
        self.assertNotIn("ตรวจครบแล้ว", self.editor.actions)
        self.editor.doc.update("pos1", ignore=True)
        self.editor.refresh("pos1")
        QTest.mouseClick(self.toolbar_button("บันทึก"), Qt.MouseButton.LeftButton)
        data = read_json(self.gt/"1_gt.json")
        self.assertTrue(data["pos1"]["ignore"])
        self.assertFalse(list(self.gt.glob("*.review.json")))
        self.assertEqual({path.name for path in self.gt.iterdir()}, {"1_gt.json", "1_gt.png"})
        reopened = GTDocument(self.images/"1.png", "1.png", self.drafts, self.gt)
        self.assertEqual(reopened.ignored, {"pos1"})
        self.assertFalse(reopened.dirty)

    def test_saved_gt_is_evaluated_without_confirmation(self):
        QTest.mouseClick(self.toolbar_button("บันทึก"), Qt.MouseButton.LeftButton)
        class Engine:
            def predict(self, image):
                return [{"rec_texts": ["ยา"], "rec_scores": [.99],
                         "rec_polys": [[[40, 80], [180, 80], [180, 110], [40, 110]]]}]
        output = self.root/"results"
        argv = ["evaluate_ocr.py", "--input", str(self.images), "--gt", str(self.gt), "--output", str(output)]
        with patch.object(sys, "argv", argv), patch("evaluate_ocr.build_engine", return_value=(Engine(), .1)), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(evaluate_ocr.main(), 0)
        run = next(output.iterdir())
        report = read_json(run/"evaluation/report.json")
        self.assertEqual(report["metrics"]["end_to_end"]["f1"], 1)
        self.assertEqual(report["completed_images"], 1)
        self.assertEqual(read_json(run/"skipped.json"), [{"image": "2.png", "reason": "no saved GT"}])
        self.assertFalse(list((run/"dataset").rglob("*.review.json")))

    def test_empty_new_box_can_be_saved_without_a_review_gate(self):
        key = self.draw_box()
        self.assertTrue(self.editor.save())
        data = read_json(self.gt/"1_gt.json")
        self.assertEqual(data[key]["text"], "")
        self.assertFalse(data[key]["ignore"])

    def test_saved_edits_are_used_without_hash_reconfirmation(self):
        self.assertTrue(self.editor.save())
        path = self.gt/"1_gt.json"
        data = read_json(path)
        data["pos1"]["text"] = "แก้โดยตรง"
        write_json(path, data)
        reopened = GTDocument(self.images/"1.png", "1.png", self.drafts, self.gt)
        self.assertEqual(reopened.data["pos1"]["text"], "แก้โดยตรง")
        manifest = evaluate_ocr.freeze_dataset([{"relative": "1.png", "image_path": self.images/"1.png"}], self.gt, self.root/"snapshot")
        sample = read_json(manifest)["samples"][0]
        self.assertEqual(read_json(manifest.parent/sample["gt"])["pos1"]["text"], "แก้โดยตรง")


if __name__ == "__main__":
    unittest.main()
