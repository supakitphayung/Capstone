import { useEffect, useState } from 'react';
import { Check, ChevronDown, Copy, LoaderCircle, Play, Plus, RotateCcw, Terminal, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import { ErrorNotice } from '../../components/ui';
import type { Catalog, Config, Dataset, Preset, RunRequest, ScriptId } from '../../types';

export function defaultRequest(script: ScriptId, baseline: Config): RunRequest {
  return { script, input: 'images', gt: 'GroundTruth', drafts: 'GroundTruthDraft', config: { ...baseline },
    ids: [], recursive: false, overwrite: false, timeout: 1800, tune_only: false, combine: true,
    dry_run: false, split_file: 'experiments/dataset_split.json', experiment_mode: 'automatic',
    experiments: [{ name: 'my-setting', parameters: { ...baseline } }] };
}

function ConfigFields({ config, catalog, onChange }: { config: Config; catalog: Catalog; onChange: (value: Config) => void }) {
  return <div className="form-grid">{Object.entries(catalog.parameter_help).map(([key, help]) => <label className="field" key={key}>
    <span className="font-mono text-xs">{key}</span>
    {key === 'text_det_limit_type' ? <select aria-label={key} value={String(config[key])} onChange={event => onChange({ ...config, [key]: event.target.value })}><option value="max">max — จำกัดด้านยาว</option><option value="min">min — จำกัดด้านสั้น</option></select> :
      <input aria-label={key} type="number" required value={Number(config[key])} min={key.includes('thresh') ? 0 : key === 'scale' || key === 'text_det_unclip_ratio' ? 0.01 : 1}
        max={key.includes('thresh') ? 1 : undefined} step={key === 'min_text_length' || key === 'text_det_limit_side_len' ? 1 : 'any'}
        onChange={event => onChange({ ...config, [key]: Number(event.target.value) })} />}
    <small>{help}</small>
  </label>)}</div>;
}

export function RunForm({ script, catalog, dataset, presets }: { script: ScriptId; catalog: Catalog; dataset: Dataset; presets: Preset[] }) {
  const navigate = useNavigate();
  const [request, setRequest] = useState(() => defaultRequest(script, catalog.baseline));
  const [preset, setPreset] = useState('baseline');
  const [activeTrial, setActiveTrial] = useState(0);
  const [command, setCommand] = useState('');
  const [previewError, setPreviewError] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const update = (value: Partial<RunRequest>) => { setRequest(current => ({ ...current, ...value })); setError(''); };
  const experiment = script === 'experiment_ocr';
  const editor = script === 'gt_editor';
  const editableConfig = !editor && (!experiment || request.experiment_mode === 'custom');
  const config = experiment ? request.experiments[activeTrial]?.parameters || catalog.baseline : request.config;
  const folders = [...new Set(['images', ...dataset.images.map(image => image.path.slice(0, image.path.lastIndexOf('/')))])];
  const changeConfig = (next: Config) => {
    setPreset('custom');
    if (experiment) update({ experiments: request.experiments.map((trial, index) => index === activeTrial ? { ...trial, parameters: next } : trial) });
    else update({ config: next });
  };
  const applyPreset = (id: string) => {
    const chosen = id === 'baseline' ? catalog.baseline : presets.find(item => item.id === id)?.config;
    if (!chosen) return;
    changeConfig({ ...chosen });
    setPreset(id);
  };
  useEffect(() => {
    let current = true;
    setCommand(''); setPreviewError('');
    const timer = window.setTimeout(() => {
      api.preview(request).then(value => { if (current) setCommand(value.command); })
        .catch(cause => { if (current) setPreviewError(cause.message); });
    }, 350);
    return () => { current = false; window.clearTimeout(timer); };
  }, [request]);
  const run = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError('');
    try { const job = await api.start(request); navigate(`/jobs/${job.id}`); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'เริ่มงานไม่สำเร็จ'); }
    finally { setBusy(false); }
  };

  return <form onSubmit={event => void run(event)} className="card overflow-hidden">
    <div className="section-heading"><div><h2>{editor ? 'เปิดโปรแกรม GT Editor' : 'ตั้งค่าการรัน'}</h2><p>ใช้ค่าเริ่มต้นได้ทันที หรือปรับให้เหมาะกับงานนี้</p></div><span className="pill">LOCAL CLI</span></div>
    <div className="space-y-6 p-5 sm:p-6">
      <label className="field"><span>{script === 'create_gt' ? 'ภาพหรือโฟลเดอร์ต้นฉบับ' : 'โฟลเดอร์ภาพต้นฉบับ'}</span><select value={request.input} onChange={event => update({ input: event.target.value, ids: [] })}>
        {folders.map(folder => <option key={folder} value={folder}>{folder}/ — ทุกภาพในโฟลเดอร์</option>)}
        {script === 'create_gt' && <optgroup label="เลือกหนึ่งภาพ">{dataset.images.map(image => <option key={image.path} value={image.path}>{image.file}</option>)}</optgroup>}
      </select></label>

      {script === 'evaluate_ocr' && <fieldset><legend className="field-label">ภาพที่ต้องการประเมิน</legend><p className="field-hint mb-3">ไม่เลือก = ทุกภาพในโฟลเดอร์ ภาพที่ไม่มี saved GT จะถูกข้าม</p><div className="image-options">{dataset.images.filter(image => image.path.startsWith(request.input + '/')).map(image => <label key={image.path} className="image-choice"><input type="checkbox" checked={request.ids.includes(image.id)} onChange={event => update({ ids: event.target.checked ? [...request.ids, image.id] : request.ids.filter(id => id !== image.id) })} /><span>{image.file}</span><span className={image.gt ? 'text-emerald-600' : 'text-slate-400'}>{image.gt ? 'มี GT' : 'ไม่มี GT'}</span></label>)}</div></fieldset>}

      {experiment && <>
        <label className="field"><span>ชุดการทดลอง</span><select aria-label="ชุดการทดลอง" value={request.experiment_mode} onChange={event => update({ experiment_mode: event.target.value as 'automatic' | 'custom' })}><option value="automatic">อัตโนมัติ — baseline + single-parameter + focused trials</option><option value="custom">กำหนดเอง — เลือก preset และปรับ parameter</option></select><small>อัตโนมัติเริ่ม {catalog.automatic_trials.length} ชุด แล้วอาจเพิ่ม combined-winners หากยังไม่ซ้ำ</small></label>
        {request.experiment_mode === 'custom' && <div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><div className="mb-4 flex flex-wrap gap-2">{request.experiments.map((trial, index) => <button key={index} type="button" className={`trial-tab ${activeTrial === index ? 'trial-tab-active' : ''}`} onClick={() => { setActiveTrial(index); setPreset('custom'); }}>{trial.name || `Trial ${index + 1}`}</button>)}<button type="button" className="button button-small button-secondary" onClick={() => { update({ experiments: [...request.experiments, { name: `trial-${request.experiments.length + 1}`, parameters: { ...catalog.baseline } }] }); setActiveTrial(request.experiments.length); setPreset('baseline'); }}><Plus size={14} />เพิ่มชุด</button></div><div className="flex items-end gap-3"><label className="field flex-1"><span>ชื่อชุดทดลอง</span><input aria-label="ชื่อชุดทดลอง" required pattern={"[A-Za-z0-9][A-Za-z0-9_.\\-]{0,100}"} value={request.experiments[activeTrial]?.name || ''} onChange={event => update({ experiments: request.experiments.map((trial, index) => index === activeTrial ? { ...trial, name: event.target.value } : trial) })} /><small>ใช้ A–Z, a–z, 0–9, จุด, ขีดกลาง หรือ underscore และชื่อไม่ซ้ำกัน</small></label>{request.experiments.length > 1 && <button type="button" className="icon-button mb-6 text-red-500" aria-label="ลบชุดทดลองนี้" onClick={() => { update({ experiments: request.experiments.filter((_, index) => index !== activeTrial) }); setActiveTrial(0); }}><Trash2 size={18} /></button>}</div></div>}
      </>}

      {editableConfig && <div className="space-y-3"><div className="flex items-center justify-between gap-2"><label htmlFor="preset" className="field-label">ค่าเริ่มต้นของ OCR</label><button type="button" className="text-link text-xs" onClick={() => applyPreset('baseline')}><RotateCcw size={13} />คืนค่า Baseline</button></div><select id="preset" value={preset} onChange={event => applyPreset(event.target.value)}><option value="baseline">Baseline — ค่า default ของ script ปัจจุบัน</option>{presets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}{preset === 'custom' && <option value="custom">ปรับแต่งเอง</option>}</select><div className="config-summary"><span>Detector <b>{String(config.text_det_limit_side_len)} px</b></span><span>Threshold <b>{String(config.text_det_thresh)}</b></span><span>Unclip <b>{String(config.text_det_unclip_ratio)}</b></span><span>Min length <b>{String(config.min_text_length)}</b></span></div></div>}

      {script === 'create_gt' && <div className="space-y-3"><Toggle checked={request.recursive} onChange={recursive => update({ recursive })} title="ค้นหาในโฟลเดอร์ย่อย (recursive)" /><Toggle checked={request.overwrite} onChange={overwrite => update({ overwrite })} title="สร้าง draft ทับของเดิม (overwrite)" description="ค่าเริ่มต้นจะข้ามภาพที่มี draft แล้ว" /></div>}
      {editor && <div className="notice notice-info"><Terminal size={19} className="shrink-0" /><div><strong>หน้าต่าง GUI จะเปิดบนเครื่องนี้</strong><p className="mt-1">แก้ไขและบันทึกจากหน้าต่าง GT Editor ตามปกติ เว็บนี้ใช้เปิดโปรแกรมและติดตามสถานะการทำงาน</p></div></div>}
      {experiment && <div className="space-y-3"><Toggle checked={request.tune_only} onChange={tune_only => update({ tune_only })} title="Tune only" description="ทดลองเฉพาะ tune ไม่รัน holdout และยังไม่ต้องมี GT ของ holdout" />{request.experiment_mode === 'automatic' && <Toggle checked={request.combine} onChange={combine => update({ combine })} title="รวมค่าที่ชนะเป็น combined-winners" />}<Toggle checked={request.dry_run} onChange={dry_run => update({ dry_run })} title="Dry-run: ตรวจแผนก่อนรันจริง" description="ไม่โหลด OCR ไม่ต้องมี saved GT และไม่สร้างผลทดลอง" /></div>}

      <details className="advanced"><summary><span>ตั้งค่าขั้นสูง</span><ChevronDown size={17} /></summary><div className="space-y-6 pt-5">
        {editableConfig && <ConfigFields config={config} catalog={catalog} onChange={changeConfig} />}
        {!editor && <div className="fixed-config"><span className="field-label">ค่าคงที่จาก script</span><div className="mt-2 flex flex-wrap gap-2">{Object.entries(catalog.baseline).filter(([key]) => !(key in catalog.parameter_help)).map(([key, value]) => <span key={key}>{key}: <b>{String(value)}</b></span>)}</div></div>}
        <div className="form-grid">
          {(editor || script === 'evaluate_ocr' || experiment) && <label className="field"><span>โฟลเดอร์ saved GT</span><input value={request.gt} onChange={event => update({ gt: event.target.value })} /></label>}
          {editor && <label className="field"><span>โฟลเดอร์ Draft</span><input value={request.drafts} onChange={event => update({ drafts: event.target.value })} /></label>}
          {!editor && <label className="field"><span>โฟลเดอร์ผลลัพธ์ (ไม่บังคับ)</span><input placeholder={script === 'create_gt' ? 'GroundTruthDraft' : `${experiment ? 'experiment' : 'evaluation'}_output/อัตโนมัติตามงาน`} value={request.output || ''} onChange={event => update({ output: event.target.value || undefined })} /><small>{script === 'create_gt' ? 'ถ้าเปลี่ยน ให้ตั้งโฟลเดอร์ Draft ในหน้า GT Editor ให้ตรงกัน' : 'ระบบแยกโฟลเดอร์งานให้อัตโนมัติภายใต้เส้นทางนี้'}</small></label>}
          {experiment && <><label className="field"><span>ไฟล์แบ่ง dataset</span><input required value={request.split_file} onChange={event => update({ split_file: event.target.value })} /></label><label className="field"><span>Timeout ต่อ trial (วินาที)</span><input required type="number" min="1" step="any" value={request.timeout} onChange={event => update({ timeout: Number(event.target.value) })} /></label></>}
          <label className="field"><span>ฟอนต์ไทย (ไม่บังคับ)</span><input placeholder="เลือกอัตโนมัติ หรือ fonts/NotoSansThai-Regular.ttf" value={request.font || ''} onChange={event => update({ font: event.target.value || undefined })} /><small>ฟอนต์ที่กำหนดเองต้องอยู่ใน fonts/ ของโปรเจกต์</small></label>
          <label className="field"><span>ขนาดป้ายข้อความ (ไม่บังคับ)</span><input type="number" min="1" step="1" placeholder="อัตโนมัติ" value={request.font_size || ''} onChange={event => update({ font_size: event.target.value ? Number(event.target.value) : undefined })} /></label>
        </div>
      </div></details>
      <details className="command-preview"><summary><Terminal size={15} />ตัวอย่างคำสั่งที่จะรัน</summary><p className="field-hint my-3">ระบบจะสร้างไฟล์ config และแทน preview ด้วย ID ของงานเมื่อกดเริ่ม</p>{previewError ? <ErrorNotice message={previewError} /> : <pre>{command || 'กำลังตรวจสอบค่าที่เลือก…'}</pre>}{command && <button type="button" className="text-link mt-3 text-xs" onClick={() => { void navigator.clipboard.writeText(command).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1500); }); }}>{copied ? <Check size={13} /> : <Copy size={13} />}{copied ? 'คัดลอกแล้ว' : 'คัดลอกคำสั่ง'}</button>}</details>
      <ErrorNotice message={error} />
      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-100 pt-5"><p className="text-xs text-slate-500">{editor ? 'ปิดโปรแกรมผ่านหน้าต่าง GUI ตามปกติ' : 'ติดตาม logs และผลลัพธ์ได้ในหน้าประวัติงาน'}</p><button className="button button-primary" type="submit" disabled={busy || !dataset.images.length}>{busy ? <LoaderCircle size={17} className="animate-spin" /> : <Play size={17} />}{busy ? 'กำลังเริ่ม…' : editor ? 'เปิด GT Editor' : request.dry_run && experiment ? 'ตรวจแผน Dry-run' : 'เริ่มรัน Script'}</button></div>
    </div>
  </form>;
}

function Toggle({ checked, onChange, title, description }: { checked: boolean; onChange: (value: boolean) => void; title: string; description?: string }) {
  return <label className="toggle-row"><input aria-label={title} type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} /><span><strong>{title}</strong>{description && <small>{description}</small>}</span></label>;
}
