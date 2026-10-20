import json
import time
import os
from pathlib import Path
import cv2
import numpy as np
from paddleocr import PaddleOCR
from PIL import Image, ImageDraw, ImageFont

def get_next_round_dir(base_path="."):
    """หาโฟลเดอร์ OCR_round_X ล่าสุด แล้วสร้างโฟลเดอร์ถัดไป"""
    base = Path(base_path)
    existing_rounds = [int(d.name.split("_")[-1]) for d in base.glob("OCR_round_*") if d.is_dir() and d.name.split("_")[-1].isdigit()]
    next_round = max(existing_rounds) + 1 if existing_rounds else 0
    new_dir = base / f"OCR_round_{next_round}"
    new_dir.mkdir(parents=True, exist_ok=True)
    return new_dir

def calculate_iou(boxA, boxB):
    """คำนวณพื้นที่ทับซ้อน (Intersection over Union) ของ 2 กรอบ"""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    if interArea == 0: return 0.0
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    return interArea / float(boxAArea + boxBArea - interArea)

def edit_distance(s1, s2):
    """ฟังก์ชันหา Character Error Rate (CER) พื้นฐาน"""
    if len(s1) > len(s2): s1, s2 = s2, s1
    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2+1]
        for i1, c1 in enumerate(s1):
            if c1 == c2: distances_.append(distances[i1])
            else: distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
        distances = distances_
    return distances[-1] / len(s2) if s2 else 0.0

def find_thai_font():
    candidates = [
        Path(__file__).parent / "fonts" / "NotoSansThai-Regular.ttf",
        Path("/System/Library/Fonts/Supplemental/Thonburi.ttc"),
        Path.home() / "Library/Fonts/THSarabunNew.ttf",
    ]
    for font in candidates:
        if font.is_file(): return str(font)
    raise FileNotFoundError("ไม่พบฟอนต์ภาษาไทย")

