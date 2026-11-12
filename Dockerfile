# OCR Workbench (หน้าเว็บ + สคริปต์ OCR) แบบ CPU
# ขั้นตรวจแก้เฉลย (gt_editor.py) เป็นโปรแกรมหน้าต่าง PyQt5 จึงไม่รวมอยู่ใน image นี้ ให้รันบนเครื่องจริง

# ---- 1) build หน้าเว็บ ----
FROM node:22-slim AS frontend
WORKDIR /build
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci
COPY web/frontend/ ./
RUN npm run build

# ---- 2) Python + PaddleOCR ----
FROM python:3.12-slim
# ไลบรารีระบบที่ OpenCV และ PaddlePaddle ต้องใช้ และฟอนต์ไทย (Garuda) สำหรับเขียนข้อความบนภาพผลลัพธ์
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 fonts-tlwg-garuda-ttf \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./requirements.txt
COPY web/backend/requirements.txt ./web/backend/requirements.txt
# ข้าม PyQt5: ใช้เฉพาะ gt_editor.py ซึ่งไม่รันใน container
RUN grep -v -i '^PyQt5' requirements.txt > /tmp/ocr-requirements.txt \
    && pip install --no-cache-dir -r /tmp/ocr-requirements.txt -r web/backend/requirements.txt \
    && rm /tmp/ocr-requirements.txt

COPY create_gt.py evaluate_ocr.py experiment_ocr.py gt_editor.py ./
COPY helpers/ helpers/
COPY experiments/ experiments/
COPY web/backend/app/ web/backend/app/
COPY --from=frontend /build/dist web/frontend/dist

# โฟลเดอร์ข้อมูลจะถูก mount จากเครื่องจริง สร้างไว้ให้เขียนได้แม้รันด้วย user ที่ไม่ใช่ root
RUN mkdir -p images GroundTruthDraft GroundTruth evaluation_output experiment_output .ocr_cache .webui /tmp/home \
    && chmod -R a+rwX /app /tmp/home

ENV HOME=/tmp/home \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OCR_HEADLESS=1

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=8)" || exit 1
# worker เดียวเท่านั้น: ระบบจองงาน OCR ออกแบบมาสำหรับ process เดียว
CMD ["python", "-m", "uvicorn", "web.backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
