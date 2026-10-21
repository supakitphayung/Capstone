import { useState } from 'react';
import { Download, Expand, ImageOff } from 'lucide-react';
import { artifactUrl } from '../../api/client';
import { Empty, number, Status } from '../../components/ui';
import type { ImageReport, Metrics, Report } from '../../types';

export function MetricCards({ metrics }: { metrics?: Metrics }) {
  return <div className="metric-grid">{[
    ['END-TO-END F1', number(metrics?.end_to_end?.f1), 'ทั้งกรอบและข้อความถูกครบ'],
    ['DETECTION F1', number(metrics?.detection?.f1), 'จับคู่กรอบด้วย IoU ≥ 0.5'],
    ['MATCHED CER', number(metrics?.matched_cer), 'ยิ่งต่ำยิ่งดี · เฉพาะคู่ที่จับได้'],
    ['ACCURACY', metrics ? `${number(metrics.accuracy_percent, 2)}%` : 'n/a', 'ตำแหน่งถูกครบ / GT'],
  ].map(([label, value, hint], index) => <div className={`metric-card ${index === 0 ? 'metric-featured' : ''}`} key={label}><p className="eyebrow">{label}</p><strong>{value}</strong><small>{hint}</small></div>)}</div>;
}

export function TrialTable({ trials, best, selected, onSelect }: { trials: Report[]; best: string | null; selected: string; onSelect: (name: string) => void }) {
  return <div className="table-scroll"><table><thead><tr><th>Trial</th><th>สถานะ</th><th>E2E F1</th><th>Detection F1</th><th>Matched CER</th><th>Accuracy %</th><th>OCR รวม (s)</th><th>เฉลี่ย/ภาพ (s)</th><th>Peak RSS MB</th></tr></thead><tbody>{trials.map((trial, index) => {
    const count = trial.completed_images ?? trial.images?.filter(image => image.status === 'completed').length ?? 0;
    return <tr key={trial.name || index} className={selected === trial.name ? 'selected-row' : ''}><td><button className="trial-link" onClick={() => onSelect(trial.name || '')}>{trial.name}<span className="sr-only"> — ดูรายละเอียด</span></button>{best === trial.name && <span className="winner-badge">BEST</span>}</td><td><Status status={trial.status} /></td><td className="numeric font-semibold">{number(trial.metrics?.end_to_end?.f1)}</td><td className="numeric">{number(trial.metrics?.detection?.f1)}</td><td className="numeric">{number(trial.metrics?.matched_cer)}</td><td className="numeric">{number(trial.metrics?.accuracy_percent, 2)}</td><td className="numeric">{number(trial.ocr_seconds, 3)}</td><td className="numeric">{count && trial.ocr_seconds != null ? number(trial.ocr_seconds / count, 3) : 'n/a'}</td><td className="numeric">{number(trial.peak_rss_mb, 1)}</td></tr>;
  })}</tbody></table>{!trials.length && <Empty title="ยังไม่มี trial ที่สิ้นสุด">ระหว่างรันดูรายละเอียดจากหน้า logs ได้</Empty>}</div>;
}

