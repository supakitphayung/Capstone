import { ArrowRight, ArrowUpRight, BookOpen, CheckCircle2, FileInput, FileOutput } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useResource } from '../app/hooks';
import { ErrorNotice, Loading, PageTitle } from '../components/ui';
import { scriptGuides, scriptOrder } from '../content/scripts';
import { RunForm } from '../features/runner/RunForm';
import type { ScriptId } from '../types';

export function ScriptPage() {
  const { scriptId } = useParams();
  if (!scriptOrder.includes(scriptId as ScriptId)) return <ErrorNotice message="ไม่พบ script นี้" />;
  return <ScriptContent key={scriptId} id={scriptId as ScriptId} />;
}

function ScriptContent({ id }: { id: ScriptId }) {
  const resource = useResource(async () => { const [catalog, dataset, presets] = await Promise.all([api.catalog(), api.dataset(), api.presets()]); return { catalog, dataset, presets }; }, 10000);
  const guide = scriptGuides[id];
  return <div className="space-y-6"><PageTitle eyebrow={guide.eyebrow} title={guide.title} description={guide.description} action={<span className="script-file">{guide.file}</span>} />
    <div className="workflow-strip">{scriptOrder.map((step, index) => <Link to={`/scripts/${step}`} className={step === id ? 'current-step' : ''} key={step}><span>{index + 1}</span>{scriptGuides[step].step}{index < 3 && <ArrowRight size={14} />}</Link>)}</div>
    <ErrorNotice message={resource.error} />
    <div className="script-layout"><div className="space-y-6">{resource.data ? <RunForm key={id} script={id} {...resource.data} /> : resource.error ? <button className="button button-secondary" onClick={() => void resource.refresh()}>ลองโหลดอีกครั้ง</button> : <Loading />}
      <section className="card overflow-hidden"><div className="section-heading"><div><h2>Flow การทำงาน</h2><p>สิ่งที่ script ทำหลังจากกดรัน</p></div><BookOpen size={19} className="text-blue-500" /></div><ol className="explanation-flow">{guide.flow.map((step, index) => <li key={step.title}><span className="explanation-number">{index + 1}</span><div><h3>{step.title}</h3><p>{step.body}</p></div></li>)}</ol></section>
    </div><aside className="space-y-5"><section className="card p-5"><h2 className="aside-title"><FileInput size={17} />ข้อมูลที่ใช้</h2><ul className="explanation-list">{guide.inputs.map(item => <li key={item}>{item}</li>)}</ul></section><section className="card p-5"><h2 className="aside-title"><FileOutput size={17} />ผลลัพธ์ที่ได้</h2><ul className="explanation-list">{guide.outputs.map(item => <li key={item}>{item}</li>)}</ul></section><section className="tip-card"><h2 className="aside-title"><CheckCircle2 size={17} />ทำความเข้าใจก่อนรัน</h2><ul className="explanation-list">{guide.tips.map(item => <li key={item}>{item}</li>)}</ul></section><Link className="next-step" to={guide.next.to}><span><small>ขั้นตอนถัดไป</small><strong>{guide.next.label}</strong></span><ArrowUpRight size={20} /></Link></aside></div>
  </div>;
}
