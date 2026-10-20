#!/usr/bin/env python3
"""Review original label images and edit GT without importing an OCR model."""
import argparse
import sys
from pathlib import Path

from helpers.ocr_common import ROOT, find_images
from helpers.gt_document import GTDocument

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, Signal
    from PySide6.QtGui import QAction, QColor, QKeySequence, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
                                  QFormLayout, QGraphicsScene, QGraphicsView,
                                  QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox,
                                  QSplitter, QVBoxLayout, QWidget)
except ImportError:
    if __name__ == "__main__":
        print("Install the GUI dependency: .venv/bin/python -m pip install -r requirements.txt", file=sys.stderr)
        sys.exit(2)
    raise


class ImageView(QGraphicsView):
    selected = Signal(str)
    box_changed = Signal(str, list)
    box_added = Signal(list)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setMouseTracking(True)
        self.doc = None
        self.active = None
        self.overlays = []
        self.add_mode = False
        self.gesture = None
        self.preview = None
        self.space_down = False

    def load_document(self, doc):
        self.set_add_mode(False)
        self.doc, self.active = doc, None
        self.scene().clear()
        self.overlays = []
        pixmap = QPixmap(str(doc.image_path))
        if pixmap.isNull():
            raise ValueError(f"Cannot open image: {doc.image_path}")
        self.scene().addPixmap(pixmap)
        self.setSceneRect(0, 0, doc.width, doc.height)
        self.refresh()
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def clear_gesture(self):
        self.gesture = None
        if self.preview is not None:
            self.scene().removeItem(self.preview)
            self.preview = None

    def set_add_mode(self, enabled):
        self.clear_gesture()
        self.space_down = False
        self.add_mode = enabled
        self.update_drag_mode()

    def update_drag_mode(self):
        drawing = self.add_mode and not self.space_down
        self.setDragMode(QGraphicsView.DragMode.NoDrag if drawing else QGraphicsView.DragMode.ScrollHandDrag)
        cursor = (Qt.CursorShape.CrossCursor if drawing else
                  Qt.CursorShape.OpenHandCursor if self.space_down else Qt.CursorShape.ArrowCursor)
        self.viewport().setCursor(cursor)

    def focusOutEvent(self, event):
        self.space_down = False
        self.update_drag_mode()
        super().focusOutEvent(event)

    def refresh(self):
        for item in self.overlays:
            self.scene().removeItem(item)
        self.overlays = []
        if not self.doc:
            return
        for key, value in self.doc.data.items():
            l, t, r, b = value["bbox"]
            color = QColor("#007aff" if key == self.active else "#777777" if value["ignore"] else "#00aa00")
            pen = QPen(color, 2 if key == self.active else 1)
            pen.setCosmetic(True)
            rect = self.scene().addRect(QRectF(l, t, r-l, b-t), pen)
            self.overlays.append(rect)
            label = self.scene().addSimpleText(f"{key}: {value['text']}")
            label.setBrush(color)
            label.setPos(l, t)
            self.overlays.append(label)
            if key == self.active:
                size = 8 / max(self.transform().m11(), 0.01)
                for x, y in ((l,t), (r,t), (l,b), (r,b)):
                    handle = self.scene().addRect(x-size/2, y-size/2, size, size, pen, color)
                    self.overlays.append(handle)

    def wheelEvent(self, event):
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        if 0.02 <= self.transform().m11() * factor <= 30:
            self.scale(factor, factor)
            self.refresh()
        event.accept()

    def bounded_point(self, event):
        point = self.mapToScene(event.position().toPoint())
        return QPointF(max(0, min(point.x(), self.doc.width)), max(0, min(point.y(), self.doc.height)))

    def mousePressEvent(self, event):
        if not self.doc or event.button() != Qt.MouseButton.LeftButton or self.space_down:
            return super().mousePressEvent(event)
        point = self.bounded_point(event)
        if self.add_mode:
            self.gesture = ("add", None, point, None)
            event.accept()
            return
        tolerance = 10 / max(self.transform().m11(), 0.01)
        if self.active in self.doc.data:
            box = self.doc.data[self.active]["bbox"]
            l,t,r,b = box
            for corner, (x,y) in enumerate(((l,t), (r,t), (l,b), (r,b))):
                if abs(point.x()-x) <= tolerance and abs(point.y()-y) <= tolerance:
                    self.gesture = ("resize", self.active, point, (box[:], corner))
                    event.accept()
                    return
        hits = [(key, value) for key, value in self.doc.data.items()
                if QRectF(value["bbox"][0], value["bbox"][1],
                          value["bbox"][2]-value["bbox"][0], value["bbox"][3]-value["bbox"][1]).contains(point)]
        if hits:
            key, value = min(hits, key=lambda pair: (pair[1]["bbox"][2]-pair[1]["bbox"][0]) *
                            (pair[1]["bbox"][3]-pair[1]["bbox"][1]))
            self.active = key
            self.selected.emit(key)
            self.gesture = ("move", key, point, value["bbox"][:])
            self.refresh()
            event.accept()
            return
        super().mousePressEvent(event)

    def gesture_box(self, point):
        kind, key, start, original = self.gesture
        if kind == "add":
            return [min(start.x(), point.x()), min(start.y(), point.y()),
                    max(start.x(), point.x()), max(start.y(), point.y())]
        if kind == "move":
            l,t,r,b = original
            dx = max(-l, min(point.x()-start.x(), self.doc.width-r))
            dy = max(-t, min(point.y()-start.y(), self.doc.height-b))
            return [l+dx,t+dy,r+dx,b+dy]
        box, corner = original
        l,t,r,b = box
        if corner in (0,2):
            l = min(point.x(), r-1)
        else:
            r = max(point.x(), l+1)
        if corner in (0,1):
            t = min(point.y(), b-1)
        else:
            b = max(point.y(), t+1)
        return [l,t,r,b]

    def mouseMoveEvent(self, event):
        if self.gesture:
            box = self.gesture_box(self.bounded_point(event))
            rectangle = QRectF(box[0],box[1],box[2]-box[0],box[3]-box[1])
            if self.preview is None:
                pen = QPen(QColor("#007aff"), 2)
                pen.setCosmetic(True)
                self.preview = self.scene().addRect(rectangle, pen)
                self.preview.setZValue(10)
            else:
                self.preview.setRect(rectangle)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.gesture and event.button() == Qt.MouseButton.LeftButton:
            kind, key, _, _ = self.gesture
            box = self.gesture_box(self.bounded_point(event))
            self.clear_gesture()
            if box[2]-box[0] >= 1 and box[3]-box[1] >= 1:
                if kind == "add":
                    self.box_added.emit(box)
                else:
                    self.box_changed.emit(key, box)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.space_down = True
            self.update_drag_mode()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.space_down = False
            self.update_drag_mode()
            event.accept()
            return
        super().keyReleaseEvent(event)


