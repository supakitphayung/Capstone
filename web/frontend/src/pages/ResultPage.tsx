import { useState } from 'react';
import { ArrowLeft, Download, RefreshCw, Trophy } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { api, artifactUrl } from '../api/client';
import { useResource } from '../app/hooks';
import { date, Empty, ErrorNotice, Loading, percent, PageTitle, Status } from '../components/ui';
import { ReportView, TrialTable } from '../features/results/ReportView';
import type { Comparison, Report } from '../types';

export function ResultPage() {
  const { resultId } = useParams();
  return <ResultContent key={resultId} id={resultId!} />;
}

function ResultContent({ id }: { id: string }) {
  const resource = useResource(() => api.result(id), 5000);
  const [selected, setSelected] = useState('');
  const result = resource.data;
  if (!result) return resource.error ? <ErrorNotice message={resource.error} /> : <Loading />;
  const comparison = result.kind === 'experiment' ? result.report as Comparison : undefined;
  const name = selected || comparison?.best_trial || comparison?.trials[0]?.name || '';
  const report = comparison ? comparison.trials.find(trial => trial.name === name) : result.report as Report;
  return <div className="space-y-6"><PageTitle eyebrow="รายงานผล" title={comparison ? 'ผลทดลองปรับค่า' : 'ผลวัดความแม่นยำ'} description={`สร้างเมื่อ ${date(result.created_utc)}`} action={<div className="flex gap-2"><button className="button button-secondary" onClick={() => void resource.refresh()}><RefreshCw size={16} />รีเฟรช</button><a className="button button-secondary" href={artifactUrl(result.path, true)}><Download size={16} />ดาวน์โหลดรายงาน</a></div>} />
    <ErrorNotice message={resource.error} />
    <div className="flex flex-wrap items-center justify-between gap-3"><Link to="/history" className="text-link"><ArrowLeft size={16} />กลับไปผลลัพธ์ทั้งหมด</Link><Status status={result.status} /></div>
    {comparison && <>
      <div className="selection-banner"><span className="selection-icon"><Trophy size={26} /></span><div className="flex-1"><p className="eyebrow">ชุดค่าที่แม่นที่สุด</p><h2>{comparison.best_trial || 'ยังไม่ได้เลือกผู้ชนะ'}</h2><p>เลือกจากคะแนนรวมสูงสุด ถ้าเท่ากันดูตัวอักษรที่อ่านผิดน้อยที่สุด แล้วจึงดูความเร็ว</p></div>{result.selected_config_path && <a href={artifactUrl(result.selected_config_path, true)} className="button button-secondary"><Download size={16} />ดาวน์โหลดชุดค่านี้</a>}</div>
      <div className="card overflow-hidden"><div className="section-heading"><div><h2>เปรียบเทียบทุกชุดค่า</h2><p>กดชื่อชุดค่าเพื่อดูรายละเอียดด้านล่าง คะแนนในตารางนี้มาจากชุดปรับค่า</p></div></div><TrialTable trials={comparison.trials} best={comparison.best_trial} selected={name} onSelect={setSelected} /></div>
      <h2 className="section-title">รายละเอียดของชุดค่า: {name || 'กำลังรอผล'}</h2>
    </>}
    {report ? <ReportView key={report.name || 'evaluation'} report={report} /> : <Empty title="กำลังรอผลของชุดค่าแรก">ดูความคืบหน้าได้จากหน้าของงาน</Empty>}
    {comparison && <section className="card overflow-hidden"><div className="section-heading"><div><h2>ผลทดสอบสุดท้าย</h2><p>นำชุดค่าที่ชนะไปทดสอบกับภาพที่ไม่ได้ใช้ตอนเลือก เพื่อยืนยันว่าแม่นจริง</p></div>{comparison.holdout && <Status status={comparison.holdout.status} />}</div>{comparison.holdout ? <div className="space-y-5 p-5 sm:p-7"><p>คะแนนรวม <b>{percent(comparison.holdout.metrics?.end_to_end?.f1)}</b> · ตัวอักษรที่อ่านผิด <b>{percent(comparison.holdout.metrics?.matched_cer, 2)}</b></p><details><summary className="text-link">ดูผลทดสอบสุดท้ายทั้งหมด</summary><div className="mt-5"><ReportView report={comparison.holdout} /></div></details></div> : <Empty title="ยังไม่มีผลทดสอบสุดท้าย">อาจเลือกข้ามการทดสอบสุดท้ายไว้ หรือการทดลองยังไปไม่ถึงขั้นนี้</Empty>}</section>}
    <div className="guide-banner"><div><h3>คะแนนแต่ละตัวหมายถึงอะไร?</h3><p>คู่มือมีคำอธิบายแบบเข้าใจง่าย พร้อมวิธีคำนวณสำหรับผู้ที่สนใจ</p></div><Link className="text-link whitespace-nowrap" to="/guide">เปิดคู่มือ</Link></div>
  </div>;
}
