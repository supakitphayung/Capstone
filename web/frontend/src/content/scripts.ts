import type { ScriptId } from '../types';

export interface ScriptGuide {
  title: string; eyebrow: string; description: string; file: string; step: string;
  inputs: string[]; flow: { title: string; body: string }[]; outputs: string[];
  tips: string[]; next: { to: string; label: string };
}

export const scriptOrder: ScriptId[] = ['create_gt', 'gt_editor', 'evaluate_ocr', 'experiment_ocr'];
export const scriptGuides: Record<ScriptId, ScriptGuide> = {
  create_gt: {
    title: 'สร้างร่าง Ground Truth', eyebrow: '01 / PREPARE', step: 'สร้าง Draft', file: 'create_gt.py',
    description: 'ให้ OCR ช่วยวางกรอบและอ่านข้อความเบื้องต้น ก่อนที่เราจะตรวจแก้ให้เป็นเฉลยที่เชื่อถือได้',
    inputs: ['ภาพต้นฉบับใน images/ เลือกหนึ่งภาพหรือทั้งโฟลเดอร์ได้', 'ค่า OCR จาก baseline หรือ config ที่ชนะการทดลองเดิม'],
    flow: [
      { title: 'เลือกภาพที่ยังไม่มี draft', body: 'ค่าเริ่มต้นข้ามภาพที่มี draft อยู่แล้ว เปิด overwrite เมื่อต้องการสร้างร่างทับของเดิม และเปิด recursive เพื่อค้นภาพในโฟลเดอร์ย่อย' },
      { title: 'โหลดโมเดลหนึ่งครั้ง แล้วอ่านทีละภาพ', body: 'ใช้ PP-OCRv5 Mobile detector และ recognizer ภาษาไทยตัวเดิมกับทุกภาพในรอบนี้ โดยอ่านจากภาพต้นฉบับ' },
      { title: 'กรองผล OCR', body: 'ตรวจ confidence เก็บข้อความที่มีอักขระไม่ใช่ช่องว่างอย่างน้อย min_text_length ตัวหลัง Unicode NFC และตัดข้อความที่มีแต่ combining marks เช่น วรรณยุกต์ลอย' },
      { title: 'บันทึกร่างและภาพตัวอย่าง', body: 'บันทึกข้อความและ bbox ในพิกัดภาพต้นฉบับ พร้อม confidence/config แยกใน metadata ร่างนี้ยังต้องผ่านการตรวจของคน' },
    ],
    outputs: ['GroundTruthDraft/<ชื่อภาพ>_gt.json — ข้อความและกรอบร่าง', '<ชื่อภาพ>_gt.draft.json — config, confidence และเวลา OCR', '<ชื่อภาพ>_gt.png — ภาพตีกรอบ และ draft_run.json — สรุปรอบรัน'],
    tips: ['Baseline รับ confidence ตั้งแต่ 0.0 และตั้ง min_text_length = 2 จึงตัดข้อความเดี่ยว เช่น 9 หรือ N', 'overwrite เขียนทับเฉพาะ draft; GT ที่บันทึกแล้วเป็นข้อมูลอีกชุด และ GT Editor จะเลือก saved GT ก่อน draft'],
    next: { to: '/scripts/gt_editor', label: 'ตรวจแก้ใน GT Editor' },
  },
  gt_editor: {
    title: 'ตรวจแก้ Ground Truth', eyebrow: '02 / REVIEW', step: 'ตรวจ GT', file: 'gt_editor.py',
    description: 'เปิดหน้าต่าง GUI เดิมบนเครื่องนี้ เพื่อแก้ข้อความ เพิ่มกรอบ และบันทึกเฉลยสำหรับการประเมิน',
    inputs: ['ภาพต้นฉบับใน images/ พร้อม draft ถ้ามี', 'saved GT เดิมมีลำดับความสำคัญก่อน draft เมื่อเปิดภาพ'],
    flow: [
      { title: 'เปิดโปรแกรมบน desktop', body: 'FastAPI เรียก gt_editor.py เป็นอีก process หน้าต่าง PySide6 จะขึ้นบนเครื่องที่รัน backend และไม่โหลดโมเดล OCR' },
      { title: 'ตรวจทุกตำแหน่ง', body: 'เลือกกรอบเพื่อแก้ข้อความ ลากกรอบเพื่อย้าย ลากมุมเพื่อเปลี่ยนขนาด เพิ่มหรือลบกรอบตามภาพจริง เก็บสระ วรรณยุกต์ ตัวเลข และเครื่องหมายให้ครบ' },
      { title: 'กำหนด ignore เมื่ออ่านไม่ได้', body: 'ใช้กับบริเวณที่คนอ่านไม่ได้จริง กรอบนี้จะถูกแยกจากตัวหาร GT และมีเกณฑ์ละเว้น detection ที่ทับบริเวณ ignore' },
      { title: 'กดบันทึกใน GUI', body: 'ไฟล์จะถูกเขียนลง GroundTruth/ พร้อมภาพตัวอย่าง พิกัดอ้างอิงภาพต้นฉบับเสมอ ไม่เปลี่ยนตามการซูม จากนั้นจึงนำไปประเมินได้' },
    ],
    outputs: ['GroundTruth/<ชื่อภาพ>_gt.json — text, bbox และ ignore ของแต่ละตำแหน่ง', 'GroundTruth/<ชื่อภาพ>_gt.png — ภาพตรวจสอบ GT ที่บันทึกแล้ว'],
    tips: ['ล้อเมาส์เพื่อซูม; Space + ลากเพื่อเลื่อนภาพ; Cmd/Ctrl + Z เพื่อ Undo', 'ปิดผ่านหน้าต่าง GUI เพื่อให้โปรแกรมถามบันทึกงานตามปกติ เมื่อบันทึกแล้วรีเฟรชสถานะ dataset ในเว็บได้'],
    next: { to: '/scripts/evaluate_ocr', label: 'ประเมินกับ GT ที่บันทึกแล้ว' },
  },
  evaluate_ocr: {
    title: 'ประเมินความแม่นยำ OCR', eyebrow: '03 / EVALUATE', step: 'ประเมิน OCR', file: 'evaluate_ocr.py',
    description: 'วัดการหาตำแหน่งและการอ่านข้อความเทียบกับ GT ที่คนตรวจแล้ว สำหรับ parameter หนึ่งชุด',
    inputs: ['ภาพต้นฉบับและ saved GT ใน GroundTruth/', 'เลือกบาง ID หรือทุกภาพได้ ภาพที่ไม่มี GT จะถูกข้ามและบันทึกใน skipped.json'],
    flow: [
      { title: 'แช่แข็งข้อมูลรอบนี้', body: 'คัดลอกภาพและ GT เป็น snapshot พร้อม SHA-256 และ manifest การแก้ GT ต้นฉบับภายหลังไม่เปลี่ยนผลรอบนี้' },
      { title: 'รัน OCR ด้วย config ที่เลือก', body: 'โหลดโมเดลครั้งเดียว อ่านภาพเต็มและกรองผลตามค่า OCR เดียวกับขั้นสร้าง draft โดยไม่ใช้กรอบ GT เป็น crop ให้โมเดลอ่าน' },
      { title: 'จับคู่กรอบก่อนเทียบข้อความ', body: 'ใช้ bbox บนภาพต้นฉบับ จับคู่หนึ่งต่อหนึ่งที่ IoU ≥ 0.5 ด้วย Hungarian assignment ให้ได้จำนวนคู่มากที่สุด แล้วให้ผลรวม IoU สูงที่สุด ข้อความไม่มีส่วนในการเลือกคู่' },
      { title: 'เทียบข้อความและรวมคะแนน', body: 'ทำ Unicode NFC และ strip หัวท้าย แล้วเทียบข้อความทั้ง region เก็บ character errors และ counts ของทุกภาพ ก่อนคำนวณคะแนนรวมใหม่' },
    ],
    outputs: ['evaluation_output/<รอบ>/dataset/ — snapshot และ manifest', 'evaluation/report.json — คะแนนรวม config เวลา และผลรายภาพ', 'evaluation/images/ และ framed/ — JSON รายภาพและภาพอธิบายข้อผิดพลาด'],
    tips: ['ตรงกรอบแต่อ่านผิดหนึ่งอักขระยังได้ detection match แต่ไม่เป็น end-to-end correct', 'Matched CER ไม่รวม GT ที่หาไม่เจอหรือ detection เกิน ต้องดู End-to-end F1 ประกอบเสมอ'],
    next: { to: '/scripts/experiment_ocr', label: 'ทดลองหลาย parameter' },
  },
  experiment_ocr: {
    title: 'ทดลองและเลือก Parameter', eyebrow: '04 / EXPERIMENT', step: 'ทดลองค่า', file: 'experiment_ocr.py',
    description: 'เปรียบเทียบหลาย config บน dataset เดียวกัน เลือกผู้ชนะจาก tune แล้วประเมิน holdout แยกภายหลัง',
    inputs: ['ภาพและ saved GT ตาม experiments/dataset_split.json', 'ชุดอัตโนมัติ หรือชุดทดลองที่ตั้งชื่อและกำหนด parameter เอง'],
    flow: [
      { title: 'ตรวจ split และ snapshot', body: 'ตรวจภาพ ID และไม่ให้ product group เดียวกันอยู่ทั้ง tune กับ holdout จากนั้นคัดลอกภาพและ GT ให้ทุก trial ใช้ข้อมูลเดียวกัน' },
      { title: 'รัน trial ทีละชุด', body: 'อัตโนมัติเริ่ม 12 ชุด: baseline 1, เปลี่ยนทีละ parameter 8 และ focused trials 3 แต่ละ trial เปิด subprocess และโหลดโมเดลของตัวเองครั้งเดียวก่อนอ่านภาพ tune' },
      { title: 'ลองรวมค่าที่ชนะ', body: 'เมื่อเปิด combine จะเลือกค่าจาก baseline และ trial ที่เปลี่ยนทีละ parameter มารวมเป็น combined-winners แล้วรันเพิ่มถ้ายังไม่ซ้ำ ชุด focused ยังมีสิทธิ์เป็นผู้ชนะโดยรวม' },
      { title: 'เลือกจาก tune แล้วตรวจ holdout', body: 'เรียงตาม End-to-end F1 สูงสุด → Matched CER ต่ำสุด → เวลา OCR ต่ำสุด → peak RSS ต่ำสุด บันทึก selected_config ก่อนรัน holdout ซึ่งไม่ใช้เลือก parameter' },
    ],
    outputs: ['comparison.json / comparison.md — ตารางทุก trial และผู้ชนะ', 'selected_config.json — config เต็มของชุดที่เลือก', 'trials/<ชื่อ>/ — รายงาน logs และภาพของแต่ละชุด; holdout/ — ผลชุดที่เลือกบน holdout'],
    tips: ['ค่า timeout เริ่มต้น 1,800 วินาทีต่อ trial งานที่รันไม่ครบหรือ failed จะไม่ถูกเลือก', 'Dry-run ตรวจและแสดงแผนโดยไม่โหลด OCR หรือสร้างผลทดลอง; ชุด custom ไม่เพิ่ม combined-winners', 'นี่คือการ tune parameter ใน inference โมเดลไม่ได้ถูกฝึกหรือ fine-tune น้ำหนักใหม่'],
    next: { to: '/history', label: 'ดูประวัติและเปรียบเทียบผล' },
  },
};

