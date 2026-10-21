import { useState } from 'react';
import { Download, RefreshCw, Trophy } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { api, artifactUrl } from '../api/client';
import { useResource } from '../app/hooks';
import { Empty, ErrorNotice, Loading, number, PageTitle, Status } from '../components/ui';
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
  return <div className="space-y-6"><PageTitle eyebrow={result.kind === 'experiment' ? 'EXPERIMENT REPORT' : 'EVALUATION REPORT'} title={result.kind === 'experiment' ? 'ผลการทดลอง Parameter' : 'ผลประเมิน OCR'} description={result.name} action={<div className="flex gap-2"><button className="icon-button" aria-label="รีเฟรชรายงาน" onClick={() => void resource.refresh()}><RefreshCw size={17} /></button><a className="button button-secondary" href={artifactUrl(result.path, true)}><Download size={16} />รายงาน JSON</a></div>} />
    <ErrorNotice message={resource.error} />
    <div className="flex flex-wrap items-center justify-between gap-3"><Link to="/history" className="text-link text-sm">← กลับไปประวัติ</Link><Status status={result.status} /></div>
    {comparison && <>
      <div className="selection-banner"><span className="selection-icon"><Trophy size={23} /></span><div className="flex-1"><p className="eyebrow">SELECTED USING TUNE ONLY</p><h2>{comparison.best_trial || 'ยังไม่ได้เลือกผู้ชนะ'}</h2><p>E2E F1 สูงสุด → CER ต่ำสุด → เวลา OCR ต่ำสุด → Peak RSS ต่ำสุด</p></div>{result.selected_config_path && <a href={artifactUrl(result.selected_config_path, true)} className="button button-secondary"><Download size={15} />Selected config</a>}</div>
      <div className="card overflow-hidden"><div className="section-heading"><div><h2>เปรียบเทียบทุก Trial</h2><p>คลิกชื่อชุดเพื่อดูรายละเอียด · OCR รวมเป็นผลรวมทุกภาพใน split นั้น</p></div><span className="pill">TUNE</span></div><TrialTable trials={comparison.trials} best={comparison.best_trial} selected={name} onSelect={setSelected} /></div>
      <div className="flex items-center justify-between"><h2 className="section-title">รายละเอียด: {name || 'กำลังรอผล'}</h2><span className="pill">TUNE</span></div>
    </>}
    {report ? <ReportView key={report.name || 'evaluation'} report={report} /> : <Empty title="กำลังรอรายงาน trial แรก">ดูความคืบหน้าได้จากหน้า logs ของงาน</Empty>}
    {comparison && <section className="card overflow-hidden"><div className="section-heading"><div><h2>Holdout</h2><p>ประเมินเฉพาะ config ที่เลือกแล้ว คะแนนส่วนนี้ไม่มีผลต่อการเลือกผู้ชนะ</p></div>{comparison.holdout && <Status status={comparison.holdout.status} />}</div>{comparison.holdout ? <div className="space-y-5 p-5"><p className="text-sm text-slate-500">End-to-end F1: <b className="text-slate-800">{number(comparison.holdout.metrics?.end_to_end?.f1)}</b> · Matched CER: <b className="text-slate-800">{number(comparison.holdout.metrics?.matched_cer)}</b></p><details><summary className="cursor-pointer text-sm font-semibold text-blue-600">ดูผล Holdout ทั้งหมด</summary><div className="mt-5"><ReportView report={comparison.holdout} /></div></details></div> : <Empty title="ยังไม่มีผล Holdout">อาจเป็นการรัน tune-only หรือยังไม่ถึงขั้นประเมิน holdout</Empty>}</section>}
    <div className="guide-banner"><p>Matched CER คิดเฉพาะกรอบที่จับคู่ได้ ส่วนคะแนนรวมใช้ counts ของทุกภาพ</p><Link className="text-link whitespace-nowrap" to="/guide">อ่านวิธีคิดคะแนน →</Link></div>
  </div>;
}