def main():
    input_dir = Path("images")        # โฟลเดอร์รูปภาพ
    gt_dir = Path("GroundTruth")      # โฟลเดอร์ที่เก็บเฉลยจากโค้ด 1
    output_round_dir = get_next_round_dir()
    
    font_path = find_thai_font()
    
    # อัปเดต Parameter ให้ตรงกับ create_gt.py เพื่อป้องกันเครื่องค้าง
    engine = PaddleOCR(
        lang="th", 
        use_textline_orientation=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        enable_mkldnn=False,
        cpu_threads=4,
        text_det_limit_side_len=2560
    )
    
    for img_path in input_dir.rglob("*"):
        if img_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}: continue
        
        gt_json_file = gt_dir / f"{img_path.stem}_gt.json"
        if not gt_json_file.exists():
            print(f"ข้าม {img_path.name}: ไม่มีไฟล์เฉลย")
            continue
            
        with open(gt_json_file, "r", encoding="utf-8") as f:
            gt_data = json.load(f)

        print(f"กำลังประเมินภาพ: {img_path.name}")
        
        image = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None: continue
        
        # --- เริ่มจับเวลา ---
        start_time = time.perf_counter()
        results = engine.predict(image)[0]
        scan_time = round(time.perf_counter() - start_time, 3)
        # --- หยุดจับเวลา ---
        
        # แปลงผลลัพธ์เป็นโครงสร้าง Box
        detections = []
        if results:
            for text, score, polygon in zip(results["rec_texts"], results["rec_scores"], results["rec_polys"]):
                pts = np.array(polygon, dtype=np.int32)
                bbox = [int(pts[:, 0].min()), int(pts[:, 1].min()), int(pts[:, 0].max()), int(pts[:, 1].max())]
                detections.append({"text": text, "bbox": bbox})

        # --- ส่วนของการเปรียบเทียบ (Evaluation ด้วย IoU และ Bounding Box) ---
        canvas = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).convert("RGBA")
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.truetype(font_path, size=20)
        
        metrics = {
            "image_name": img_path.name,
            "scan_time_seconds": scan_time,
            "total_gt_positions": len(gt_data),
            "correct_positions": 0,
            "missed_positions": 0,
            "wrong_text_positions": 0,
            "details": {}
        }
        
        matched_detections = set()

        for pos_key, gt_val in gt_data.items():
            gt_box = gt_val["bbox"]
            gt_text = gt_val["text"]
            
            # หา Detection ที่ทับซ้อนกับกล่องเฉลยมากที่สุด
            best_iou = 0
            best_det_idx = -1
            for i, det in enumerate(detections):
                if i in matched_detections: continue
                iou = calculate_iou(gt_box, det["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_det_idx = i
            
            # l,t,r,b เริ่มต้นให้เป็นพิกัดของกล่องเฉลย (เผื่อใช้ตอนหาไม่เจอ)
            l, t, r, b = gt_box 
            
            if best_iou > 0.3: # แปลว่าเจอกล่องในตำแหน่งที่ใกล้เคียงกัน
                matched_detections.add(best_det_idx)
                det_text = detections[best_det_idx]["text"]
                cer = edit_distance(gt_text, det_text)
                
                # หากหาเจอ ให้วาดกรอบตรงจุดที่โมเดลจับได้ล่าสุด
                det_l, det_t, det_r, det_b = detections[best_det_idx]["bbox"]
                
                if cer == 0: # อ่านถูกเป๊ะ 100%
                    metrics["correct_positions"] += 1
                    metrics["details"][pos_key] = {"status": "correct", "text": det_text}
                    color = (0, 200, 0, 255) # สีเขียว
                    label = f"OK: {det_text}"
                else: # หาเจอแต่อ่านเพี้ยน
                    metrics["wrong_text_positions"] += 1
                    metrics["details"][pos_key] = {"status": "wrong_text", "expected": gt_text, "got": det_text, "cer": round(cer, 3)}
                    color = (255, 0, 0, 255) # สีแดง
                    label = f"ผิด! ควรเป็น: {gt_text}"
                    
                # วาดกรอบและข้อความ ด้วยพิกัดใหม่ที่มันเจอ
                draw.rectangle([det_l, det_t, det_r, det_b], outline=color, width=3)
                bounds = draw.textbbox((0, 0), label, font=font)
                w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
                draw.rectangle([det_l, det_t-h-4, det_l+w+4, det_t], fill=(255, 255, 255, 220))
                draw.text((det_l+2, det_t-h-4), label, font=font, fill=color)
                
            else:
                # หาตำแหน่งนั้นไม่เจอเลย (Missed)
                metrics["missed_positions"] += 1
                metrics["details"][pos_key] = {"status": "missed", "expected": gt_text}
                color = (255, 0, 0, 255) # สีแดง
                label = f"หาไม่เจอ: {gt_text}"

                # [อัปเดต] วาดกรอบและข้อความ ด้วยพิกัดจากเฉลย (Ground Truth)
                # เพื่อบอกให้รู้ว่าโมเดลพลาดตรงจุดนี้นะ
                draw.rectangle([l, t, r, b], outline=color, width=3)
                bounds = draw.textbbox((0, 0), label, font=font)
                w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
                draw.rectangle([l, t-h-4, l+w+4, t], fill=(255, 255, 255, 220))
                draw.text((l+2, t-h-4), label, font=font, fill=color)

        # สรุปความแม่นยำรวม
        if metrics["total_gt_positions"] > 0:
            metrics["accuracy_percent"] = round((metrics["correct_positions"] / metrics["total_gt_positions"]) * 100, 2)
        else:
            metrics["accuracy_percent"] = 0.0

        # --- สร้างโฟลเดอร์ผลลัพธ์ย่อย (เช่น pic1_res) ---
        img_res_dir = output_round_dir / f"{img_path.stem}_res"
        img_res_dir.mkdir(exist_ok=True)
        
        # เซฟภาพที่ตีวงแล้ว และไฟล์ JSON
        final_img = cv2.cvtColor(np.asarray(canvas.convert("RGB")), cv2.COLOR_RGB2BGR)
        cv2.imencode(img_path.suffix, final_img)[1].tofile(img_res_dir / f"{img_path.stem}_evaluated{img_path.suffix}")
        
        with open(img_res_dir / f"{img_path.stem}_metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)

    print(f"✅ เสร็จสิ้น! ผลลัพธ์ถูกบันทึกไว้ที่โฟลเดอร์: {output_round_dir.name}")

if __name__ == "__main__":
    main()