# Thai and English label OCR

`ocr_labels.py` reads images with OpenCV, recognizes Thai and English together
using PaddleOCR's `th` PP-OCRv5 model, draws text polygons and Thai/English
transcriptions directly on each image with Pillow, and writes
UTF-8 JSON logs. The original images are preserved.

## Run

The local virtual environment has been installed. From this folder:

```sh
.venv/bin/python ocr_labels.py
```

To set up on another machine (Python 3.9–3.13):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python ocr_labels.py
```

The first scan downloads model weights from Paddle's model server into
`.ocr_cache/`. Later scans reuse them.

## Options

```sh
# Scan one image
.venv/bin/python ocr_labels.py --input "LRUSP800_B_R2_B - Copy.png"

# Include subfolders and keep more low-confidence results
.venv/bin/python ocr_labels.py --recursive --min-confidence 0.3

# Enlarge small text before OCR
.venv/bin/python ocr_labels.py --scale 1.5

# Scan a fixed rectangle: x y width height
.venv/bin/python ocr_labels.py --roi 100 100 600 700

# Choose a Thai font and label size
.venv/bin/python ocr_labels.py --font "/path/to/NotoSansThai-Regular.ttf" --font-size 24
```

Each run saves a separate folder under `ocr_output/` containing:

- `framed/`: original-sized images with polygons, recognized Thai/English text,
  region IDs and confidence scores rendered directly on the image.
- `json/`: a JSON document per image with text, confidence, polygons, bounding
  boxes, image dimensions, and processing time. Thai remains readable in UTF-8.
- `run.json`: batch status and links to each image's artifacts.
- `run.log`: processing messages and errors.

Green boxes have confidence of at least 0.8; orange boxes have lower confidence.
Box IDs match the JSON `regions` entries. Coordinates use the original image,
with the origin at the upper left. `bbox` is `[left, top, right, bottom]`.
`languages` labels are based on Thai/Latin characters in recognized text.
Reading order is approximately top-to-bottom; multiple columns may need review.
Recognition confidence is a model score, not a guarantee of correct text.
An image with no retained text has status `no_text`. Failed images are logged,
and processing continues. Exit codes: 0 for a completed batch, 1 for OCR errors,
and 2 for invalid input.

Thai text uses an automatically detected Thai font (Thonburi on macOS, Tahoma
on Windows, or Noto Sans Thai/Garuda on Linux). You can provide `--font` or place
`NotoSansThai-Regular.ttf` in the project's `fonts/` folder. Text labels use
white backgrounds and automatically shrink to fit within the image width.

Model reference: [PaddleOCR general OCR documentation](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/OCR.en.md).
