# Flow การรันสั้นๆ
```sh
python create_gt.py # สร้าง GroundTruthDraft

python gt_editor.py # edit groundTruth

python evaluate_ocr.py # เทียบ ocr กับ groundTruth
```

# ตรวจ GT และทดลอง Thai/English OCR ด้วย PP-OCRv5 Mobile

ลำดับงาน: **สร้างร่าง → แก้ไขใน GUI แล้วบันทึก → ประเมิน OCR → ทดลองพารามิเตอร์กับ GT คงที่**
ยังไม่มีการ fine-tune โมเดล ทุกสคริปต์ใช้ค่าร่วมจาก `helpers/ocr_common.py`:

```python
text_detection_model_name="PP-OCRv5_mobile_det"
text_recognition_model_name="th_PP-OCRv5_mobile_rec"
```

ผู้พัฒนารายงาน detector Mobile v5 Hmean 79.0% เทียบกับ v4 63.8% บนชุดประเมินของผู้พัฒนา
([เอกสาร detector](https://www.paddleocr.ai/main/en/version3.x/module_usage/text_detection.html))
recognizer ภาษาไทยรองรับไทย อังกฤษ และตัวเลข
([เอกสาร recognition](https://www.paddleocr.ai/main/en/version3.x/module_usage/text_recognition.html))
คะแนนเหล่านี้ไม่ใช่คะแนนภาพฉลากของเรา ต้องวัดด้วย GT ที่คนตรวจแล้ว

## โครงสร้างโปรเจกต์

สคริปต์ที่เรียกใช้งานอยู่ใน root ส่วนโค้ดที่ใช้ร่วมกันอยู่ใน `helpers/`:

```text
Capstone/
├── create_gt.py          # สร้างร่างเฉลยด้วย OCR
├── gt_editor.py          # GUI แก้ไขและบันทึก GT
├── evaluate_ocr.py       # รัน OCR เทียบกับ GT
├── experiment_ocr.py     # ทดลองพารามิเตอร์หลายชุด
├── ocr_labels.py         # สแกน OCR ทั่วไป
├── helpers/
│   ├── __init__.py       # กำหนดให้ helpers เป็น Python package
│   ├── ocr_common.py     # ค่าตั้งโมเดล อ่าน/เขียนข้อมูล และวาดภาพ
│   ├── ocr_metrics.py    # จับคู่กรอบและคำนวณคะแนน
│   └── gt_document.py    # จัดการข้อมูล GT และ Undo/Redo
├── images/              # ภาพต้นฉบับ
├── GroundTruthDraft/    # ร่างจาก OCR
├── README.md
└── requirements.txt
```

`GroundTruth/` จะถูกสร้างเมื่อบันทึกงานใน GUI ส่วนโฟลเดอร์ผลลัพธ์จะถูกสร้างเมื่อรันแต่ละขั้น
เรียกสคริปต์จาก root ตามคำสั่งด้านล่างได้เลย โค้ดใน `helpers/` ถูก import อัตโนมัติ
เส้นทางเริ่มต้นของภาพ GT ผลลัพธ์ ฟอนต์ และแคชโมเดลอ้างอิง root ของโปรเจกต์

## ติดตั้งและลองหนึ่งภาพ

รันจากโฟลเดอร์นี้ ใช้ Python 3.12 กับ virtual environment:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# ดาวน์โหลด weights ที่ยังไม่มี แล้วลองภาพต้นฉบับหนึ่งภาพก่อนรันหลายชุด
.venv/bin/python ocr_labels.py --input images/1.png
```

PaddleOCR/PaddlePaddle ใช้เวอร์ชันที่ตรึงใน `requirements.txt` GUI ใช้ PySide6
weights และแคชใหม่เก็บใน `.ocr_cache/` และอ่าน weights ที่มีอยู่ใน `~/.paddlex/official_models/` ได้
ต้องมีอินเทอร์เน็ตในการติดตั้งและดาวน์โหลดครั้งแรก โดยเฉพาะ `PP-OCRv5_mobile_det`
เมื่อมี weights ครบแล้วใช้แคชรันออฟไลน์ได้ ไม่สลับไปใช้ detector รุ่นอื่นเมื่อดาวน์โหลดไม่สำเร็จ

ฟอนต์ไทยเลือกอัตโนมัติ: Thonburi บน Mac, Tahoma บน Windows, Noto Sans Thai/Garuda บน Linux
หรือใช้ `--font /path/to/NotoSansThai-Regular.ttf` และ `--font-size 24`

## สร้างร่างและตรวจแก้

```sh
# ร่างทั้ง 9 ภาพ เก็บใน GroundTruthDraft/ ไม่เขียนลง GroundTruth/
.venv/bin/python create_gt.py

# เปิดภาพต้นฉบับพร้อมกรอบ ข้อความ และรายการตำแหน่ง โดยไม่โหลด PaddleOCR
.venv/bin/python gt_editor.py
```

เลือกภาพจากรายการด้านขวา เลือกกรอบจากภาพหรือรายการข้อความ แล้วแก้ข้อความและพิกัด
ล้อเมาส์ซูม; ลากพื้นที่ว่างหรือ Space+ลากบนภาพเพื่อเลื่อน; ลากกรอบเพื่อย้าย;
ลากมุมสีน้ำเงินเพื่อปรับขนาด; กด **เพิ่มกรอบ** แล้วลากบนภาพเพื่อเพิ่มตำแหน่งที่ตกหล่น
ใช้ **ลบกรอบ**, **Undo/Redo** หรือ Cmd+Z/Cmd+Shift+Z ได้
พิกัดในช่องและไฟล์เป็นพิกเซลบนภาพต้นฉบับเสมอ ไม่ขึ้นกับการซูม

ตรวจทุกข้อความ รวมสเกลปริมาตร ข้อความเล็ก สระและวรรณยุกต์
ใช้กรอบตามบรรทัดหรือกลุ่มข้อความที่แยกกันชัดเจน ไม่รวมหลายบรรทัดที่อ่านแยกกันได้
ใช้ `ignore` เฉพาะตำแหน่งที่คนอ่านไม่ได้จริง จำนวน ignore แสดงแยกในรายงาน
กด **บันทึก** หรือ Cmd+S เพื่อเก็บ GT แล้วใช้ประเมินได้ทันที ไม่มีขั้นตอนยืนยันตรวจครบ
เมื่อแก้ข้อความ กรอบ หรือ ignore ให้บันทึกอีกครั้งก่อนรันประเมิน
เปลี่ยนภาพหรือปิดหน้าต่างขณะมีงานค้าง โปรแกรมจะให้เลือกบันทึก/ทิ้ง/ยกเลิก

```text
GroundTruthDraft/
  1_gt.json            # pos → {text, bbox}: ร่างจาก OCR
  1_gt.draft.json      # config, confidence ของ OCR และเวลารัน
  1_gt.png             # preview พร้อม confidence
GroundTruth/
  1_gt.json            # pos → {text, bbox, ignore}: งานที่บันทึกแล้ว
  1_gt.png             # preview งานแก้ ไม่มี confidence ของมนุษย์
```

`bbox` คือ `[left, top, right, bottom]` จุดเริ่มอยู่มุมซ้ายบน
ID `pos` คงที่ระหว่างแก้ ลบแล้วอาจมีเลขข้าม ใช้ ID เดิมเชื่อมรายงานได้
เปิด GUI ครั้งถัดไปจะเลือกงานใน `GroundTruth/` ก่อนร่างเดิม
หากยังไม่มีร่าง สามารถเพิ่มกรอบด้วยมือจากภาพต้นฉบับได้
เก็บ `ignore` เป็น boolean ในแต่ละตำแหน่งของ GT โดยตรง ไม่มีไฟล์สถานะตรวจทานแยก

```json
{"pos1": {"text": "ปริมาตร 1000 mL", "bbox": [20, 30, 300, 70], "ignore": false}}
```

```sh
# สร้างร่างภาพเดียว หรือสร้างร่างเดิมใหม่โดยไม่แตะงานคนตรวจ
.venv/bin/python create_gt.py --input images/1.png
.venv/bin/python create_gt.py --overwrite
```

## ประเมินชุดเดียว

```sh
# ประเมินภาพที่มี GT บันทึกอยู่ใน GroundTruth/
.venv/bin/python evaluate_ocr.py

# ระบุภาพและปรับค่าด้วย CLI ที่ใช้ร่วมกับ ocr_labels.py และ create_gt.py
.venv/bin/python evaluate_ocr.py --ids 1 2 3 4 8 9 \
  --det-max-side 1920 --det-thresh 0.2 --det-box-thresh 0.5 --det-unclip-ratio 2.0
```

ผลอยู่ใน `evaluation_output/<เวลา>/` มีสำเนาภาพต้นฉบับและ GT ใน `dataset/`
ภาพที่ไม่มี GT จะถูกระบุใน `skipped.json`; ถ้ายังไม่ได้บันทึก GT เลยจะหยุดด้วย exit code 2
`evaluation/report.json` มีคะแนนรวมและรายภาพ พร้อม detections เวลาโหลดโมเดล เวลา OCR และ peak RSS
ภาพพร้อมป้ายอยู่ใน `evaluation/framed/` JSON รายภาพอยู่ใน `evaluation/images/`

## ทดลองพารามิเตอร์หลายชุด

```sh
# ดูคำอธิบาย ค่าจริง และค่าที่เปลี่ยนจาก baseline โดยไม่โหลดโมเดล/ไม่ต้องมี GT
.venv/bin/python experiment_ocr.py --dry-run

# รอบอัตโนมัติ: baseline + เปลี่ยนทีละค่า + ชุดแก้ปัญหาเฉพาะ รวม 12 ชุด
# ต้องบันทึก GT ทั้ง 9 ภาพก่อนเริ่ม แล้วประเมิน holdout เฉพาะชุดที่เลือก
.venv/bin/python experiment_ocr.py

# ทดลองเฉพาะชุดปรับค่า หากยังไม่ต้องการประเมิน holdout
.venv/bin/python experiment_ocr.py --tune-only

# JSON ที่มีหนึ่งหรือหลายชุด; ตัวอย่างนี้มี 3 ชุด และไม่เพิ่มชุดรวมอัตโนมัติ
.venv/bin/python experiment_ocr.py --experiments experiments/example.json
```

แต่ละชุดโหลดโมเดลใหม่ใน subprocess ของตัวเอง รันทีละชุด
ค่า timeout เริ่มต้น 1,800 วินาทีต่อชุด ปรับได้ด้วย `--timeout`
ชุดที่ timeout, crash, โหลดโมเดลไม่ได้ หรือรันภาพไม่ครบ ถูกระบุ `failed` และไม่มีสิทธิ์เป็นชุดดีที่สุด

| พารามิเตอร์ | ผลเมื่อปรับ | Baseline / ค่าที่ทดลอง |
|---|---|---|
| `text_det_limit_side_len` | ลอง 1280 สำหรับตัวใหญ่ และ 3200 เพื่อเก็บรายละเอียด/ช่องว่างบรรทัดไทย; ค่าสูงใช้เวลาและ RAM เพิ่ม | 2560 / 1280, 2560, 3200 |
| `text_det_limit_type` | `max` จำกัดด้านยาว; `min` อาจขยายด้านสั้น | `max` |
| `text_det_thresh` | ลดเพื่อเก็บสระ/วรรณยุกต์จาง; เพิ่มเพื่อทดลองลดส่วนที่เชื่อมระหว่างบรรทัด | 0.3 / 0.2, 0.3, 0.4 |
| `text_det_box_thresh` | ลดแล้วรับกรอบเพิ่ม แต่อาจมีกรอบเกิน | 0.6 / 0.3, 0.5, 0.6 |
| `text_det_unclip_ratio` | ลดการขยายกรอบสำหรับบรรทัดชิด/กรอบชนกัน; ลอง 1.8 ในชุดเก็บสระ/วรรณยุกต์ | 1.5 / 1.0, 1.2, 1.5, 1.8 |
| `text_rec_score_thresh` | กรองคำตอบหลังอ่าน ไม่ได้ทำให้อ่านเก่งขึ้น | 0.0 |
| `scale` | ย่อ/ขยายภาพก่อน pipeline และยังขึ้นกับเพดาน detector | 1.0; เปลี่ยนเองได้ |
| `min_text_length` | กรองผลหลังอ่านให้มีอักขระที่ไม่ใช่ช่องว่างอย่างน้อย 2 ตัว และตัดผลที่มีแต่ combining marks | 2 ทุกชุดอัตโนมัติ |

เพิ่มชุดผสมเพื่อทดสอบปัญหาจากภาพโดยตรง:

| ชุด | ด้านยาวสูงสุด | Pixel threshold | Box threshold | Unclip ratio | จุดที่ต้องการทดสอบ |
|---|---:|---:|---:|---:|---|
| `tight-thai-lines` | 3200 | 0.4 | 0.5 | 1.0 | บรรทัดไทยชิดกัน โดยเก็บรายละเอียดและลดการขยายกรอบ |
| `thai-diacritics` | 3200 | 0.2 | 0.5 | 1.8 | เก็บสระ/วรรณยุกต์ให้ติดกับข้อความหลัก |
| `large-touching-text` | 1280 | 0.4 | 0.3 | 1.0 | ตัวใหญ่และกรอบใกล้กัน โดยลองย่อภาพ detector และลด padding |

ค่าข้างต้นเป็นสมมติฐานสำหรับทดลอง ต้องวัดกับ GT ก่อนสรุปว่าชุดใดช่วยจริง
ความหมายของ threshold และการขยายกรอบอ้างอิง [เอกสาร PaddleOCR](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html)
ตัวกรอง `min_text_length` ทำงานร่วมกันใน `create_gt.py`, `evaluate_ocr.py` และตัวทดลอง
โดยนับ Unicode code points หลัง NFC และไม่นับช่องว่าง เช่น `9`, `N`, `่` จะถูกตัด แต่ `ยา`, `ก้`, `100 ml` ยังอยู่
ตัวกรองนี้ไม่รวมวรรณยุกต์กลับเข้าคำเดิม และไม่ช่วยกู้ข้อความที่ detector หาไม่เจอ
GT ที่เป็นอักขระเดียวยังถูกนับคะแนนตามเดิม จึงอาจได้คะแนนลดลงหากมีข้อความเดี่ยวที่ต้องอ่านจริง
ใช้ `--min-text-length 1` ในสคริปต์ OCR หรือ `"min_text_length": 1` ใน JSON เมื่อต้องการรับข้อความเดี่ยว
ผลที่มีแต่ combining marks ยังคงถูกตัด และค่า `min_text_length` ถูกบันทึกใน config/รายงานเพื่อทำซ้ำได้

ทุกชุดคง CPU 4 เธรด, recognition batch size 1, ปิด MKLDNN, unwarping และ orientation ทุกชนิด
`helpers/ocr_common.py` ตรวจและปฏิเสธ config ที่เปลี่ยนค่าคงที่เหล่านี้

12 ชุดเริ่มต้นคือ baseline, ค่าที่ต่างจาก baseline อย่างละ 2 ค่าใน 4 พารามิเตอร์ และชุดผสมเฉพาะปัญหา 3 ชุด
จากนั้นเลือกค่าที่ชนะของแต่ละพารามิเตอร์จากผล tune มารวมอีกหนึ่งชุดถ้ายังไม่ซ้ำ
ขั้นตอนรวมพิจารณาเฉพาะ baseline และชุดที่เปลี่ยนทีละพารามิเตอร์ ส่วนชุดผสมมีสิทธิ์เป็นชุดดีที่สุดตามปกติ
หาก baseline ไม่สำเร็จ จะไม่สร้างชุดรวม ใช้ `--no-combine` ปิดขั้นตอนรวมได้
การเลือกทุกขั้นใช้ end-to-end F1 สูงสุด ตามด้วย matched CER ต่ำสุด เวลา OCR ต่ำสุด และ RAM ต่ำสุด

ใช้ split ใน `experiments/dataset_split.json` แยกตามกลุ่มผลิตภัณฑ์:

| ชุด | ภาพ | กลุ่มผลิตภัณฑ์ |
|---|---|---|
| tune | 1, 2, 3, 4, 8, 9 | 0.45NSSBP1000, D50WUSP500, LRUSP800 |
| holdout | 5, 6, 7 | Dextran40USP500, LRUSP250 |

ตัวรันตรวจไม่ให้กลุ่มเดียวกันอยู่ทั้งสองชุด และบันทึกชุดที่เลือกก่อนอ่านคะแนน holdout
ไม่ใช้ holdout เพื่อเลือกพารามิเตอร์หรือเลือกชุดรวม ถ้าตัดสินใจปรับค่าโดยดู holdout ชุดนี้แล้ว
ควรเตรียม holdout ใหม่สำหรับการตรวจครั้งถัดไป

ผลอยู่ใน `experiment_output/<เวลา>/`:

- `dataset/`: สำเนาภาพต้นฉบับและ GT พร้อม hashes และ `manifest.json`
- `requested_trials.json`, `dataset_split.json`: ค่าที่ขอทดลองและ split ที่ใช้จริง
- `trials/<ชื่อ>/`: `config.json`, `job.json`, `worker.log`, `report.json`, `images/` และ `framed/`
- `comparison.json`, `comparison.md`: คะแนนและสถานะเปรียบเทียบทุกชุด
- `selected_config.json`: config เต็มของชุดที่เลือกจาก tune ใช้กับสคริปต์อื่นด้วย `--config` ได้
- `holdout/`: ผลเฉพาะชุดที่เลือก ไม่มีผลต่ออันดับจาก tune

ทุกชุดในรอบเดียวกันใช้ snapshot เดียวกันและตรวจ hash ก่อนรัน
การแก้ GT ไม่เปลี่ยนผลรอบเก่า รันคำสั่งใหม่เพื่อเริ่มการเปรียบเทียบรอบใหม่
ห้ามแก้ไฟล์ใน `dataset/` ของรอบที่กำลังเปรียบเทียบ

JSON สำหรับทดลองชุดเดียว:

```json
{"experiments": [{"name": "my-setting", "parameters": {"text_det_thresh": 0.2, "scale": 1.0}}]}
```

`--config` ในสคริปต์ OCR เดิมรับ JSON object ของพารามิเตอร์โดยตรง ไม่ใช่ wrapper `experiments`
เช่น `{"text_det_thresh": 0.2}` หรือ `selected_config.json`
ค่า CLI ที่ระบุจะทับค่าใน `--config`; ค่าที่ไม่ได้ระบุใช้ baseline

## วิธีคิดคะแนนและรูปผลลัพธ์

จับคู่กรอบหนึ่งต่อหนึ่งที่ **IoU ≥ 0.5** โดยเพิ่มจำนวนคู่ให้มากที่สุดก่อน แล้วเพิ่มผลรวม IoU
ใช้เกณฑ์เดียวกันทุกชุด ไม่อาศัยความถูกต้องของข้อความในการจับคู่
กรอบ ignore ไม่เข้าตัวหาร GT หลังจับคู่ข้อความที่อ่านได้แล้ว จะไม่นับ detection ที่เหลือ
ซึ่งพื้นที่อย่างน้อย 50% ของตัว detection อยู่ในกรอบ ignore (intersection / detection area)
รายงานจำนวน ignored GT และ ignored detections แยกต่างหาก

- detection precision/recall/F1: คู่ที่จับตำแหน่งได้เทียบกับจำนวน GT และ detections ที่นับคะแนน
- matched CER: ผลรวม Levenshtein edits หารด้วยจำนวนอักขระ GT ในคู่ที่จับได้ อาจเกิน 1 หรือ 100%
  แสดง `null` ถ้าไม่มีอักขระ GT ในคู่ที่จับได้
- end-to-end precision/recall/F1: คู่ต้องผ่านทั้งตำแหน่งและข้อความตรงกันทั้งหมด
  ข้อความผิด ข้อความตกหล่น และกรอบเกินจึงลดคะแนน
- `accuracy_percent`: จำนวนตำแหน่งถูกทั้งหมด / จำนวน GT ที่นับคะแนน × 100 คงไว้ประกอบผลเดิม

ข้อความใช้ Unicode NFC และตัดช่องว่างหัวท้ายเท่านั้น ยังตรวจช่องว่างภายใน ตัวพิมพ์ ตัวเลข และเครื่องหมาย
CER ใช้ Unicode code points ไม่ใช่ grapheme clusters คะแนนรวมเป็น micro average จาก counts/อักขระ
ถ้าไม่มี GT และ predictions ที่นับคะแนน F1 เป็น 0 ไม่ใช่ 1

ทุกสคริปต์วาดภาพผ่าน `helpers/ocr_common.py` ใช้ฟอนต์ไทย ป้ายอยู่ในขอบภาพและพยายามลดการทับกัน
พื้นที่แน่นอาจยังมีป้ายทับกันได้ รูปเป็นขนาดต้นฉบับ:

| ผล | การแสดง |
|---|---|
| ร่าง OCR | กรอบ ID ข้อความ และ confidence; เขียว ≥ 0.8 ส้ม < 0.8 |
| GT จาก GUI | ข้อความ/กรอบที่บันทึก ไม่มี confidence ที่สมมติขึ้น |
| อ่านถูก | เขียว พร้อมข้อความที่อ่านได้ |
| อ่านผิด | แดง พร้อมข้อความคาดหวังและข้อความที่อ่านได้ |
| หาไม่เจอ | แดงที่กรอบ GT พร้อมข้อความที่คาดหวัง |
| เกิน | แดงที่ detection พร้อมป้ายว่าเกิน |
| ignore | เทาและรายงานจำนวนแยก |

ใช้ภาพต้นฉบับทำ OCR เสมอ ภาพติดป้ายเป็นผลสำหรับตรวจดูเท่านั้น

## ใช้สคริปต์ OCR ทั่วไป

```sh
.venv/bin/python ocr_labels.py                         # images/ ทั้งโฟลเดอร์
.venv/bin/python ocr_labels.py --recursive --min-confidence 0.3
.venv/bin/python ocr_labels.py --input images/1.png --scale 1.5
.venv/bin/python ocr_labels.py --input images/1.png --roi 100 100 600 700
.venv/bin/python ocr_labels.py --config experiment_output/<รอบ>/selected_config.json
```

เก็บผลแต่ละรอบใน `ocr_output/<เวลา>/framed/`, `json/`, `run.json`, `run.log`
มีข้อความ คะแนน กรอบ พิกัดต้นฉบับ ขนาดภาพ ภาษา และเวลา
`response_time_seconds` รายภาพนับเฉพาะ `predict`;
`elapsed_seconds` รวมอ่านภาพ/เตรียมภาพ/วาด/บันทึกภาพ;
เวลารวมใน `run.json` รวมการโหลดโมเดลด้วย
`--min-confidence` เป็นตัวกรองเพิ่มเติมเฉพาะสคริปต์ OCR ทั่วไป ไม่ใช้ในตัวประเมิน
Exit codes ของ CLI: 0 สำเร็จ, 1 รันไม่สำเร็จหรือมีบางชุดล้มเหลว, 2 input/config ไม่ถูกต้อง

## ทดสอบ

```sh
.venv/bin/python -m unittest discover -s tests -v
```

`tests/test_gt_workflow.py` ใช้ Qt offscreen ตรวจเพิ่มกรอบจาก toolbar,
กรณี Space ค้างหลังเปลี่ยนโฟกัส, เพิ่ม/ย้าย/ปรับกรอบหลังซูม, Undo/Redo,
save/reopen, ignore และการนำ GT ที่บันทึกแล้วไปประเมินได้ทันที
integration test ใช้ OCR จำลองเพื่อทดสอบระบบรายงาน ไม่ใช่ผลความแม่นยำของโมเดลจริง
คำสั่ง OCR หนึ่งภาพด้านบนคือการตรวจรับโมเดลจริงก่อนเริ่มรอบทดลอง
