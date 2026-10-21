import { ArrowUpRight, History, RefreshCw } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useResource } from '../app/hooks';
import { date, Empty, ErrorNotice, Loading, PageTitle, Status } from '../components/ui';
import { scriptGuides } from '../content/scripts';
import { JobPanel } from '../features/runner/JobPanel';

export function HistoryPage() {
  const { jobId } = useParams();
  const jobs = useResource(api.jobs, 2000);
  const results = useResource(api.results, 5000);
  return <div className="space-y-6"><PageTitle eyebrow="RUNS & RESULTS" title={jobId ? 'ติดตามการทำงาน' : 'ประวัติและผลลัพธ์'} description={jobId ? 'ดูสถานะ logs และผลที่ script สร้างในรอบนี้' : 'งานจากเว็บและผลการทดลองเดิมทั้งหมดในโปรเจกต์'} action={<button className="button button-secondary" onClick={() => { void jobs.refresh(); void results.refresh(); }}><RefreshCw size={16} />รีเฟรช</button>} />
    <ErrorNotice message={jobs.error || results.error} />
    {jobId && <JobPanel key={jobId} id={jobId} />}
    <section className="card overflow-hidden"><div className="section-heading"><div><h2>งานที่สั่งผ่านเว็บ</h2><p>เก็บคำสั่ง เวลา และ logs ของแต่ละงานแยกกัน</p></div><History size={19} className="text-slate-400" /></div>{jobs.loading ? <Loading /> : jobs.data?.length ? <div className="table-scroll"><table><thead><tr><th>Script / Job</th><th>สถานะ</th><th>เริ่มทำงาน</th><th>Exit code</th><th /></tr></thead><tbody>{jobs.data.map(job => <tr key={job.id} className={job.id === jobId ? 'selected-row' : ''}><td><Link to={`/jobs/${job.id}`} className="trial-link">{scriptGuides[job.script].step}</Link><small className="mt-1 block font-mono text-slate-400">{job.id.slice(0, 12)}</small></td><td><Status status={job.status} /></td><td className="text-slate-500">{date(job.created_utc)}</td><td className="numeric">{job.returncode ?? '—'}</td><td><Link aria-label={`เปิดงาน ${job.id.slice(0, 8)}`} to={`/jobs/${job.id}`} className="icon-button"><ArrowUpRight size={17} /></Link></td></tr>)}</tbody></table></div> : <Empty title="ยังไม่มีงานที่สั่งผ่านเว็บ">เลือก script จากเมนูเพื่อเริ่มรันงานแรก</Empty>}</section>
    <section className="card overflow-hidden"><div className="section-heading"><div><h2>รายงานผลในโปรเจกต์</h2><p>รวม evaluation และ experiment ที่รันจาก CLI เดิมด้วย</p></div><span className="pill">{results.data?.length || 0} REPORTS</span></div>{results.loading ? <Loading /> : results.data?.length ? <div className="table-scroll"><table><thead><tr><th>รอบการทำงาน</th><th>ประเภท</th><th>สถานะ</th><th>สร้างเมื่อ</th><th /></tr></thead><tbody>{results.data.map(result => <tr key={result.id}><td><Link className="trial-link break-all" to={`/results/${result.id}`}>{result.name}</Link>{result.best_trial && <small className="mt-1 block text-slate-400">Best: {result.best_trial}</small>}</td><td><span className="pill">{result.kind === 'experiment' ? 'EXPERIMENT' : 'EVALUATION'}</span></td><td><Status status={result.status} /></td><td className="text-slate-500">{date(result.created_utc)}</td><td><Link aria-label={`ดูผล ${result.name}`} to={`/results/${result.id}`} className="icon-button"><ArrowUpRight size={17} /></Link></td></tr>)}</tbody></table></div> : <Empty title="ยังไม่มีรายงานผล">เมื่อ script สร้างรายงานแล้ว ผลจะปรากฏที่นี่</Empty>}</section>
  </div>;
}