export function ReportView({ report }: { report: Report }) {
  const images = report.images || [];
  const [filename, setFilename] = useState(images[0]?.filename || '');
  const image = images.find(item => item.filename === filename) || images[0];
  const metrics = report.metrics;
  const count = report.completed_images ?? images.filter(item => item.status === 'completed').length;
  return <div className="space-y-5"><MetricCards metrics={metrics} />
    {report.error && <div className="notice notice-error">{report.error}</div>}
    <div className="card"><div className="timing-grid"><Timing label="เวลา OCR รวม" value={report.ocr_seconds} hint={`${count} ภาพที่สำเร็จ · ช่วง engine.predict()`} /><Timing label="เวลา OCR เฉลี่ยต่อภาพ" value={count && report.ocr_seconds != null ? report.ocr_seconds / count : undefined} hint="เวลารวม ÷ จำนวนภาพที่สำเร็จ" /><Timing label="โหลดโมเดล" value={report.model_load_seconds} hint="แยกจากเวลา OCR" /><Timing label="เวลารวมงาน" value={report.elapsed_seconds} hint="รวมเตรียม อ่านภาพ และบันทึกผล" /></div></div>
    {metrics && <div className="count-strip">{[['GT', metrics.total_gt_positions], ['จับคู่ได้', metrics.matched_positions], ['ถูกครบ', metrics.correct_positions], ['ข้อความผิด', metrics.wrong_text_positions], ['หาไม่เจอ', metrics.missed_positions], ['กรอบเกิน', metrics.extra_positions], ['Ignore GT', metrics.ignored_gt_positions], ['Ignore detection', metrics.ignored_detections]].map(([label, value]) => <span key={label}><b>{value}</b>{label}</span>)}</div>}
    <div className="card overflow-hidden"><div className="section-heading"><div><h2>ผลรายภาพ</h2><p>คลิกชื่อภาพเพื่อดูภาพตีกรอบและข้อความแต่ละตำแหน่ง</p></div><span className="pill">{images.length} IMAGES</span></div><div className="table-scroll"><table><thead><tr><th>ภาพ</th><th>สถานะ</th><th>E2E F1</th><th>Matched CER</th><th>OCR ภาพนี้ (s)</th><th>รวมภาพนี้ (s)</th></tr></thead><tbody>{images.map(item => <tr key={item.filename} className={image?.filename === item.filename ? 'selected-row' : ''}><td><button className="trial-link" onClick={() => setFilename(item.filename)}>{item.filename}</button></td><td><Status status={item.status} /></td><td className="numeric">{number(item.metrics?.end_to_end?.f1)}</td><td className="numeric">{number(item.metrics?.matched_cer)}</td><td className="numeric">{number(item.ocr_seconds, 3)}</td><td className="numeric">{number(item.elapsed_seconds, 3)}</td></tr>)}</tbody></table></div>{!images.length && <Empty title="ยังไม่มีผลรายภาพ">รายงานจะปรากฏเมื่อ script อ่านและประเมินภาพเสร็จ</Empty>}</div>
    {image && <ImageDetails key={image.filename} image={image} />}
    {report.config && <details className="card p-5"><summary className="cursor-pointer text-sm font-semibold">Config ที่ใช้จริง</summary><pre className="json-view mt-4">{JSON.stringify(report.config, null, 2)}</pre></details>}
  </div>;
}

function Timing({ label, value, hint }: { label: string; value: number | null | undefined; hint: string }) {
  return <div><p>{label}</p><strong>{number(value, 3)}<span> s</span></strong><small>{hint}</small></div>;
}

function ImageDetails({ image }: { image: ImageReport }) {
  const details = Object.entries(image.metrics?.details || {});
  return <div className="card overflow-hidden"><div className="section-heading"><div><h2>{image.filename}</h2><p>เขียว: ถูก · แดง: ผิด/หาไม่เจอ/เกิน · เทา: ignore</p></div>{image.framed_path && <div className="flex gap-2"><a className="button button-secondary button-small" target="_blank" rel="noreferrer" href={artifactUrl(image.framed_path)}><Expand size={14} />ดูเต็มภาพ</a><a className="icon-button" aria-label="ดาวน์โหลดภาพผลลัพธ์" href={artifactUrl(image.framed_path, true)}><Download size={17} /></a></div>}</div>
    {image.error && <div className="notice notice-error m-5">{image.error}</div>}
    {image.framed_path ? <div className="report-image"><img src={artifactUrl(image.framed_path)} alt={`ผลประเมิน OCR ของ ${image.filename}`} loading="lazy" /></div> : <div className="empty"><ImageOff className="mx-auto mb-3 text-slate-300" /><p>ยังไม่มีไฟล์ภาพผลลัพธ์</p></div>}
    {!!details.length && <div className="table-scroll"><table><thead><tr><th>ตำแหน่ง</th><th>สถานะ</th><th>Ground Truth</th><th>OCR อ่านได้</th><th>IoU</th><th>CER ของคู่นี้</th></tr></thead><tbody>{details.map(([key, detail]) => <tr key={key}><td className="font-mono text-xs">{key}</td><td><Status status={detail.status} /></td><td className="region-text">{detail.expected ?? detail.text ?? '—'}</td><td className="region-text">{detail.got ?? '—'}</td><td className="numeric">{number(detail.iou, 3)}</td><td className="numeric">{number(detail.cer)}</td></tr>)}</tbody></table></div>}
    {!!image.metrics?.extras?.length && <div className="border-t border-slate-100 p-5 text-sm"><strong className="text-red-600">กรอบเกิน (Extra)</strong><ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600">{image.metrics.extras.map((extra, index) => <li key={index}>{extra.text}</li>)}</ul></div>}
  </div>;
}
