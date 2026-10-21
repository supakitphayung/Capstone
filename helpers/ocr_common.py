"""Shared OCR settings, original-image coordinates, annotations and rendering.

Imports PaddleOCR only inside build_engine(), so the GT editor never loads it.
"""
import hashlib
import json
import math
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".ocr_cache"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
TEXT_DETECTION_MODEL = "PP-OCRv5_mobile_det"
TEXT_RECOGNITION_MODEL = "th_PP-OCRv5_mobile_rec"
BASELINE = {
    "text_detection_model_name": TEXT_DETECTION_MODEL,
    "text_recognition_model_name": TEXT_RECOGNITION_MODEL,
    "device": "cpu", "cpu_threads": 4, "enable_mkldnn": False,
    "use_doc_unwarping": False, "use_doc_orientation_classify": False,
    "use_textline_orientation": False, "text_recognition_batch_size": 1,
    "text_det_limit_side_len": 2560, "text_det_limit_type": "max",
    "text_det_thresh": 0.3, "text_det_box_thresh": 0.6,
    "text_det_unclip_ratio": 1.5, "text_rec_score_thresh": 0.0, "scale": 1.0,
    "min_text_length": 2,
}
PARAMETER_HELP = {
    "text_det_limit_side_len": "เพดานด้านยาวของ detector: เพิ่มเพื่อเก็บรายละเอียด แต่ใช้เวลาและ RAM เพิ่ม",
    "text_det_limit_type": "max จำกัดด้านยาว; min อาจขยายด้านสั้น",
    "text_det_thresh": "เกณฑ์พิกเซลข้อความ: ลดเพื่อรับข้อความจางและสิ่งรบกวนเพิ่ม",
    "text_det_box_thresh": "เกณฑ์รับกรอบ: ลดเพื่อรับกรอบเพิ่ม แต่เสี่ยงกรอบเกิน",
    "text_det_unclip_ratio": "ขยายกรอบก่อนอ่าน: เพิ่มเพื่อครอบวรรณยุกต์ แต่เสี่ยงติดบรรทัดข้างเคียง",
    "text_rec_score_thresh": "กรองคะแนนหลังอ่าน ไม่ได้เพิ่มความสามารถในการอ่าน",
    "scale": "ย่อ/ขยายภาพก่อน pipeline; ยังขึ้นกับเพดาน detector และใช้ RAM เพิ่มเมื่อขยาย",
    "min_text_length": "จำนวนอักขระที่ไม่ใช่ช่องว่างขั้นต่ำหลังอ่าน (Unicode NFC); 2 ตัดข้อความเดี่ยว และไม่รับข้อความที่มีแต่ combining marks",
}
FIXED = set(BASELINE) - set(PARAMETER_HELP)
GREEN = (0, 170, 0)
RED = (255, 0, 0)
GRAY = (100, 100, 100)
ORANGE = (190, 85, 0)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
                         + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_config(overrides=None):
    if overrides is not None and not isinstance(overrides, dict):
        raise ValueError("OCR config must be a JSON object")
    overrides = overrides or {}
    unknown = set(overrides) - set(BASELINE)
    if unknown:
        raise ValueError(f"Unknown OCR settings: {sorted(unknown)}")
    config = {**BASELINE, **overrides}
    for key in FIXED:
        if type(config[key]) is not type(BASELINE[key]) or config[key] != BASELINE[key]:
            raise ValueError(f"{key} is fixed at {BASELINE[key]!r} for comparable runs")
    for key in ("text_det_thresh", "text_det_box_thresh", "text_rec_score_thresh"):
        if type(config[key]) not in (int, float) or not 0 <= config[key] <= 1:
            raise ValueError(f"{key} must be between 0 and 1")
    for key in ("scale", "text_det_unclip_ratio", "text_det_limit_side_len"):
        if type(config[key]) not in (int, float) or not math.isfinite(config[key]) or config[key] <= 0:
            raise ValueError(f"{key} must be finite and positive")
    if type(config["text_det_limit_side_len"]) is not int:
        raise ValueError("text_det_limit_side_len must be an integer")
    if type(config["min_text_length"]) is not int or config["min_text_length"] < 1:
        raise ValueError("min_text_length must be a positive integer")
    if config["text_det_limit_type"] not in ("min", "max"):
        raise ValueError("text_det_limit_type must be min or max")
    return config


