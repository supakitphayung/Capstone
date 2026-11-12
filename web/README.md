# OCR Workbench

เว็บ local สำหรับเรียก `create_gt.py`, `gt_editor.py`, `evaluate_ocr.py` และ `experiment_ocr.py` ผ่าน CLI เดิม ใช้ React + TypeScript + Vite + Tailwind CSS และ FastAPI โดยไม่แก้ไข script หรือ helpers ของ OCR

## เริ่มใช้งาน

รันคำสั่งจาก root ของโปรเจกต์ ใช้ virtual environment เดิมที่ติดตั้ง dependencies ของ OCR แล้ว:

```sh
.venv/bin/python -m pip install -r web/backend/requirements.txt
```

ติดตั้งและ build frontend:

```sh
cd web/frontend
npm ci
npm run build
cd ../..
```

เริ่ม backend ซึ่งเสิร์ฟเว็บที่ build แล้วด้วย:

```sh
.venv/bin/python -m uvicorn web.backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

เปิด **http://127.0.0.1:8000** และเปิด terminal นี้ไว้ระหว่างใช้งาน ระบบออกแบบสำหรับ backend worker เดียวเพื่อให้การจองงาน OCR สอดคล้องกัน ไม่ใช้ `--reload` ขณะมีงานทำงานอยู่

เครื่องใหม่ให้ติดตั้ง OCR ตาม README หลักก่อน Node.js ต้องรองรับ Vite รุ่นที่ระบุใน package-lock (Node 22.12+ หรือรุ่นใหม่กว่าที่รองรับ) ตัวเว็บใช้ฟอนต์จากระบบและไม่เรียกบริการ OCR ภายนอก

## รันด้วย Docker (CPU)

ต้องมี Docker Desktop หรือ Docker Engine พร้อม Compose รันจาก root ของโปรเจกต์:

```sh
docker compose up --build
```

เปิด **http://127.0.0.1:8000** หยุดด้วย `Ctrl+C` หรือ `docker compose down` ครั้งแรกใช้เวลาหลายนาทีเพราะต้องดาวน์โหลด PaddlePaddle (image ประมาณ 1.7GB)

- โฟลเดอร์ `images/`, `GroundTruthDraft/`, `GroundTruth/`, `evaluation_output/`, `experiment_output/`, `experiments/`, `.ocr_cache/` และ `.webui/` ผูกกับเครื่องจริง ข้อมูลและผลลัพธ์จึงอยู่ที่เดิมแม้ลบ container
- ถ้าพอร์ต 8000 ถูกใช้อยู่ ให้เปลี่ยนด้วย `OCR_PORT=8001 docker compose up`
- บน Linux ให้ไฟล์ผลลัพธ์เป็นของผู้ใช้ปัจจุบัน: `OCR_UID=$(id -u) OCR_GID=$(id -g) docker compose up --build`
- ขั้นตรวจแก้เฉลย (GT Editor) เป็นโปรแกรมหน้าต่าง PyQt5 จึงเปิดจากหน้าเว็บใน Docker ไม่ได้ ให้รัน `python gt_editor.py` บนเครื่องจริง ไฟล์เฉลยจะเห็นร่วมกันผ่านโฟลเดอร์ที่ผูกไว้
- image นี้ใช้ CPU เท่านั้น ถ้าจะใช้ GPU บน Jetson ให้ดูหัวข้อถัดไป

## รันด้วย Docker บน Jetson (GPU)

ใช้ได้กับ JetPack 5 (L4T R35, CUDA 11.4) ต้อง build และรันบนตัว Jetson เอง เพราะ image อิง `nvcr.io/nvidia/l4t-jetpack:r35.4.1`
ถ้า L4T ของเครื่องต่างออกไป เปลี่ยนได้ด้วย `--build-arg L4T_IMAGE=...`

1. วาง wheel `paddlepaddle_gpu-3.0.0-cp38-cp38-linux_aarch64.whl` (ตัวเดียวกับที่ใช้ใน `.venv-jetson`) ไว้ในโฟลเดอร์ `wheels/`
2. รันจาก root ของโปรเจกต์:

```sh
OCR_UID=$(id -u) OCR_GID=$(id -g) docker compose -f docker-compose.jetson.yml up --build
```

3. เปิด **http://127.0.0.1:8000** ฟอร์ม "ประมวลผลด้วย" จะตั้งเป็น GPU (gpu:0) ให้อัตโนมัติ

ใน image นี้มี Python สองตัว คือ `/opt/ocr` (3.8 + paddlepaddle-gpu) สำหรับรันสคริปต์ OCR และ `/opt/web` (3.12) สำหรับหน้าเว็บ
เพราะ FastAPI ที่ตรึงไว้ไม่รองรับ Python 3.8 หน้าเว็บสั่งรันสคริปต์ผ่านตัวแปร `OCR_PYTHON=/opt/ocr/bin/python`
ตรวจว่า container เห็น GPU (ต้องได้ `True 1`):

```sh
docker compose -f docker-compose.jetson.yml exec workbench /opt/ocr/bin/python -c "import paddle; print(paddle.is_compiled_with_cuda(), paddle.device.cuda.device_count())"
```

## พัฒนา frontend

เปิด backend ด้วยคำสั่งข้างต้น แล้วเปิดอีก terminal:

```sh
cd web/frontend
npm run dev
```

เปิด **http://127.0.0.1:5173** Vite proxy `/api` ไป FastAPI ที่พอร์ต 8000 หลังแก้ frontend ให้ build ใหม่เมื่อต้องการใช้งานผ่านพอร์ต 8000 หน้า deep link เช่น `/guide` และ `/results/<id>` เปิดตรงหรือ refresh ได้

## หน้าต่าง GT Editor

ปุ่มเปิด GT Editor เรียก Python จาก `.venv/bin/python` เป็นอีก process และแสดง GUI PyQt5 ตามปกติบน desktop ของเครื่อง backend ให้รัน backend จาก desktop session ของผู้ใช้เครื่องนี้ ไม่ใช่ headless SSH

บน Jetson/Ubuntu ARM64 ให้ติดตั้ง `python3-pyqt5` และสร้าง venv ด้วย Python ของระบบพร้อม `--system-site-packages` ตาม [README หลัก](../README.md#gt-editor-บน-nvidia-jetson-orin-nx--ubuntu-arm64)
ถ้าใช้ `.venv-jetson` ให้ตั้ง `OCR_PYTHON="$PWD/.venv-jetson/bin/python"` ตอนเริ่ม backend
interpreter นี้ใช้กับทุก script จึงต้องติดตั้ง dependencies ของ OCR เพิ่มด้วยหากต้องการรัน OCR ผ่านเว็บ

GUI ใช้โฟลเดอร์ภาพ draft และ saved GT ตามฟอร์ม เมื่อแก้ไขแล้วกดบันทึกจาก GUI และปิดด้วยปุ่มปิดหน้าต่าง เพื่อใช้ขั้นตอนถามบันทึกเดิม เว็บจะไม่บังคับหยุด GUI จากปุ่มยกเลิกงาน OCR

หาก backend ปิด หน้าต่าง GT Editor ที่เปิดอยู่จะยังอยู่ ส่วนงาน OCR จะถูกหยุดทั้ง process group เมื่อ backend เปิดใหม่ งานที่ติดตามต่อไม่ได้จะแสดง `interrupted`; ปิด GUI เดิมด้วยตัวเองก่อนเปิดซ้ำใน session ใหม่

## การตั้งค่าและข้อมูล

- หน้าเว็บใช้ภาพจาก `images/` ไม่มี upload หรือ browser GT editor
- เลือก Baseline ที่อ่านจาก `helpers/ocr_common.py` หรือ selected config ของผลทดลองเดิมได้ ปรับต่อในส่วนขั้นสูงได้
- ค่า CPU/model/thread/batch ที่ script ล็อกไว้แสดงอ่านอย่างเดียว เว็บยังไม่ได้เพิ่ม GPU support
- Experiment อัตโนมัติอ่านรายการ trial จากโค้ดเดิม ส่วน custom ตั้งชื่อหลายชุดและปรับค่าของแต่ละชุดได้
- ตั้ง `OCR_PYTHON` ใน environment ของ backend หากต้องใช้ Python interpreter อื่น ค่าเริ่มต้นใช้ `.venv/bin/python` ของโปรเจกต์ จากนั้น fallback เป็น interpreter ของ backend
- ฟอนต์เลือกอัตโนมัติตาม script เดิม หากกำหนดเองให้นำไฟล์ไว้ใน `fonts/` และกรอกเส้นทางในฟอร์ม

แต่ละงานบันทึก metadata, config และ console log ใน `.webui/jobs/<job-id>/` ซึ่งถูก gitignore การเปิด/refresh browser ไม่หยุดงาน งานยังทำงานต่อขณะที่ backend ทำงานอยู่

Draft ใช้ `GroundTruthDraft/` ตามเดิม เพื่อให้ GUI เปิดตรวจต่อได้ Evaluation และ experiment เก็บใน `<โฟลเดอร์ผลลัพธ์>/web-<job-id>/<เวลา>/` แม้กำหนดโฟลเดอร์ผลเองก็ยังแยก job เพื่อไม่ให้ประวัติของแต่ละงานปะปน

เว็บค้นหารายงานเดิมใน `evaluation_output/` และ `experiment_output/` โดยไม่ย้ายไฟล์หรือคำนวณ metrics ใหม่ รายงานที่ JSON กำลังเขียนหรืออ่านไม่ได้จะไม่ทำให้หน้าประวัติล้ม ภาพผลลัพธ์ที่หายไปยังดูคะแนนและข้อความได้

## สถานะและ Logs

งาน OCR ทำได้ครั้งละหนึ่งงาน และเปิด GUI แยกได้หนึ่งหน้าต่างต่อ server session งานที่กดซ้อนจะได้ข้อความให้รอหรือยกเลิกงานเดิม

Frontend poll สถานะ/logs ทุกประมาณ 1 วินาที มี console และ worker log ของแต่ละ trial ให้เลือก Logs ใช้ UTF-8 และ cursor เพื่ออ่านเฉพาะส่วนที่เพิ่ม หน้าจอเก็บท้าย log สูงสุด 250,000 อักขระ ส่วนไฟล์เต็มยังอยู่บนดิสก์

ยกเลิกงานจะส่ง SIGTERM ไปทั้ง process group รวม worker ของ experiment หากยังไม่หยุดใน 3 วินาทีจึงส่ง SIGKILL รายงานบางส่วนยังเปิดได้ สถานะแยก `completed`, `completed_with_errors`, `failed`, `cancelled`, `interrupted` และ `cancelling`

## Response Logs

Backend บันทึกทุก response ของ `/api/*` ลง `.webui/logs/responses-YYYYMMDD.jsonl` (ไฟล์ละวัน บรรทัดละหนึ่ง response) พร้อม method, path, status, เวลาที่ใช้, request body และ response body ดูและค้นหาได้ที่หน้า **Response Logs** (`/logs`) หรือ `GET /api/response-logs`

GET ที่ตอบเหมือนครั้งก่อนของ URL เดียวกันบันทึกครั้งเดียว เพราะหน้าเว็บ poll ซ้ำตลอด เนื้อหาเกิน 16,000 อักขระถูกตัด ไฟล์ภาพ/ดาวน์โหลดบันทึกเฉพาะสถานะ และไม่มีการลบ log เก่าอัตโนมัติ

## API และโครงสร้าง

API docs: **http://127.0.0.1:8000/docs**

| API | หน้าที่ |
|---|---|
| `GET /api/health` | Python ที่ใช้และสถานะ dependencies โดยไม่โหลดโมเดล |
| `GET /api/scripts`, `/api/dataset`, `/api/presets` | Script, baseline, dataset และ config จากผลเดิม |
| `POST /api/jobs/preview` | ตรวจค่าและแสดงคำสั่ง โดยยังไม่สร้าง config/run |
| `POST /api/jobs`, `GET /api/jobs` | เริ่มงานและอ่านประวัติ |
| `GET /api/jobs/{id}` | สถานะ ความคืบหน้า และผลที่เชื่อมกับงาน |
| `GET /api/jobs/{id}/logs?source=console&offset=0` | อ่าน logs ต่อจาก byte cursor |
| `POST /api/jobs/{id}/cancel` | ยกเลิกงาน OCR |
| `GET /api/results`, `/api/results/{id}` | รายการและรายละเอียดรายงาน |
| `GET /api/artifacts?path=...&download=true` | ดูหรือดาวน์โหลดไฟล์ผลลัพธ์ที่รองรับ |

Backend รับเฉพาะ script ที่กำหนดและใช้ argument list ไม่ใช้ shell จำกัดไฟล์ภายในโฟลเดอร์ข้อมูลของโปรเจกต์ ตรวจ symlink/path traversal และปฏิเสธ Origin/Host นอก localhost

```text
web/
├── backend/
│   ├── app/
│   │   ├── main.py       # App, lifespan, localhost guard และเสิร์ฟ frontend
│   │   ├── config.py     # Project paths และ Python interpreter
│   │   ├── schemas.py    # Request models
│   │   ├── catalog.py    # Baseline/dataset และแปลงฟอร์มเป็น CLI
│   │   ├── jobs.py       # Process lifecycle, logs และประวัติงาน
│   │   ├── results.py    # อ่านรายงาน/preset และตรวจ artifact paths
│   │   └── routes.py     # API endpoints
│   ├── tests/           # Integration tests ด้วย subprocess เล็ก ๆ
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── app/         # Layout และ resource polling hook
    │   ├── api/         # Typed API client
    │   ├── components/  # UI ที่ใช้ร่วมกัน
    │   ├── content/     # คำอธิบาย script และ metrics ภาษาไทย
    │   ├── features/
    │   │   ├── runner/  # ฟอร์มและ logs ของงาน
    │   │   └── results/ # ตารางคะแนนและภาพผลลัพธ์
    │   ├── pages/       # Overview, Script, History, Result และ Guide
    │   ├── types/       # Frontend data contracts
    │   ├── main.tsx     # Entry และ routes
    │   └── styles.css   # Tailwind และ theme ที่ใช้ร่วมกัน
    └── package-lock.json
```

เพิ่ม script ใหม่โดยเริ่มที่ schema/catalog ของ backend และเพิ่มเนื้อหาใน `content/scripts.ts` แล้วเชื่อมฟอร์มเฉพาะความสามารถที่ CLI รองรับ เนื้อหา flow อยู่แยกจาก page เพื่อแก้คำอธิบายได้โดยไม่แก้ process runner

## ตรวจสอบ

จาก project root:

```sh
.venv/bin/python -m unittest discover -s web/backend/tests -v
.venv/bin/python -m unittest discover -s tests -v
```

จาก `web/frontend/`:

```sh
npm test
npm run build
```

ทดสอบ browser จริงโดยเปิด backend ที่พอร์ต 8000 และ build frontend แล้ว:

```sh
npm run test:e2e
```

ใช้ Google Chrome ที่ติดตั้งบน macOS หรือ browser ของ Playwright (ติดตั้งได้ด้วย `npx playwright install chromium`) ตั้ง `OCR_CHROME_PATH` เพื่อระบุ executable เอง หรือ `OCR_WEB_URL` สำหรับ URL localhost อื่น การทดสอบนี้เปิดหน้าต่างแบบ headless รันเฉพาะ experiment dry-run ไม่โหลด OCR และบันทึก screenshot ใน temporary directory

Backend tests ใช้ subprocess fixture แทน OCR จริง ตรวจการยกเลิก worker ที่ไม่ยอมรับ SIGTERM การกดซ้อน restore history path guards และรายงานบางส่วน Frontend tests ตรวจเลือก preset ปรับ/คืนค่า parameter สั่งรัน custom trials เปิด editor ดู logs ยกเลิกงาน และแยกเวลาเฉลี่ย/เวลารวม
