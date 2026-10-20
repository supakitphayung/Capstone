import json
import time
from pathlib import Path
import cv2
import numpy as np
from paddleocr import PaddleOCR
from PIL import Image, ImageDraw, ImageFont

def find_thai_font():
    candidates = [
        Path(__file__).parent / "fonts" / "NotoSansThai-Regular.ttf",
        Path("/System/Library/Fonts/Supplemental/Thonburi.ttc"),
        Path("/System/Library/Fonts/ThonburiUI.ttc"),
        Path.home() / "Library/Fonts/THSarabunNew.ttf",
    ]
    for font in candidates:
        if font.is_file(): return str(font)
    raise FileNotFoundError("ไม่พบฟอนต์ภาษาไทย กรุณาติดตั้งหรือระบุ Path ฟอนต์")

def main():
    input_dir = Path("images") # โฟลเดอร์รูปที่ต้องการทำเฉลย (เปลี่ยนชื่อได้)
    output_dir = Path("GroundTruth")
    output_dir.mkdir(exist_ok=True)
    
    font_path = find_thai_font()
    
    # เพิ่ม Parameter ป้องกันเครื่อง Mac M3 ค้าง และจำกัดขนาดภาพเพื่อให้สแกนไวขึ้น
    engine = PaddleOCR(
        lang="th", 
        use_textline_orientation=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        enable_mkldnn=False,
        cpu_threads=4,
        text_det_limit_side_len=2560,
        det_db_box_thresh=0.3,       # ลดเกณฑ์ในการตีกรอบลง เพื่อให้จับข้อความได้ครอบคลุมขึ้น (ค่าเริ่มต้นมักจะ 0.5)
        det_db_unclip_ratio=2.5      # เพิ่มค่านี้ (จากปกติ 1.5 หรือ 2.0) เพื่อขยายขนาดกล่องให้ใหญ่ขึ้น ครอบคลุมสระบน/ล่างได้ดีขึ้น
    )
    
    for img_path in input_dir.rglob("*"):
        if img_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}: continue
        print(f"กำลังสร้างเฉลยให้ภาพ: {img_path.name}")
        
        image = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None: continue
        
        results = engine.predict(image)[0]
        if not results: continue
        
        # จัดเรียงจากบนลงล่าง
        regions = []
        for text, score, polygon in zip(results["rec_texts"], results["rec_scores"], results["rec_polys"]):
            pts = np.array(polygon, dtype=np.int32)
            bbox = [int(pts[:, 0].min()), int(pts[:, 1].min()), int(pts[:, 0].max()), int(pts[:, 1].max())]
            regions.append({"text": text, "bbox": bbox, "polygon": pts.tolist()})
        regions.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))
        
        gt_json = {}
        canvas = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).convert("RGBA")
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.truetype(font_path, size=24)
        
        for i, region in enumerate(regions, 1):
            pos_key = f"pos{i}"
            
            # [อัปเดต] นำ bbox กลับมาบันทึกใน JSON เพื่อให้มีประโยชน์ตอน Evaluate
            gt_json[pos_key] = {"text": region["text"], "bbox": region["bbox"]}
            
            # ตีกรอบสีแดง (Red) บนภาพ
            l, t, r, b = region["bbox"]
            draw.rectangle([l, t, r, b], outline=(255, 0, 0, 255), width=2)
            
            # วาดพื้นหลังข้อความและป้าย pos
            label = f"{pos_key}: {region['text']}"
            bounds = draw.textbbox((0, 0), label, font=font)
            w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
            draw.rectangle([l, t-h-4, l+w+4, t], fill=(255, 255, 255, 200))
            draw.text((l+2, t-h-4), label, font=font, fill=(255, 0, 0, 255))
        
        final_img = cv2.cvtColor(np.asarray(canvas.convert("RGB")), cv2.COLOR_RGB2BGR)
        
        # บันทึกภาพเฉลยและ JSON
        img_out_path = output_dir / f"{img_path.stem}_gt.png"
        json_out_path = output_dir / f"{img_path.stem}_gt.json"
        
        cv2.imencode('.png', final_img)[1].tofile(img_out_path)
        with open(json_out_path, "w", encoding="utf-8") as f:
            json.dump(gt_json, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()