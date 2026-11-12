import { useEffect, useRef, useState } from 'react';
import { ArrowRight, ChevronDown, LoaderCircle, Square } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import { useResource } from '../../app/hooks';
import { activeStatus, date, Empty, ErrorNotice, Loading, Status } from '../../components/ui';
import { scriptGuides } from '../../content/scripts';

const outcomes: Record<string, string> = {
  completed: 'งานนี้เสร็จเรียบร้อยแล้ว', completed_with_errors: 'งานเสร็จแล้ว แต่มีบางภาพที่ทำไม่สำเร็จ',
  failed: 'งานนี้ไม่สำเร็จ เปิด “รายละเอียดการทำงาน” ด้านล่างเพื่อดูสาเหตุ', cancelled: 'งานนี้ถูกยกเลิก',
  interrupted: 'งานนี้หยุดกลางคันเพราะระบบถูกปิด ลองเริ่มใหม่อีกครั้ง',
};

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
      } catch (cause) { if (current) setLogError(cause instanceof Error ? cause.message : 'อ่านรายละเอียดไม่สำเร็จ'); }
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
  const active = activeStatus(job.status), editor = job.script === 'gt_editor';
  const progress = job.progress;
  const share = progress?.expected_images ? Math.min(100, Math.round(progress.completed_images / progress.expected_images * 100)) : null;
  return <div className="space-y-5"><ErrorNotice message={resource.error || cancelError || job.error || undefined} /><div className="card overflow-hidden">
    <div className="section-heading"><div><h2>{scriptGuides[job.script].step}</h2><p>เริ่ม {date(job.created_utc)}{job.finished_utc && ` · เสร็จ ${date(job.finished_utc)}`}</p></div><Status status={job.status} /></div>
    <div className="space-y-5 p-5 sm:p-7">
      {active && (editor
        ? <div className="notice notice-info"><LoaderCircle size={20} className="animate-spin shrink-0" /><span>โปรแกรมตรวจแก้เปิดอยู่บนจอของเครื่องนี้ แก้และกดบันทึกในหน้าต่างนั้น เสร็จแล้วปิดหน้าต่างได้เลย</span></div>
        : <div className="progress-info"><div className="flex items-center gap-2"><LoaderCircle size={18} className="animate-spin shrink-0" /><strong>{progress ? (progress.model_loaded ? 'กำลังอ่านภาพ' : 'กำลังเตรียมโปรแกรมอ่านข้อความ อาจใช้เวลาสักครู่') : 'กำลังเตรียมงาน'}</strong></div>
          {progress && <><div className="progress-bar" role="progressbar" aria-label="ความคืบหน้า" aria-valuemin={0} aria-valuemax={100} aria-valuenow={share ?? undefined}><i style={{ width: `${share ?? 0}%` }} /></div><p>เสร็จแล้ว {progress.completed_images} จาก {progress.expected_images ?? '—'} ภาพ{job.script === 'experiment_ocr' && ` · ลองครบแล้ว ${progress.completed_trials} ชุดค่า`}</p></>}
        </div>)}
      {!active && outcomes[job.status] && <p className="job-outcome">{outcomes[job.status]}</p>}
      {job.draft_report && <p className="job-outcome">อ่านสำเร็จ <b>{job.draft_report.processed}</b> ภาพ{job.draft_report.failures.length > 0 && ` · อ่านไม่สำเร็จ ${job.draft_report.failures.length} ภาพ`}</p>}
      <div className="flex flex-wrap items-center gap-3">
        {job.result_ids?.map((resultId, index) => <Link className="button button-primary button-large" to={`/results/${resultId}`} key={resultId}>ดูผลลัพธ์{job.result_ids!.length > 1 ? ` ${index + 1}` : ''}<ArrowRight size={18} /></Link>)}
        {job.script === 'create_gt' && job.status === 'completed' && <Link className="button button-primary button-large" to="/scripts/gt_editor">ไปขั้นถัดไป: ตรวจแก้เฉลย<ArrowRight size={18} /></Link>}
        {editor && job.status === 'completed' && <Link className="button button-primary button-large" to="/scripts/evaluate_ocr">ไปขั้นถัดไป: วัดความแม่นยำ<ArrowRight size={18} /></Link>}
        {!editor && active && <button className="button button-danger" disabled={cancelling || job.status === 'cancelling'} onClick={() => void cancel()}><Square size={15} />{cancelling || job.status === 'cancelling' ? 'กำลังหยุด…' : 'ยกเลิกงานนี้'}</button>}
      </div>
    </div>
  </div>
  <details className="card details-card" open={job.status === 'failed'}>
    <summary><span>รายละเอียดการทำงาน<small>ข้อความจากระบบ ใช้เมื่อต้องการตรวจสอบปัญหา</small></span><ChevronDown size={19} /></summary>
    <div className="space-y-4 px-5 pb-5 sm:px-7 sm:pb-7">
      <div className="terminal-card"><div className="terminal-heading"><span>ข้อความจากระบบ</span><div className="flex items-center gap-3"><select aria-label="แหล่งที่มาของข้อความ" className="terminal-select" value={source} onChange={event => setSource(event.target.value)}>{(job.log_sources || ['console']).map(item => <option key={item} value={item}>{item}</option>)}</select><label className="flex items-center gap-2"><input type="checkbox" checked={follow} onChange={event => setFollow(event.target.checked)} />เลื่อนตามอัตโนมัติ</label></div></div><ErrorNotice message={logError} /><pre ref={terminal} aria-label="รายละเอียดการทำงาน" className="terminal-output">{logs || 'ยังไม่มีข้อความจากระบบ…'}</pre></div>
      {job.script === 'experiment_ocr' && <p className="field-hint">เลือก trial:&lt;ชื่อ&gt; ในช่องด้านบนเพื่อดูข้อความของแต่ละชุดค่า</p>}
      <div className="command-preview"><p className="field-label">คำสั่งที่ใช้ (สำหรับผู้ดูแลระบบ)</p><pre>{job.command}</pre><p className="field-hint mt-2">รหัสงาน {job.id.slice(0, 8)} · รหัสผลลัพธ์จากโปรแกรม (exit code): {job.returncode ?? '—'}</p></div>
    </div>
  </details>
  {!active && !job.result_ids?.length && (job.script === 'evaluate_ocr' || job.script === 'experiment_ocr') && job.status === 'completed' && <Empty title="งานนี้ไม่มีรายงานผล">การตรวจแผนจะแสดงแผนไว้ใน “รายละเอียดการทำงาน” โดยไม่สร้างรายงาน</Empty>}
  </div>;
}
