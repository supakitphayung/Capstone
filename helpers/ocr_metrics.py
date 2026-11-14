"""Deterministic one-to-one IoU matching and corpus OCR metrics, without OCR."""
import unicodedata

from .ocr_common import GRAY, GREEN, RED

IOU_THRESHOLD = 0.5
IGNORE_OVERLAP_THRESHOLD = 0.5

COUNT_KEYS = (
    "total_gt_positions",
    "ignored_gt_positions",
    "total_detections",
    "ignored_detections",
    "matched_positions",
    "correct_positions",
    "wrong_text_positions",
    "missed_positions",
    "extra_positions",
    "matched_character_errors",
    "matched_gt_characters",
)


def normalize_text(text):
    return unicodedata.normalize("NFC", text).strip()


def character_errors(expected, got):
    expected = normalize_text(expected)
    got = normalize_text(got)

    previous = list(range(len(got) + 1))

    for row, char in enumerate(expected, 1):
        current = [row]

        for col, other in enumerate(got, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[col] + 1,
                    previous[col - 1] + (char != other),
                )
            )

        previous = current

    return previous[-1]


def character_error_rate(expected, got):
    length = len(normalize_text(expected))
    errors = character_errors(expected, got)

    if length:
        return errors / length

    if not errors:
        return 0.0

    return None


def intersection(a, b):
    width = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return width * height


def area(box):
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def calculate_iou(a, b):
    overlap = intersection(a, b)
    union = area(a) + area(b) - overlap

    if union:
        return overlap / union

    return 0.0


def assignment_costs(overlaps, gt_count, detection_count):
    """Build a cost matrix with dummy columns for unmatched GT positions."""
    bonus = min(gt_count, detection_count) + 1
    costs = []

    for row in overlaps:
        cost_row = [
            -(bonus + value) if value >= IOU_THRESHOLD else 0.0
            for value in row
        ]
        cost_row += [0.0] * gt_count
        costs.append(cost_row)

    return costs


def match_boxes(gt_boxes, detection_boxes):
    """Maximize pair count at IoU >= .5, then total IoU (Hungarian assignment).

    Each row also has dummy columns, allowing unmatched GT. A cardinality bonus
    larger than any possible IoU sum makes the two objectives lexicographic.
    """
    n = len(gt_boxes)
    m = len(detection_boxes)

    if not n or not m:
        return []

    overlaps = [
        [calculate_iou(gt_box, detection_box) for detection_box in detection_boxes]
        for gt_box in gt_boxes
    ]
    costs = assignment_costs(overlaps, n, m)

    columns = m + n
    u = [0.0] * (n + 1)
    v = [0.0] * (columns + 1)
    p = [0] * (columns + 1)
    way = [0] * (columns + 1)

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minimum = [float("inf")] * (columns + 1)
        used = [False] * (columns + 1)

        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0

            for j in range(1, columns + 1):
                if used[j]:
                    continue

                candidate = costs[i0 - 1][j - 1] - u[i0] - v[j]

                if candidate < minimum[j]:
                    minimum[j] = candidate
                    way[j] = j0

                if minimum[j] < delta:
                    delta = minimum[j]
                    j1 = j

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

    pairs = []

    for j in range(1, m + 1):
        if not p[j]:
            continue

        gt_index = p[j] - 1
        iou = overlaps[gt_index][j - 1]

        if iou >= IOU_THRESHOLD:
            pairs.append((gt_index, j - 1, iou))

    return sorted(pairs)


def with_rates(counts):
    result = dict(counts)

    gt = counts["total_gt_positions"]
    predictions = counts["total_detections"] - counts["ignored_detections"]

    def rates(true_positives):
        if predictions:
            precision = true_positives / predictions
        else:
            precision = 0.0

        if gt:
            recall = true_positives / gt
        else:
            recall = 0.0

        if predictions + gt:
            f1 = 2 * true_positives / (predictions + gt)
        else:
            f1 = 0.0

        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    result["detection"] = rates(counts["matched_positions"])
    result["end_to_end"] = rates(counts["correct_positions"])

    chars = counts["matched_gt_characters"]
    if chars:
        result["matched_cer"] = counts["matched_character_errors"] / chars
    else:
        result["matched_cer"] = None

    if gt:
        result["accuracy_percent"] = 100 * counts["correct_positions"] / gt
    else:
        result["accuracy_percent"] = 0.0

    return result