export const metricGuides = [
  { title: 'Detection F1', formula: '2 × matched / (predictions + GT)', body: 'วัดว่าหากรอบตรงตำแหน่งหรือไม่ คู่ต้องผ่าน IoU ≥ 0.5 โดยยังไม่สนใจว่าอ่านข้อความถูก จำนวน predictions หัก ignored detections แล้ว' },
  { title: 'End-to-end F1', formula: '2 × correct / (predictions + GT)', body: 'ต้องผ่านทั้งตำแหน่งและข้อความตรงทั้งหมด ผิดเพียงหนึ่งอักขระก็ไม่เป็น correct กรอบเกิน ข้อความผิด และข้อความตกหล่นลดคะแนนนี้' },
  { title: 'Matched CER', formula: 'Σ(substitution + deletion + insertion) / Σ(matched GT characters)', body: 'ใช้ Levenshtein distance เฉพาะคู่ที่จับกรอบได้ ยิ่งต่ำยิ่งดี อาจเกิน 1 หากมีอักขระเกินมาก นับ Unicode code points หลัง NFC; สระและวรรณยุกต์อาจนับแยก ถ้าไม่มีอักขระ GT ที่จับคู่ได้แสดง n/a' },
  { title: 'Accuracy %', formula: 'correct / GT × 100', body: 'สัดส่วนตำแหน่ง GT ที่หากรอบและอ่านถูกครบ กรอบเกินไม่มีผลโดยตรงต่อค่านี้ จึงใช้ F1 ประกอบ' },
];