class Editor(QMainWindow):
    def __init__(self, args):
        super().__init__()
        self.args, self.doc, self.loading = args, None, False
        source = args.input.expanduser().resolve()
        self.images = find_images(source, recursive=True)
        if not self.images:
            raise ValueError("No source images found")
        self.source_root = source if source.is_dir() else source.parent
        self.resize(1400, 900)
        self.view = ImageView()
        self.image_picker = QComboBox()
        for image in self.images:
            self.image_picker.addItem(str(image.relative_to(self.source_root)))
        self.image_picker.currentIndexChanged.connect(self.change_image)
        self.positions = QListWidget()
        self.positions.currentRowChanged.connect(self.select_row)
        self.text_edit = QLineEdit()
        self.text_edit.editingFinished.connect(self.apply_fields)
        self.ignore = QCheckBox("ignore: คนอ่านไม่ได้จริง")
        self.ignore.setToolTip("ใช้เฉพาะข้อความที่คนอ่านไม่ได้ ไม่ใช้ซ่อนข้อความที่ OCR อ่านผิด")
        self.ignore.toggled.connect(self.apply_fields)
        self.coordinates = []
        form = QFormLayout()
        form.addRow("ข้อความ", self.text_edit)
        for title in ("left", "top", "right", "bottom"):
            spin = QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setRange(0, 1000000)
            spin.editingFinished.connect(self.apply_fields)
            self.coordinates.append(spin)
            form.addRow(title, spin)
        form.addRow(self.ignore)
        self.status = QLabel()
        self.status.setWordWrap(True)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(self.image_picker)
        layout.addWidget(QLabel("ตรวจทุกบรรทัด รวมสเกลปริมาตรและข้อความย่อย\nลากมุมเพื่อปรับกรอบ; Space+ลากเพื่อเลื่อน; ล้อเมาส์เพื่อซูม"))
        layout.addWidget(self.positions)
        layout.addLayout(form)
        layout.addWidget(self.status)
        splitter = QSplitter()
        splitter.addWidget(self.view)
        splitter.addWidget(panel)
        splitter.setStretchFactor(0, 1)
        self.setCentralWidget(splitter)
        toolbar = self.addToolBar("GT")
        self.actions = {}
        def action(name, callback, shortcut=None, checkable=False):
            item = QAction(name, self)
            item.setCheckable(checkable)
            if shortcut:
                item.setShortcut(shortcut)
            if checkable:
                item.toggled.connect(callback)
            else:
                item.triggered.connect(callback)
            toolbar.addAction(item)
            self.actions[name] = item
            return item
        action("บันทึก", self.save, QKeySequence.StandardKey.Save)
        action("Undo", self.undo, QKeySequence.StandardKey.Undo)
        action("Redo", self.redo, QKeySequence.StandardKey.Redo)
        action("เพิ่มกรอบ", self.set_add_mode, checkable=True)
        action("ลบกรอบ", self.delete_region)
        action("พอดีภาพ", self.fit_image)
        self.view.selected.connect(self.select_key)
        self.view.box_changed.connect(self.change_box)
        self.view.box_added.connect(self.add_box)
        self.current_index = 0
        self.change_image(0)

    def report_error(self, error):
        QMessageBox.warning(self, "บันทึก/แก้ไขไม่สำเร็จ", str(error))

    def fit_image(self):
        self.view.fitInView(self.view.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.view.refresh()

    def maybe_save(self):
        self.apply_fields()
        if not self.doc or not self.doc.dirty:
            return True
        choice = QMessageBox.question(self, "มีงานที่ยังไม่บันทึก", "บันทึกงานก่อนเปลี่ยนภาพหรือปิด?",
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        return self.save() if choice == QMessageBox.StandardButton.Save else True

    def change_image(self, index):
        if not self.maybe_save():
            self.image_picker.blockSignals(True)
            self.image_picker.setCurrentIndex(self.current_index)
            self.image_picker.blockSignals(False)
            return
        try:
            image = self.images[index]
            doc = GTDocument(image, image.relative_to(self.source_root), self.args.drafts, self.args.gt)
            self.view.load_document(doc)
            self.doc = doc
            self.actions["เพิ่มกรอบ"].setChecked(False)
            self.current_index = index
            self.refresh()
        except Exception as error:
            self.report_error(error)
            self.image_picker.blockSignals(True)
            self.image_picker.setCurrentIndex(self.current_index)
            self.image_picker.blockSignals(False)

    def refresh(self, selected=None):
        if not self.doc:
            return
        selected = selected or self.view.active
        self.loading = True
        self.positions.clear()
        self.keys = sorted(self.doc.data, key=lambda key: int(key[3:]))
        for key in self.keys:
            self.positions.addItem(f"{key}{' [ignore]' if key in self.doc.ignored else ''}: {self.doc.data[key]['text']}")
        row = self.keys.index(selected) if selected in self.keys else (0 if self.keys else -1)
        self.positions.setCurrentRow(row)
        self.loading = False
        self.select_row(row)
        self.view.refresh()
        saved_status = ("มีการแก้ไขที่ยังไม่บันทึก" if self.doc.dirty else
                        "บันทึก GT แล้ว" if self.doc.gt_path.exists() else "ยังไม่บันทึก GT")
        self.status.setText(f"{saved_status} | "
                            f"{len(self.doc.data)} กรอบ | ignore {len(self.doc.ignored)}\n"
                            "พิกัดทั้งหมดเป็นพิกเซลบนภาพต้นฉบับ")
        self.setWindowTitle(f"GT Editor — {self.doc.relative}{' *' if self.doc.dirty else ''}")
        self.actions["Undo"].setEnabled(bool(self.doc.undo_stack))
        self.actions["Redo"].setEnabled(bool(self.doc.redo_stack))

    def select_key(self, key):
        if key in self.keys:
            self.positions.setCurrentRow(self.keys.index(key))

    def select_row(self, row):
        if self.loading or not self.doc:
            return
        self.loading = True
        key = self.keys[row] if 0 <= row < len(self.keys) else None
        self.view.active = key
        value = self.doc.data.get(key)
        self.text_edit.setEnabled(value is not None)
        self.ignore.setEnabled(value is not None)
        self.text_edit.setText(value["text"] if value else "")
        self.ignore.setChecked(key in self.doc.ignored)
        for spin, coordinate in zip(self.coordinates, value["bbox"] if value else [0]*4):
            spin.setEnabled(value is not None)
            spin.setValue(coordinate)
        self.loading = False
        self.view.refresh()

    def apply_fields(self, *_):
        if self.loading or not self.doc or self.view.active not in self.doc.data:
            return
        try:
            displayed = [spin.value() for spin in self.coordinates]
            original = self.doc.data[self.view.active]["bbox"]
            bbox = None if displayed == [round(value, 2) for value in original] else displayed
            self.doc.update(self.view.active, text=self.text_edit.text(),
                            bbox=bbox, ignore=self.ignore.isChecked())
        except ValueError as error:
            self.report_error(error)
        self.refresh()

    def change_box(self, key, box):
        self.doc.update(key, bbox=box)
        self.refresh(key)

    def add_box(self, box):
        key = self.doc.add(box)
        self.actions["เพิ่มกรอบ"].setChecked(False)
        self.refresh(key)
        self.text_edit.setFocus()

    def set_add_mode(self, enabled):
        self.view.set_add_mode(enabled)
        if enabled:
            self.view.setFocus(Qt.FocusReason.OtherFocusReason)

    def delete_region(self):
        if self.view.active in self.doc.data:
            self.doc.delete(self.view.active)
            self.refresh()

    def undo(self):
        self.doc.undo()
        self.refresh()

    def redo(self):
        self.doc.redo()
        self.refresh()

    def save(self):
        self.apply_fields()
        try:
            self.doc.save(self.args.font, self.args.font_size)
            self.refresh()
            return True
        except Exception as error:
            self.report_error(error)
            return False

    def closeEvent(self, event):
        event.accept() if self.maybe_save() else event.ignore()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "images")
    parser.add_argument("--drafts", type=Path, default=ROOT / "GroundTruthDraft")
    parser.add_argument("--gt", type=Path, default=ROOT / "GroundTruth")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--font-size", type=int)
    args = parser.parse_args()
    if args.drafts.resolve() == args.gt.resolve():
        parser.error("Drafts and saved GT must use different folders")
    app = QApplication(sys.argv[:1])
    editor = Editor(args)
    editor.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