def describe_config(config):
    return {key: {"value": value, "baseline": BASELINE[key],
                  "changed": value != BASELINE[key],
                  "description": PARAMETER_HELP.get(key, "ค่าคงที่ในการทดลอง")}
            for key, value in validate_config(config).items()}


def print_config(config):
    for key, item in describe_config(config).items():
        change = f" (baseline {item['baseline']!r})" if item["changed"] else ""
        print(f"  {key} = {item['value']!r}{change}: {item['description']}", flush=True)


def add_ocr_arguments(parser):
    parser.add_argument("--config", type=Path, help="JSON object of shared OCR settings")
    parser.add_argument("--scale", type=float)
    parser.add_argument("--det-max-side", type=int, dest="text_det_limit_side_len")
    parser.add_argument("--det-limit-type", choices=["max", "min"], dest="text_det_limit_type")
    parser.add_argument("--det-thresh", type=float, dest="text_det_thresh")
    parser.add_argument("--det-box-thresh", type=float, dest="text_det_box_thresh")
    parser.add_argument("--det-unclip-ratio", type=float, dest="text_det_unclip_ratio")
    parser.add_argument("--rec-score-thresh", type=float, dest="text_rec_score_thresh")
    parser.add_argument("--min-text-length", type=int, help="Minimum non-whitespace Unicode characters after recognition (default: 2)")
    parser.add_argument("--cpu-threads", type=int, choices=[4], default=4)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--font-size", type=int)


def config_from_args(args):
    overrides = validate_config(read_json(args.config)) if args.config else {}
    for key in PARAMETER_HELP:
        value = getattr(args, key, None)
        if value is not None:
            overrides[key] = value
    if args.font_size is not None and args.font_size <= 0:
        raise ValueError("--font-size must be positive")
    return validate_config(overrides)


def build_engine(config):
    config = validate_config(config)
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(CACHE / "paddlex"))
    os.environ.setdefault("PADDLE_HOME", str(CACHE / "paddle"))
    os.environ.setdefault("HF_HOME", str(CACHE / "huggingface"))
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")
    started = time.perf_counter()
    from paddleocr import PaddleOCR
    kwargs = {key: value for key, value in config.items() if key not in ("scale", "min_text_length")}
    # Reuse an existing read-only cache without writing outside this project.
    for kind in ("detection", "recognition"):
        name = config[f"text_{kind}_model_name"]
        legacy = Path.home() / ".paddlex" / "official_models" / name
        local = CACHE / "paddlex" / "official_models" / name
        if legacy.is_dir() and not local.is_dir():
            kwargs[f"text_{kind}_model_dir"] = str(legacy)
    engine = PaddleOCR(**kwargs)
    return engine, time.perf_counter() - started


def find_images(source, output=None, cache=CACHE, recursive=False):
    source = Path(source).expanduser().resolve()
    if source.is_file():
        if source.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported image format: {source.suffix}")
        return [source]
    if not source.is_dir():
        raise FileNotFoundError(f"Input does not exist: {source}")
    excluded = [ROOT / ".venv", Path(cache).resolve()]
    if output is not None:
        excluded.append(Path(output).resolve())
    candidates = source.rglob("*") if recursive else source.iterdir()
    images = sorted(p for p in candidates if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
                    and not any(p.is_relative_to(folder) for folder in excluded))
    # stem_gt.json retains the legacy format; prevent png/jpg stem collisions.
    keys = [p.relative_to(source).with_suffix("") for p in images]
    if len(keys) != len(set(keys)):
        raise ValueError("Images with identical stems in the same folder would collide")
    return images


