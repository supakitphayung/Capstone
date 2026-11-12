import { AlertTriangle, ArrowRight, CheckCircle2, ChevronRight, Lightbulb, ListChecks, PackageCheck } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useResource } from '../app/hooks';
import { workflow } from '../app/progress';
import { ErrorNotice, Loading, PageTitle } from '../components/ui';
import { scriptGuides, scriptOrder } from '../content/scripts';
import { RunForm } from '../features/runner/RunForm';
import type { Dataset, ScriptId } from '../types';

export function ScriptPage() {
  const { scriptId } = useParams();
  if (!scriptId || !(scriptId in scriptGuides)) return <ErrorNotice message="ไม่พบขั้นตอนที่เลือก" />;
  return <ScriptContent key={scriptId} id={scriptId as ScriptId} />;
}

function ScriptContent({ id }: { id: ScriptId }) {
  const guide = scriptGuides[id];
  const resource = useResource(async () => { const [catalog, dataset, presets] = await Promise.all([api.catalog(), api.dataset(), api.presets()]); return { catalog, dataset, presets }; });
  return <div className="space-y-6"><PageTitle eyebrow={guide.eyebrow} title={guide.title} description={guide.description} />
    <nav className="workflow-strip" aria-label="ขั้นตอนทั้งหมด">{scriptOrder.map((step, index) => <Link to={`/scripts/${step}`} className={step === id ? 'current-step' : ''} aria-current={step === id ? 'step' : undefined} key={step}><span>{index + 1}</span>{scriptGuides[step].step}{index < 3 && <ChevronRight size={16} />}</Link>)}</nav>
    <ErrorNotice message={resource.error} />
    {resource.data && <Readiness id={id} dataset={resource.data.dataset} />}
    <div className="script-layout"><div className="space-y-6">{resource.data ? <RunForm key={id} script={id} {...resource.data} /> : resource.error ? <button className="button button-secondary" onClick={() => void resource.refresh()}>ลองโหลดอีกครั้ง</button> : <Loading />}
      <section className="card overflow-hidden"><div className="section-heading"><div><h2>เมื่อกดเริ่ม ระบบจะทำอะไรบ้าง</h2><p>อ่านไว้เพื่อความเข้าใจ ไม่ต้องทำเอง</p></div></div><ol className="explanation-flow">{guide.flow.map((step, index) => <li key={step.title}><span className="explanation-number">{index + 1}</span><div><h3>{step.title}</h3><p>{step.body}</p></div></li>)}</ol></section>
    </div><aside className="space-y-5">
      <section className="card p-5"><h2 className="aside-title"><ListChecks size={19} />สิ่งที่ต้องมีก่อน</h2><ul className="explanation-list">{guide.inputs.map(item => <li key={item}>{item}</li>)}</ul></section>
      <section className="card p-5"><h2 className="aside-title"><PackageCheck size={19} />สิ่งที่จะได้</h2><ul className="explanation-list">{guide.outputs.map(item => <li key={item}>{item}</li>)}</ul></section>
      <section className="tip-card"><h2 className="aside-title"><Lightbulb size={19} />ข้อควรรู้</h2><ul className="explanation-list">{guide.tips.map(item => <li key={item}>{item}</li>)}</ul></section>
      <Link className="next-step" to={guide.next.to}><span><small>ขั้นตอนถัดไป</small><strong>{guide.next.label}</strong></span><ArrowRight size={20} /></Link>
    </aside></div>
  </div>;
}

/** One line on whether this step can run now, and what to do first if it cannot. */
function Readiness({ id, dataset }: { id: ScriptId; dataset: Dataset }) {
  const { total, covered, saved } = workflow(dataset);
  let ready = true, message = '', link: { to: string; label: string } | undefined;
  if (!total) { ready = false; message = 'ยังไม่มีภาพในโฟลเดอร์ images วางไฟล์ภาพก่อนจึงจะเริ่มได้'; }
  else if (id === 'create_gt') message = covered === total ? `คอมพิวเตอร์อ่านครบทั้ง ${total} ภาพแล้ว ถ้ากดเริ่มอีกครั้ง ระบบจะข้ามภาพที่อ่านแล้ว เว้นแต่เลือกอ่านใหม่ทับของเดิม` : `อ่านแล้ว ${covered} จาก ${total} ภาพ กดเริ่มเพื่ออ่านภาพที่เหลือ`;
  else if (id === 'gt_editor') {
    if (!covered) { ready = false; message = 'คอมพิวเตอร์ยังไม่ได้อ่านภาพ เปิดโปรแกรมได้ แต่ต้องตีกรอบและพิมพ์ข้อความเองทั้งหมด'; link = { to: '/scripts/create_gt', label: 'ให้คอมพิวเตอร์อ่านก่อน' }; }
    else message = `มีเฉลยแล้ว ${saved} จาก ${total} ภาพ อย่าลืมกดบันทึกทุกครั้งที่แก้เสร็จหนึ่งภาพ`;
  } else if (!saved) { ready = false; message = 'ยังไม่มีเฉลย จึงยังเริ่มขั้นนี้ไม่ได้ ไปตรวจแก้แล้วกดบันทึกอย่างน้อยหนึ่งภาพก่อน'; link = { to: '/scripts/gt_editor', label: 'ไปตรวจแก้เฉลย' }; }
  else if (id === 'evaluate_ocr') message = saved === total ? `พร้อมวัดครบทั้ง ${total} ภาพ` : `พร้อมวัด ${saved} ภาพที่มีเฉลย ส่วนอีก ${total - saved} ภาพที่ยังไม่มีเฉลยจะถูกข้าม`;
  else if (saved < total) { ready = false; message = `มีเฉลย ${saved} จาก ${total} ภาพ การทดลองจริงต้องมีเฉลยครบทุกภาพ ตอนนี้ใช้ได้เฉพาะ “ตรวจแผนก่อน ยังไม่รันจริง”`; link = { to: '/scripts/gt_editor', label: 'ไปตรวจแก้เฉลย' }; }
  else message = `เฉลยครบทั้ง ${total} ภาพ พร้อมทดลอง`;
  return <div className={`notice ${ready ? 'notice-ready' : 'notice-warning'}`}>{ready ? <CheckCircle2 size={20} className="shrink-0" /> : <AlertTriangle size={20} className="shrink-0" />}<span className="flex-1">{message}</span>{link && <Link to={link.to} className="text-link shrink-0">{link.label}<ArrowRight size={16} /></Link>}</div>;
}
