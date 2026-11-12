import { ArrowRight, Check, FlaskConical, Gauge, PencilLine, RefreshCw, ScanText } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api, artifactUrl } from '../api/client';
import { useResource } from '../app/hooks';
import { workflow } from '../app/progress';
import { activeStatus, date, Empty, ErrorNotice, Loading, PageTitle, Status, TextLink } from '../components/ui';
import { scriptGuides, scriptOrder } from '../content/scripts';

const icons = [ScanText, PencilLine, Gauge, FlaskConical];

interface NextAction { label: string; title: string; body: string; action: string; to: string; alternative?: { label: string; to: string } }
/** The single most useful thing to do now, derived from what already exists on disk. */
function nextAction(progress: ReturnType<typeof workflow>, activeJob?: string, latestResult?: string): NextAction {
  const { total, covered, saved } = progress;
  if (activeJob) return { label: 'มีงานกำลังทำอยู่', title: 'ระบบกำลังทำงานให้คุณอยู่', body: 'ดูความคืบหน้าได้เลย ระบบทำได้ครั้งละหนึ่งงาน งานถัดไปเริ่มได้เมื่องานนี้เสร็จ', action: 'ดูความคืบหน้า', to: `/jobs/${activeJob}` };
  if (!total) return { label: 'เริ่มต้น', title: 'เพิ่มภาพลงในโฟลเดอร์ images ก่อน', body: 'ยังไม่พบภาพ วางไฟล์ภาพที่ต้องการตรวจลงในโฟลเดอร์ images ของโปรเจกต์ แล้วกลับมาที่หน้านี้', action: 'อ่านคู่มือ', to: '/guide' };
  if (progress.current === 0) return { label: 'สิ่งที่ควรทำต่อ · ขั้นที่ 1 จาก 4', title: `ให้คอมพิวเตอร์อ่านอีก ${total - covered} ภาพ`, body: 'คอมพิวเตอร์จะอ่านข้อความและตีกรอบให้ก่อน เป็นร่างไว้ให้คุณตรวจ', action: 'ไปขั้นที่ 1', to: '/scripts/create_gt' };
  if (progress.current === 1) return { label: 'สิ่งที่ควรทำต่อ · ขั้นที่ 2 จาก 4', title: `ตรวจแก้และบันทึกเฉลยอีก ${total - saved} ภาพ`, body: `ตอนนี้มีเฉลยแล้ว ${saved} จาก ${total} ภาพ เปิดโปรแกรมตรวจแก้ แก้ข้อความและกรอบให้ถูก แล้วกดบันทึกทีละภาพ`, action: 'เปิดโปรแกรมตรวจแก้', to: '/scripts/gt_editor', alternative: saved ? { label: `หรือวัดความแม่นยำของ ${saved} ภาพที่มีเฉลยแล้ว`, to: '/scripts/evaluate_ocr' } : undefined };
  if (progress.current === 2) return { label: 'สิ่งที่ควรทำต่อ · ขั้นที่ 3 จาก 4', title: 'วัดว่าคอมพิวเตอร์อ่านแม่นแค่ไหน', body: `เฉลยครบทั้ง ${total} ภาพแล้ว ให้คอมพิวเตอร์อ่านใหม่แล้วเทียบกับเฉลย`, action: 'ไปวัดความแม่นยำ', to: '/scripts/evaluate_ocr' };
  if (progress.current === 3) return { label: 'ขั้นที่ 4 จาก 4 · ไม่บังคับ', title: 'ลองปรับค่าเพื่อให้อ่านแม่นขึ้น', body: 'ระบบจะลองหลายชุดค่ากับเฉลยชุดเดิม แล้วบอกว่าแบบไหนแม่นที่สุด', action: 'ไปลองปรับค่า', to: '/scripts/experiment_ocr', alternative: latestResult ? { label: 'หรือดูผลวัดล่าสุด', to: `/results/${latestResult}` } : undefined };
  return { label: 'ครบทุกขั้นตอนแล้ว', title: 'ดูผลลัพธ์ล่าสุดได้เลย', body: 'มีทั้งผลวัดความแม่นยำและผลทดลองปรับค่าแล้ว เปิดดูคะแนนและภาพที่ระบายสีจุดถูกผิดได้', action: 'ดูผลล่าสุด', to: latestResult ? `/results/${latestResult}` : '/history', alternative: { label: 'หรือทดลองชุดค่าใหม่', to: '/scripts/experiment_ocr' } };
}

