"""Deterministic one-to-one IoU matching and corpus OCR metrics, without OCR."""
import unicodedata

from .ocr_common import GRAY, GREEN, RED

IOU_THRESHOLD = 0.5
IGNORE_OVERLAP_THRESHOLD = 0.5
COUNT_KEYS = ("total_gt_positions", "ignored_gt_positions", "total_detections",
              "ignored_detections", "matched_positions", "correct_positions",
              "wrong_text_positions", "missed_positions", "extra_positions",
              "matched_character_errors", "matched_gt_characters")


def normalize_text(text):
    return unicodedata.normalize("NFC", text).strip()


def character_errors(expected, got):
    expected, got = normalize_text(expected), normalize_text(got)
    previous = list(range(len(got) + 1))
    for row, char in enumerate(expected, 1):
        current = [row]
        for col, other in enumerate(got, 1):
            current.append(min(current[-1] + 1, previous[col] + 1,
                               previous[col - 1] + (char != other)))
        previous = current
    return previous[-1]


def character_error_rate(expected, got):
    length = len(normalize_text(expected))
    errors = character_errors(expected, got)
    return errors / length if length else (0.0 if not errors else None)


def intersection(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def area(box):
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def calculate_iou(a, b):
    overlap = intersection(a, b)
    union = area(a) + area(b) - overlap
    return overlap / union if union else 0.0


def match_boxes(gt_boxes, detection_boxes):
    """Maximize pair count at IoU >= .5, then total IoU (Hungarian assignment).

    Each row also has dummy columns, allowing unmatched GT. A cardinality bonus
    larger than any possible IoU sum makes the two objectives lexicographic.
    """
    n, m = len(gt_boxes), len(detection_boxes)
    if not n or not m:
        return []
    overlaps = [[calculate_iou(a, b) for b in detection_boxes] for a in gt_boxes]
    bonus = min(n, m) + 1
    costs = [[-(bonus + value) if value >= IOU_THRESHOLD else 0.0 for value in row]
             + [0.0] * n for row in overlaps]
    columns = m + n
    u, v = [0.0] * (n + 1), [0.0] * (columns + 1)
    p, way = [0] * (columns + 1), [0] * (columns + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minimum = [float("inf")] * (columns + 1)
        used = [False] * (columns + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta, j1 = float("inf"), 0
            for j in range(1, columns + 1):
                if not used[j]:
                    candidate = costs[i0 - 1][j - 1] - u[i0] - v[j]
                    if candidate < minimum[j]:
                        minimum[j], way[j] = candidate, j0
                    if minimum[j] < delta:
                        delta, j1 = minimum[j], j
            for j in range(columns + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minimum[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    return sorted((p[j] - 1, j - 1, overlaps[p[j] - 1][j - 1])
                  for j in range(1, m + 1) if p[j] and overlaps[p[j] - 1][j - 1] >= IOU_THRESHOLD)


def with_rates(counts):
    result = dict(counts)
    gt = counts["total_gt_positions"]
    predictions = counts["total_detections"] - counts["ignored_detections"]
    def rates(true_positives):
        precision = true_positives / predictions if predictions else 0.0
        recall = true_positives / gt if gt else 0.0
        return {"precision": precision, "recall": recall,
                "f1": 2 * true_positives / (predictions + gt) if predictions + gt else 0.0}
    result["detection"] = rates(counts["matched_positions"])
    result["end_to_end"] = rates(counts["correct_positions"])
    chars = counts["matched_gt_characters"]
    result["matched_cer"] = counts["matched_character_errors"] / chars if chars else None
    result["accuracy_percent"] = 100 * counts["correct_positions"] / gt if gt else 0.0
    return result


def aggregate_metrics(reports):
    return with_rates({key: sum(report[key] for report in reports) for key in COUNT_KEYS})


def evaluate_regions(gt, detections, ignored=()):
    ignored = set(ignored)
    active = [(key, value) for key, value in gt.items() if key not in ignored]
    ignore_boxes = [value["bbox"] for key, value in gt.items() if key in ignored]
    pairs = match_boxes([value["bbox"] for _, value in active], [value["bbox"] for value in detections])
    paired_gt = {i: (j, iou) for i, j, iou in pairs}
    paired_detections = {j for _, j, _ in pairs}
    ignored_detections = {j for j, det in enumerate(detections) if j not in paired_detections
                          and area(det["bbox"]) > 0 and any(
                              intersection(det["bbox"], box) / area(det["bbox"]) >= IGNORE_OVERLAP_THRESHOLD
                              for box in ignore_boxes)}
    counts = dict.fromkeys(COUNT_KEYS, 0)
    counts.update(total_gt_positions=len(active), ignored_gt_positions=len(ignored),
                  total_detections=len(detections), ignored_detections=len(ignored_detections),
                  matched_positions=len(pairs))
    details, annotations, extras = {}, [], []
    for i, (key, expected) in enumerate(active):
        if i not in paired_gt:
            counts["missed_positions"] += 1
            details[key] = {"status": "missed", "expected": expected["text"], "bbox": expected["bbox"]}
            annotations.append({"bbox": expected["bbox"], "color": RED,
                                "label": f"{key} หาไม่เจอ: {expected['text']}"})
            continue
        j, iou = paired_gt[i]
        det = detections[j]
        errors = character_errors(expected["text"], det["text"])
        correct = errors == 0
        counts["correct_positions" if correct else "wrong_text_positions"] += 1
        counts["matched_character_errors"] += errors
        counts["matched_gt_characters"] += len(normalize_text(expected["text"]))
        details[key] = {"status": "correct" if correct else "wrong_text",
                        "expected": expected["text"], "got": det["text"], "iou": iou,
                        "detection_index": j, "cer": character_error_rate(expected["text"], det["text"])}
        label = (f"{key} ถูก: {det['text']}" if correct else
                 f"{key} ผิด ควรเป็น: {expected['text']} | อ่านได้: {det['text']}")
        annotations.append({"bbox": det["bbox"], "color": GREEN if correct else RED, "label": label})
    for j, det in enumerate(detections):
        if j not in paired_detections and j not in ignored_detections:
            counts["extra_positions"] += 1
            extras.append({"detection_index": j, **det})
            annotations.append({"bbox": det["bbox"], "color": RED,
                                "label": f"det{j + 1} เกิน: {det['text']}"})
    for key in sorted(ignored):
        details[key] = {"status": "ignore", **gt[key]}
        annotations.append({"bbox": gt[key]["bbox"], "color": GRAY, "label": f"{key} ignore (อ่านไม่ได้)"})
    return {**with_rates(counts), "details": details, "extras": extras,
            "ignored_detection_indices": sorted(ignored_detections),
            "iou_threshold": IOU_THRESHOLD, "ignore_overlap_threshold": IGNORE_OVERLAP_THRESHOLD}, annotations


def ranking_key(report):
    metrics = report["metrics"]
    cer = metrics["matched_cer"]
    return (-metrics["end_to_end"]["f1"], cer if cer is not None else float("inf"),
            report["ocr_seconds"], report["peak_rss_mb"])
