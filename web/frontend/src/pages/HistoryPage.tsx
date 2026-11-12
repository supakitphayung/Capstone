import { ArrowRight, RefreshCw } from 'lucide-react';
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
  return <div className="space-y-6"><PageTitle eyebrow={jobId ? 'ความคืบหน้า' : 'ผลลัพธ์ที่ผ่านมา'} title={jobId ? 'ดูความคืบหน้าของงาน' : 'ผลลัพธ์และงานที่ผ่านมา'} description={jobId ? 'หน้านี้อัปเดตเองทุกวินาที ปิดหน้าเว็บได้ งานยังทำต่อ' : 'ผลวัดความแม่นยำ ผลทดลอง และงานทั้งหมดที่เคยสั่งจากเว็บนี้'} action={<button className="button button-secondary" onClick={() => { void jobs.refresh(); void results.refresh(); }}><RefreshCw size={16} />รีเฟรช</button>} />
    <ErrorNotice message={jobs.error || results.error} />
    {jobId && <JobPanel key={jobId} id={jobId} />}
    <section className="card overflow-hidden"><div className="section-heading"><div><h2>รายงานผล</h2><p>กดที่รายการเพื่อดูคะแนนและภาพที่ระบายสีจุดถูกผิด</p></div><span className="pill">{results.data?.length || 0} รายการ</span></div>{results.loading ? <Loading /> : results.data?.length ? <div className="table-scroll"><table><thead><tr><th>รายงาน</th><th>สถานะ</th><th>วันที่</th><th /></tr></thead><tbody>{results.data.map(result => <tr key={result.id}><td><Link className="row-link" to={`/results/${result.id}`}>{result.kind === 'experiment' ? 'ผลทดลองปรับค่า' : 'ผลวัดความแม่นยำ'}</Link><small className="row-note">{result.best_trial ? `ชุดค่าที่ชนะ: ${result.best_trial} · ` : ''}{result.name}</small></td><td><Status status={result.status} /></td><td>{date(result.created_utc)}</td><td className="text-right"><Link aria-label={`ดูผล ${result.name}`} to={`/results/${result.id}`} className="button button-small button-secondary">ดูผล<ArrowRight size={15} /></Link></td></tr>)}</tbody></table></div> : <Empty title="ยังไม่มีรายงานผล">เมื่อวัดความแม่นยำหรือทดลองปรับค่าเสร็จ รายงานจะมาอยู่ที่นี่</Empty>}</section>
    <section className="card overflow-hidden"><div className="section-heading"><div><h2>งานที่เคยสั่ง</h2><p>ทุกครั้งที่กดเริ่มจากเว็บนี้</p></div></div>{jobs.loading ? <Loading /> : jobs.data?.length ? <div className="table-scroll"><table><thead><tr><th>งาน</th><th>สถานะ</th><th>เริ่มเมื่อ</th><th /></tr></thead><tbody>{jobs.data.map(job => <tr key={job.id} className={job.id === jobId ? 'selected-row' : ''}><td><Link to={`/jobs/${job.id}`} className="row-link">{scriptGuides[job.script].step}</Link></td><td><Status status={job.status} /></td><td>{date(job.created_utc)}</td><td className="text-right"><Link aria-label={`เปิดงาน ${job.id.slice(0, 8)}`} to={`/jobs/${job.id}`} className="button button-small button-secondary">ดูรายละเอียด<ArrowRight size={15} /></Link></td></tr>)}</tbody></table></div> : <Empty title="ยังไม่เคยสั่งงาน">เริ่มจากขั้นที่ 1 ในเมนูด้านซ้าย</Empty>}</section>
  </div>;
}