export function OverviewPage() {
  const dataset = useResource(api.dataset, 10000);
  const jobs = useResource(api.jobs, 2000);
  const results = useResource(api.results, 10000);
  const images = dataset.data?.images || [];
  const active = jobs.data?.filter(job => activeStatus(job.status)) || [];
  const progress = workflow(dataset.data, results.data);
  const next = nextAction(progress, active[0]?.id, results.data?.[0]?.id);
  return <div className="space-y-8">
    <PageTitle eyebrow="หน้าแรก" title="ทำตามทีละขั้น ระบบจะบอกว่าต้องทำอะไรต่อ" description="ตรวจว่าคอมพิวเตอร์อ่านข้อความจากภาพได้แม่นแค่ไหน ใน 4 ขั้นตอน" />
    <ErrorNotice message={dataset.error || jobs.error || results.error} />

    <section className="hero">
      <div className="min-w-0 flex-1">
        <span className="hero-label">{next.label}</span>
        <h2>{next.title}</h2>
        <p>{next.body}</p>
        <div className="hero-actions"><Link to={next.to} className="button button-primary button-large">{next.action}<ArrowRight size={19} /></Link>{next.alternative && <Link to={next.alternative.to} className="text-link">{next.alternative.label}</Link>}</div>
      </div>
      <ol className="hero-steps" aria-label="ความคืบหน้า">{progress.steps.map((step, index) => <li key={step.id} className={step.done ? 'hero-step-done' : index === progress.current ? 'hero-step-current' : ''}><span>{step.done ? <Check size={15} /> : index + 1}</span><div><strong>{scriptGuides[step.id].step}</strong><small>{step.detail}</small></div></li>)}</ol>
    </section>

    {!!active.length && <section className="card overflow-hidden"><div className="section-heading"><h2>งานที่กำลังทำอยู่</h2></div>{active.map(job => <Link className="job-row" to={`/jobs/${job.id}`} key={job.id}><span><strong>{scriptGuides[job.script].step}</strong><small>เริ่ม {date(job.created_utc)}</small></span><Status status={job.status} /><ArrowRight size={18} /></Link>)}</section>}

    <section>
      <div className="pb-4"><h2 className="section-title">4 ขั้นตอน</h2><p className="section-hint">ทำตามลำดับ หรือกดเข้าไปที่ขั้นที่ต้องการได้เลย</p></div>
      <div className="step-grid">{scriptOrder.map((id, index) => { const guide = scriptGuides[id], Icon = icons[index], step = progress.steps[index], current = index === progress.current; return <Link to={`/scripts/${id}`} className={`step-card ${current ? 'step-card-current' : ''}`} key={id}>
        <div className="flex items-center justify-between gap-2"><span className="step-icon"><Icon size={22} /></span><span className={`step-badge ${step.done ? 'step-badge-done' : current ? 'step-badge-current' : ''}`}>{step.done ? 'เสร็จแล้ว' : current ? 'ทำขั้นนี้ต่อ' : step.started ? 'ทำไปบางส่วน' : 'ยังไม่เริ่ม'}</span></div>
        <h3>{index + 1}. {guide.step}</h3>
        <p>{guide.summary}</p>
        <strong>{step.detail}</strong>
      </Link>; })}</div>
    </section>

    <section className="card overflow-hidden">
      <div className="section-heading"><div><h2>ภาพของคุณ</h2><p>ภาพทั้งหมดในโฟลเดอร์ images และสถานะของแต่ละภาพ</p></div><button className="button button-secondary" onClick={() => void dataset.refresh()}><RefreshCw size={16} />รีเฟรช</button></div>
      {dataset.loading ? <Loading /> : images.length ? <div className="table-scroll"><table><thead><tr><th>ภาพ</th><th>คอมพิวเตอร์อ่านแล้ว</th><th>มีเฉลยแล้ว</th><th>เปิดดู</th></tr></thead><tbody>{images.map(image => <tr key={image.path}>
        <td><a className="image-file" href={artifactUrl(image.path)} target="_blank" rel="noreferrer"><img src={artifactUrl(image.path)} alt="" loading="lazy" /><strong>{image.file}</strong></a></td>
        <td><span className={`data-badge ${image.draft ? 'data-ready' : ''}`}>{image.draft ? 'อ่านแล้ว' : 'ยังไม่ได้อ่าน'}</span></td>
        <td><span className={`data-badge ${image.gt ? 'data-saved' : ''}`}>{image.gt ? 'มีเฉลยแล้ว' : 'ยังไม่มีเฉลย'}</span></td>
        <td><div className="flex flex-wrap gap-x-5 gap-y-1">{image.draft_preview && <a className="text-link" target="_blank" rel="noreferrer" href={artifactUrl(image.draft_preview)}>ดูร่าง</a>}{image.gt_preview && <a className="text-link" target="_blank" rel="noreferrer" href={artifactUrl(image.gt_preview)}>ดูเฉลย</a>}{!image.draft_preview && !image.gt_preview && <span className="muted">—</span>}</div></td>
      </tr>)}</tbody></table></div> : <Empty title="ยังไม่มีภาพ">วางไฟล์ภาพลงในโฟลเดอร์ images ของโปรเจกต์ แล้วกดรีเฟรช</Empty>}
    </section>

    <div className="guide-banner"><div><h3>ไม่แน่ใจว่าคำไหนหมายถึงอะไร?</h3><p>คู่มือมีคำอธิบายคำศัพท์ และวิธีอ่านคะแนนแบบเข้าใจง่าย</p></div><TextLink to="/guide">เปิดคู่มือ</TextLink></div>
  </div>;
}