def aggregate_metrics(reports):
    totals = {
        key: sum(report[key] for report in reports)
        for key in COUNT_KEYS
    }
    return with_rates(totals)


def overlaps_ignored_box(detection_box, ignore_boxes):
    detection_area = area(detection_box)

    if detection_area <= 0:
        return False

    return any(
        intersection(detection_box, ignore_box) / detection_area >= IGNORE_OVERLAP_THRESHOLD
        for ignore_box in ignore_boxes
    )


def evaluate_regions(gt, detections, ignored=()):
    ignored = set(ignored)

    active = [
        (key, value)
        for key, value in gt.items()
        if key not in ignored
    ]
    ignore_boxes = [
        value["bbox"]
        for key, value in gt.items()
        if key in ignored
    ]

    pairs = match_boxes(
        [value["bbox"] for _, value in active],
        [value["bbox"] for value in detections],
    )
    paired_gt = {
        index: (detection_index, iou)
        for index, detection_index, iou in pairs
    }
    paired_detections = {
        detection_index
        for _, detection_index, _ in pairs
    }
    ignored_detections = {
        index
        for index, detection in enumerate(detections)
        if index not in paired_detections
        and overlaps_ignored_box(detection["bbox"], ignore_boxes)
    }

    counts = dict.fromkeys(COUNT_KEYS, 0)
    counts.update(
        total_gt_positions=len(active),
        ignored_gt_positions=len(ignored),
        total_detections=len(detections),
        ignored_detections=len(ignored_detections),
        matched_positions=len(pairs),
    )

    details = {}
    annotations = []
    extras = []

    for index, (key, expected) in enumerate(active):
        if index not in paired_gt:
            counts["missed_positions"] += 1
            details[key] = {
                "status": "missed",
                "expected": expected["text"],
                "bbox": expected["bbox"],
            }
            annotations.append(
                {
                    "bbox": expected["bbox"],
                    "color": RED,
                    "label": f"{key} หาไม่เจอ: {expected['text']}",
                }
            )
            continue

        detection_index, iou = paired_gt[index]
        detection = detections[detection_index]
        errors = character_errors(expected["text"], detection["text"])
        correct = errors == 0

        if correct:
            counts["correct_positions"] += 1
        else:
            counts["wrong_text_positions"] += 1

        counts["matched_character_errors"] += errors
        counts["matched_gt_characters"] += len(normalize_text(expected["text"]))

        details[key] = {
            "status": "correct" if correct else "wrong_text",
            "expected": expected["text"],
            "got": detection["text"],
            "iou": iou,
            "detection_index": detection_index,
            "cer": character_error_rate(expected["text"], detection["text"]),
        }

        if correct:
            label = f"{key} ถูก: {detection['text']}"
            color = GREEN
        else:
            label = f"{key} ผิด ควรเป็น: {expected['text']} | อ่านได้: {detection['text']}"
            color = RED

        annotations.append(
            {
                "bbox": detection["bbox"],
                "color": color,
                "label": label,
            }
        )

    for index, detection in enumerate(detections):
        if index in paired_detections or index in ignored_detections:
            continue

        counts["extra_positions"] += 1
        extras.append({"detection_index": index, **detection})
        annotations.append(
            {
                "bbox": detection["bbox"],
                "color": RED,
                "label": f"det{index + 1} เกิน: {detection['text']}",
            }
        )

    for key in sorted(ignored):
        details[key] = {"status": "ignore", **gt[key]}
        annotations.append(
            {
                "bbox": gt[key]["bbox"],
                "color": GRAY,
                "label": f"{key} ignore (อ่านไม่ได้)",
            }
        )

    return (
        {
            **with_rates(counts),
            "details": details,
            "extras": extras,
            "ignored_detection_indices": sorted(ignored_detections),
            "iou_threshold": IOU_THRESHOLD,
            "ignore_overlap_threshold": IGNORE_OVERLAP_THRESHOLD,
        },
        annotations,
    )


def ranking_key(report):
    metrics = report["metrics"]
    cer = metrics["matched_cer"]

    if cer is None:
        cer = float("inf")

    return (
        -metrics["end_to_end"]["f1"],
        cer,
        report["ocr_seconds"],
        report["peak_rss_mb"],
    )