def read_image(path, cv2=None, np=None):
    if cv2 is None:
        import cv2
    if np is None:
        import numpy as np
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Cannot decode image: {path}")
    if image.dtype != np.uint8:
        raise ValueError("Only 8-bit images are supported")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        alpha = image[:, :, 3:4].astype(np.float32) / 255
        return np.rint(image[:, :, :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)
    return image


def languages_in(text):
    return [lang for lang, pattern in (("th", r"[\u0e00-\u0e7f]"), ("en", r"[A-Za-z]"))
            if re.search(pattern, text)]


def predict_regions(engine, image, config, roi=None, min_confidence=None):
    import cv2
    import numpy as np
    height, width = image.shape[:2]
    x, y, crop_w, crop_h = roi or (0, 0, width, height)
    if min(x, y) < 0 or min(crop_w, crop_h) <= 0 or x + crop_w > width or y + crop_h > height:
        raise ValueError(f"ROI exceeds image dimensions {width} x {height}")
    scan_w = max(1, round(crop_w * config["scale"]))
    scan_h = max(1, round(crop_h * config["scale"]))
    scan = image[y:y + crop_h, x:x + crop_w]
    if (scan_w, scan_h) != (crop_w, crop_h):
        scan = cv2.resize(scan, (scan_w, scan_h), interpolation=(
            cv2.INTER_CUBIC if config["scale"] > 1 else cv2.INTER_AREA))
    started = time.perf_counter()
    results = list(engine.predict(scan))
    elapsed = time.perf_counter() - started
    if len(results) != 1:
        raise RuntimeError(f"Expected one OCR result, got {len(results)}")
    result = results[0]
    texts, scores, polygons = result["rec_texts"], result["rec_scores"], result["rec_polys"]
    if not len(texts) == len(scores) == len(polygons):
        raise RuntimeError("Mismatched OCR text, score and polygon counts")
    regions = []
    threshold = config["text_rec_score_thresh"] if min_confidence is None else min_confidence
    for text, score, polygon in zip(texts, scores, polygons):
        score = float(score)
        if not math.isfinite(score) or score < threshold:
            continue
        text = str(text)
        characters = [char for char in unicodedata.normalize("NFC", text) if not char.isspace()]
        # A detached Thai vowel/tone mark is not a separate text region. Keep
        # marks attached to a base character, without altering the OCR text.
        if (len(characters) < config["min_text_length"]
                or all(unicodedata.category(char).startswith("M") for char in characters)):
            continue
        points = np.asarray(polygon, dtype=np.float64).copy()
        points[:, 0] = np.clip(points[:, 0] * crop_w / scan_w + x, 0, width)
        points[:, 1] = np.clip(points[:, 1] * crop_h / scan_h + y, 0, height)
        bbox = [float(points[:, 0].min()), float(points[:, 1].min()),
                float(points[:, 0].max()), float(points[:, 1].max())]
        regions.append({"text": text, "confidence": score, "polygon": points.tolist(),
                        "bbox": bbox, "languages": languages_in(text)})
    regions.sort(key=lambda region: (region["bbox"][1], region["bbox"][0]))
    for index, region in enumerate(regions, 1):
        region["id"] = index
    return regions, elapsed


def find_thai_font(requested=None):
    if requested is not None:
        requested = Path(requested).expanduser().resolve()
        if not requested.is_file():
            raise FileNotFoundError(f"Font does not exist: {requested}")
        return requested
    candidates = [ROOT / "fonts/NotoSansThai-Regular.ttf",
                  Path("/System/Library/Fonts/Supplemental/Thonburi.ttc"),
                  Path("/System/Library/Fonts/ThonburiUI.ttc"),
                  Path.home() / "Library/Fonts/THSarabunNew.ttf",
                  Path("C:/Windows/Fonts/tahoma.ttf"),
                  Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
                  Path("/usr/share/fonts/truetype/tlwg/Garuda.ttf")]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("No Thai font found. Supply --font /path/to/Thai-font.ttf")


def frame_regions(image, regions, font_path=None, font_size=None, cv2=None, np=None, roi=None):
    """Draw BGR input as BGR output; explicit region colors are RGB tuples.

    A custom label/color is used for GT/evaluation; otherwise include confidence.
    All boxes are drawn last so an adjacent label cannot hide their status color.
    """
    if cv2 is None:
        import cv2
    if np is None:
        import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    height, width = image.shape[:2]
    canvas = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(canvas)
    base_size = font_size or max(16, min(32, round(width / 60)))
    if base_size <= 0:
        raise ValueError("Font size must be positive")
    font_path = find_thai_font(font_path)
    fonts, occupied = {}, []
    padding = 3 if min(width, height) >= 10 else 0
    for index, region in enumerate(regions, 1):
        identifier = region.get("id", index)
        label = region.get("label")
        if label is None:
            label = f"{identifier}: {region['text']}"
            if "confidence" in region:
                label += f" ({region['confidence']:.2f})"
        color = tuple(region.get("color", GREEN if region.get("confidence", 1) >= 0.8 else ORANGE))
        for size in range(base_size, 0, -1):
            if size not in fonts:
                fonts[size] = ImageFont.truetype(str(font_path), size=size)
            font = fonts[size]
            bounds = draw.textbbox((0, 0), label, font=font)
            label_w = bounds[2] - bounds[0] + 2 * padding
            label_h = bounds[3] - bounds[1] + 2 * padding
            if label_w <= width and label_h <= height:
                break
        # Extremely long labels are wrapped at the minimum font size.
        if label_w > width:
            chunks, line = [], ""
            for char in label:
                if line and draw.textbbox((0, 0), line + char, font=font)[2] > width - 2 * padding:
                    chunks.append(line)
                    line = ""
                line += char
            label = "\n".join(chunks + [line])
            bounds = draw.multiline_textbbox((0, 0), label, font=font, spacing=0)
            label_w = min(width, bounds[2] - bounds[0] + 2 * padding)
            label_h = min(height, bounds[3] - bounds[1] + 2 * padding)
        left, top, _, bottom = region["bbox"]
        label_x = max(0, min(round(left), width - label_w))
        candidates = [top - label_h - 2, bottom + 2, top]
        candidates.extend(top - (step + 1) * (label_h + 2) for step in range(1, 6))
        candidates = [max(0, min(round(value), height - label_h)) for value in candidates]
        def cost(label_y):
            overlap = sum(max(0, min(label_x + label_w, r) - max(label_x, l)) *
                          max(0, min(label_y + label_h, b) - max(label_y, t))
                          for l, t, r, b in occupied)
            return overlap, abs(label_y - (top - label_h - 2))
        label_y = min(candidates, key=cost)
        rectangle = (label_x, label_y, label_x + label_w - 1, label_y + label_h - 1)
        occupied.append(rectangle)
        draw.rectangle(rectangle, fill="white", outline=color)
        draw.multiline_text((label_x + padding - bounds[0], label_y + padding - bounds[1]),
                            label, font=font, fill=color, spacing=0)
    thickness = max(1, round(max(width, height) / 1000))
    for region in regions:
        color = tuple(region.get("color", GREEN if region.get("confidence", 1) >= 0.8 else ORANGE))
        if region.get("polygon"):
            points = [tuple(point) for point in region["polygon"]]
            draw.line(points + [points[0]], fill=color, width=thickness)
        else:
            draw.rectangle(region["bbox"], outline=color, width=thickness)
    if roi:
        x, y, w, h = roi
        draw.rectangle((x, y, x + w - 1, y + h - 1), outline=(0, 100, 255), width=thickness)
    return cv2.cvtColor(np.asarray(canvas), cv2.COLOR_RGB2BGR)


def save_framed(path, image, regions, font=None, font_size=None, roi=None):
    import cv2
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", frame_regions(image, regions, font, font_size, roi=roi))
    if not ok:
        raise RuntimeError(f"Cannot encode {path}")
    encoded.tofile(path)


def annotation_paths(folder, relative):
    base = Path(folder) / Path(relative).parent / f"{Path(relative).stem}_gt"
    return tuple(Path(str(base) + suffix) for suffix in (".json", ".png"))


def validate_annotations(data, width, height):
    if not isinstance(data, dict):
        raise ValueError("GT must be a pos → {text, bbox, ignore} object")
    for key, value in data.items():
        if not re.fullmatch(r"pos[1-9][0-9]*", key) or not isinstance(value, dict):
            raise ValueError(f"Invalid GT position: {key}")
        if not isinstance(value.get("text"), str):
            raise ValueError(f"{key}: text must be a string")
        if type(value.get("ignore")) is not bool:
            raise ValueError(f"{key}: ignore must be true or false")
        box = value.get("bbox")
        if not isinstance(box, list) or len(box) != 4 or any(
                type(v) not in (float, int) or not math.isfinite(v) for v in box):
            raise ValueError(f"{key}: bbox needs four finite coordinates")
        l, t, r, b = box
        if not 0 <= l < r <= width or not 0 <= t < b <= height:
            raise ValueError(f"{key}: box outside original image or has no area")
