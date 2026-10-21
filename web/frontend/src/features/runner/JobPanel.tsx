import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, LoaderCircle, Square, Terminal } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import { useResource } from '../../app/hooks';
import { activeStatus, date, Empty, ErrorNotice, Loading, Status } from '../../components/ui';
import { scriptGuides } from '../../content/scripts';

export function JobPanel({ id }: { id: string }) {
  const resource = useResource(() => api.job(id), 1000);
  const [source, setSource] = useState('console');
  const [logs, setLogs] = useState('');
  const [logError, setLogError] = useState('');
  const [cancelError, setCancelError] = useState('');
  const [cancelling, setCancelling] = useState(false);
  const [follow, setFollow] = useState(true);
  const terminal = useRef<HTMLPreElement>(null);
  const job = resource.data;
  useEffect(() => {
    let current = true, offset = 0, timer: number;
    setLogs(''); setLogError('');
    const poll = async () => {
      try {
        const result = await api.logs(id, source, offset);
        if (!current) return;
        offset = result.offset;
        setLogs(previous => (previous + result.text).slice(-250000));
        setLogError('');
      } catch (cause) { if (current) setLogError(cause instanceof Error ? cause.message : 'อ่าน logs ไม่สำเร็จ'); }
      if (current) timer = window.setTimeout(() => void poll(), 1000);
    };
    void poll();
    return () => { current = false; window.clearTimeout(timer); };
  }, [id, source]);
  useEffect(() => { if (follow && terminal.current) terminal.current.scrollTop = terminal.current.scrollHeight; }, [logs, follow]);
  const cancel = async () => {
    setCancelling(true); setCancelError('');
    try { await api.cancel(id); await resource.refresh(); }
    catch (cause) { setCancelError(cause instanceof Error ? cause.message : 'ยกเลิกไม่สำเร็จ'); }
    finally { setCancelling(false); }
  };
  if (!job) return resource.error ? <ErrorNotice message={resource.error} /> : <Loading />;
  return <div className="space-y-5"><ErrorNotice message={resource.error || cancelError || job.error || undefined} /><div className="card overflow-hidden">
    <div className="section-heading"><div><p className="eyebrow mb-2">JOB / {job.id.slice(0, 8)}</p><h2>{scriptGuides[job.script].step}</h2><p>เริ่ม {date(job.created_utc)}{job.finished_utc && ` · สิ้นสุด ${date(job.finished_utc)}`}</p></div><Status status={job.status} /></div>
    <div className="space-y-4 p-5 sm:p-6">
      {job.progress ? <div className="progress-info"><span className="flex items-center gap-2">{activeStatus(job.status) && <LoaderCircle size={16} className="animate-spin" />}<b>{job.progress.stage}</b></span><span>ภาพสำเร็จ {job.progress.completed_images} / {job.progress.expected_images ?? '—'}</span>{job.script === 'experiment_ocr' && <span>trial/รอบที่สิ้นสุดแล้ว {job.progress.completed_trials}</span>}<span>{job.progress.model_loaded ? 'โหลดโมเดลแล้ว' : 'กำลังเตรียม / โหลดโมเดล'}</span></div> : activeStatus(job.status) && <div className="notice notice-info"><LoaderCircle size={17} className="animate-spin shrink-0" /><span>{job.script === 'gt_editor' ? 'GT Editor กำลังเปิดอยู่บน desktop ปิดผ่านหน้าต่าง GUI เมื่อทำงานเสร็จ' : 'กำลังเตรียมงาน ติดตามรายละเอียดจาก logs ด้านล่าง'}</span></div>}
      {job.draft_report && <p className="text-sm text-slate-600">สร้าง draft สำเร็จ <b>{job.draft_report.processed}</b> ภาพ · ไม่สำเร็จ {job.draft_report.failures.length} ภาพ</p>}
      <details className="command-preview"><summary><Terminal size={15} />คำสั่งที่ใช้จริง</summary><pre className="mt-3">{job.command}</pre></details>
      <div className="flex flex-wrap items-center gap-3">{job.result_ids?.map((resultId, index) => <Link className="button button-primary" to={`/results/${resultId}`} key={resultId}>ดูผลลัพธ์{job.result_ids!.length > 1 ? ` ${index + 1}` : ''}<ArrowUpRight size={16} /></Link>)}{job.script === 'create_gt' && job.status === 'completed' && <Link className="button button-primary" to="/scripts/gt_editor">ตรวจแก้ใน GT Editor<ArrowUpRight size={16} /></Link>}{job.script !== 'gt_editor' && activeStatus(job.status) && <button className="button button-danger" disabled={cancelling || job.status === 'cancelling'} onClick={() => void cancel()}><Square size={14} />{cancelling || job.status === 'cancelling' ? 'กำลังหยุด…' : 'ยกเลิกงานนี้'}</button>}<span className="ml-auto font-mono text-xs text-slate-400">Exit code: {job.returncode ?? '—'}</span></div>
    </div>
  </div>
  <div className="terminal-card"><div className="terminal-heading"><span className="flex items-center gap-2"><Terminal size={16} />Live output</span><div className="flex items-center gap-3"><select aria-label="แหล่งที่มาของ logs" className="terminal-select" value={source} onChange={event => setSource(event.target.value)}>{(job.log_sources || ['console']).map(item => <option key={item} value={item}>{item}</option>)}</select><label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={follow} onChange={event => setFollow(event.target.checked)} />ตาม logs</label></div></div><ErrorNotice message={logError} /><pre ref={terminal} aria-label="Logs ของงาน" className="terminal-output">{logs || 'กำลังรอ output จาก script…'}</pre><div className="terminal-footer"><span>อัปเดตทุก 1 วินาที · UTF-8</span><span>แสดงท้าย logs สูงสุด 250,000 อักขระ</span></div></div>
  {job.script === 'experiment_ocr' && <p className="text-xs text-slate-500">เลือก trial:&lt;ชื่อ&gt; เพื่อดู logs ของ worker แต่ละชุด ส่วน console แสดงความคืบหน้าของตัวควบคุมการทดลอง</p>}
  {!activeStatus(job.status) && !job.result_ids?.length && job.script !== 'gt_editor' && job.script !== 'create_gt' && <Empty title="ยังไม่มีรายงานผลสำหรับงานนี้">Dry-run จะแสดงแผนใน logs; งานที่หยุดก่อนสร้างรายงานอาจยังไม่มีผลลัพธ์</Empty>}
  </div>;
}
