#!/usr/bin/env python3
"""Review original label images and edit GT without importing an OCR model."""
import argparse
import sys
from pathlib import Path

from helpers.ocr_common import ROOT, find_images
from helpers.gt_document import GTDocument

try:
    from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal as Signal
    from PyQt5.QtGui import QColor, QKeySequence, QPainter, QPen, QPixmap
    from PyQt5.QtWidgets import (
        QAction,
        QApplication,
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFormLayout,
        QGraphicsScene,
        QGraphicsView,
        QLabel,
        QLineEdit,
        QListWidget,
        QMainWindow,
        QMessageBox,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    try:
        # Fallback for Python versions without a PyQt5 build (e.g. Python 3.12 on Jetson ARM64).
        from PySide6.QtCore import QPointF, QRectF, Qt, Signal
        from PySide6.QtGui import QAction, QColor, QKeySequence, QPainter, QPen, QPixmap
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QDoubleSpinBox,
            QFormLayout,
            QGraphicsScene,
            QGraphicsView,
            QLabel,
            QLineEdit,
            QListWidget,
            QMainWindow,
            QMessageBox,
            QSplitter,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        if __name__ == "__main__":
            print(
                "PyQt5 or PySide6 is required. On Ubuntu/Jetson with system Python: sudo apt install "
                "python3-pyqt5 python3-venv; use /usr/bin/python3 -m venv --system-site-packages "
                ".venv-jetson. With Python 3.12: python -m pip install PySide6-Essentials. "
                "See README.md for setup. On macOS/Windows: python -m pip install 'PyQt5>=5.15,<6'.",
                file=sys.stderr,
            )
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
        self.doc = doc
        self.active = None
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

        if drawing:
            drag_mode = QGraphicsView.DragMode.NoDrag
        else:
            drag_mode = QGraphicsView.DragMode.ScrollHandDrag
        self.setDragMode(drag_mode)

        if drawing:
            cursor = Qt.CursorShape.CrossCursor
        elif self.space_down:
            cursor = Qt.CursorShape.OpenHandCursor
        else:
            cursor = Qt.CursorShape.ArrowCursor
        self.viewport().setCursor(cursor)

    def focusOutEvent(self, event):
        self.space_down = False
        self.update_drag_mode()
        super().focusOutEvent(event)

    def region_color(self, key, value):
        if key == self.active:
            return QColor("#007aff")

        if value["ignore"]:
            return QColor("#777777")

        return QColor("#00aa00")

    def refresh(self):
        for item in self.overlays:
            self.scene().removeItem(item)
        self.overlays = []

        if not self.doc:
            return

        for key, value in self.doc.data.items():
            left, top, right, bottom = value["bbox"]
            color = self.region_color(key, value)

            if key == self.active:
                width = 2
            else:
                width = 1

            pen = QPen(color, width)
            pen.setCosmetic(True)

            rectangle = QRectF(left, top, right - left, bottom - top)
            rect_item = self.scene().addRect(rectangle, pen)
            self.overlays.append(rect_item)

            label = self.scene().addSimpleText(f"{key}: {value['text']}")
            label.setBrush(color)
            label.setPos(left, top)
            self.overlays.append(label)

            if key == self.active:
                size = 8 / max(self.transform().m11(), 0.01)
                corners = (
                    (left, top),
                    (right, top),
                    (left, bottom),
                    (right, bottom),
                )

                for x, y in corners:
                    handle = self.scene().addRect(
                        x - size / 2,
                        y - size / 2,
                        size,
                        size,
                        pen,
                        color,
                    )
                    self.overlays.append(handle)

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            factor = 1.2
        else:
            factor = 1 / 1.2

        scale = self.transform().m11() * factor

        if 0.02 <= scale <= 30:
            self.scale(factor, factor)
            self.refresh()

        event.accept()

    def bounded_point(self, event):
        if hasattr(event, "position"):
            position = event.position().toPoint()
        else:
            position = event.pos()

        point = self.mapToScene(position)
        x = max(0, min(point.x(), self.doc.width))
        y = max(0, min(point.y(), self.doc.height))

        return QPointF(x, y)

    def find_resize_corner(self, point, tolerance):
        if self.active not in self.doc.data:
            return None

        box = self.doc.data[self.active]["bbox"]
        left, top, right, bottom = box
        corners = (
            (left, top),
            (right, top),
            (left, bottom),
            (right, bottom),
        )

        for corner, (x, y) in enumerate(corners):
            close_x = abs(point.x() - x) <= tolerance
            close_y = abs(point.y() - y) <= tolerance

            if close_x and close_y:
                return box[:], corner

        return None

    def find_region_at(self, point):
        hits = []

        for key, value in self.doc.data.items():
            left, top, right, bottom = value["bbox"]
            rectangle = QRectF(left, top, right - left, bottom - top)

            if rectangle.contains(point):
                hits.append((key, value))

        if not hits:
            return None

        return min(
            hits,
            key=lambda pair: (
                (pair[1]["bbox"][2] - pair[1]["bbox"][0])
                * (pair[1]["bbox"][3] - pair[1]["bbox"][1])
            ),
        )

    def mousePressEvent(self, event):
        no_document = not self.doc
        not_left_button = event.button() != Qt.MouseButton.LeftButton

        if no_document or not_left_button or self.space_down:
            return super().mousePressEvent(event)

        point = self.bounded_point(event)

        if self.add_mode:
            self.gesture = ("add", None, point, None)
            event.accept()
            return

        tolerance = 10 / max(self.transform().m11(), 0.01)
        resize = self.find_resize_corner(point, tolerance)

        if resize is not None:
            box, corner = resize
            self.gesture = ("resize", self.active, point, (box, corner))
            event.accept()
            return

        hit = self.find_region_at(point)

        if hit is not None:
            key, value = hit
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
            return [
                min(start.x(), point.x()),
                min(start.y(), point.y()),
                max(start.x(), point.x()),
                max(start.y(), point.y()),
            ]

        if kind == "move":
            left, top, right, bottom = original
            dx = max(-left, min(point.x() - start.x(), self.doc.width - right))
            dy = max(-top, min(point.y() - start.y(), self.doc.height - bottom))

            return [
                left + dx,
                top + dy,
                right + dx,
                bottom + dy,
            ]

        box, corner = original
        left, top, right, bottom = box

        if corner in (0, 2):
            left = min(point.x(), right - 1)
        else:
            right = max(point.x(), left + 1)

        if corner in (0, 1):
            top = min(point.y(), bottom - 1)
        else:
            bottom = max(point.y(), top + 1)

        return [left, top, right, bottom]

    def mouseMoveEvent(self, event):
        if self.gesture:
            box = self.gesture_box(self.bounded_point(event))
            rectangle = QRectF(
                box[0],
                box[1],
                box[2] - box[0],
                box[3] - box[1],
            )

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

            if box[2] - box[0] >= 1 and box[3] - box[1] >= 1:
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

        self.args = args
        self.doc = None
        self.loading = False

        source = args.input.expanduser().resolve()
        self.images = find_images(source, recursive=True)

        if not self.images:
            raise ValueError("No source images found")

        self.source_root = source if source.is_dir() else source.parent
        self.resize(1400, 900)

        self.view = ImageView()

        self.image_picker = QComboBox()
        for image in self.images:
            relative = image.relative_to(self.source_root)
            self.image_picker.addItem(str(relative))
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
        layout.addWidget(
            QLabel(
                "ตรวจทุกบรรทัด รวมสเกลปริมาตรและข้อความย่อย\n"
                "ลากมุมเพื่อปรับกรอบ; Space+ลากเพื่อเลื่อน; ล้อเมาส์เพื่อซูม"
            )
        )
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
        self.view.fitInView(
            self.view.sceneRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        self.view.refresh()

    def maybe_save(self):
        self.apply_fields()

        if not self.doc or not self.doc.dirty:
            return True

        choice = QMessageBox.question(
            self,
            "มีงานที่ยังไม่บันทึก",
            "บันทึกงานก่อนเปลี่ยนภาพหรือปิด?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )

        if choice == QMessageBox.StandardButton.Cancel:
            return False

        if choice == QMessageBox.StandardButton.Save:
            return self.save()

        return True

    def restore_image_picker(self):
        self.image_picker.blockSignals(True)
        self.image_picker.setCurrentIndex(self.current_index)
        self.image_picker.blockSignals(False)

    def change_image(self, index):
        if not self.maybe_save():
            self.restore_image_picker()
            return

        try:
            image = self.images[index]
            relative = image.relative_to(self.source_root)
            doc = GTDocument(
                image,
                relative,
                self.args.drafts,
                self.args.gt,
            )
            self.view.load_document(doc)
            self.doc = doc
            self.actions["เพิ่มกรอบ"].setChecked(False)
            self.current_index = index
            self.refresh()
        except Exception as error:
            self.report_error(error)
            self.restore_image_picker()

    def refresh(self, selected=None):
        if not self.doc:
            return

        selected = selected or self.view.active

        self.loading = True
        self.positions.clear()
        self.keys = sorted(
            self.doc.data,
            key=lambda key: int(key[3:]),
        )

        for key in self.keys:
            if key in self.doc.ignored:
                ignored = " [ignore]"
            else:
                ignored = ""
            self.positions.addItem(
                f"{key}{ignored}: {self.doc.data[key]['text']}"
            )

        if selected in self.keys:
            row = self.keys.index(selected)
        elif self.keys:
            row = 0
        else:
            row = -1

        self.positions.setCurrentRow(row)
        self.loading = False

        self.select_row(row)
        self.view.refresh()

        if self.doc.dirty:
            saved_status = "มีการแก้ไขที่ยังไม่บันทึก"
        elif self.doc.gt_path.exists():
            saved_status = "บันทึก GT แล้ว"
        else:
            saved_status = "ยังไม่บันทึก GT"

        self.status.setText(
            f"{saved_status} | "
            f"{len(self.doc.data)} กรอบ | ignore {len(self.doc.ignored)}\n"
            "พิกัดทั้งหมดเป็นพิกเซลบนภาพต้นฉบับ"
        )

        if self.doc.dirty:
            dirty_mark = " *"
        else:
            dirty_mark = ""
        self.setWindowTitle(f"GT Editor — {self.doc.relative}{dirty_mark}")

        self.actions["Undo"].setEnabled(bool(self.doc.undo_stack))
        self.actions["Redo"].setEnabled(bool(self.doc.redo_stack))

    def select_key(self, key):
        if key in self.keys:
            self.positions.setCurrentRow(self.keys.index(key))

    def select_row(self, row):
        if self.loading or not self.doc:
            return

        self.loading = True

        if 0 <= row < len(self.keys):
            key = self.keys[row]
        else:
            key = None

        self.view.active = key
        value = self.doc.data.get(key)
        enabled = value is not None

        self.text_edit.setEnabled(enabled)
        self.ignore.setEnabled(enabled)

        if value:
            self.text_edit.setText(value["text"])
            coordinates = value["bbox"]
        else:
            self.text_edit.setText("")
            coordinates = [0] * 4

        self.ignore.setChecked(key in self.doc.ignored)

        for spin, coordinate in zip(self.coordinates, coordinates):
            spin.setEnabled(enabled)
            spin.setValue(coordinate)

        self.loading = False
        self.view.refresh()

    def apply_fields(self, *_):
        no_document = not self.doc
        no_active_region = self.doc and self.view.active not in self.doc.data

        if self.loading or no_document or no_active_region:
            return

        try:
            displayed = [spin.value() for spin in self.coordinates]
            original = self.doc.data[self.view.active]["bbox"]
            rounded = [round(value, 2) for value in original]

            if displayed == rounded:
                bbox = None
            else:
                bbox = displayed

            self.doc.update(
                self.view.active,
                text=self.text_edit.text(),
                bbox=bbox,
                ignore=self.ignore.isChecked(),
            )
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
        if self.maybe_save():
            event.accept()
        else:
            event.ignore()


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
