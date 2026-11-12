import { useEffect, useState } from 'react';
import { Check, ChevronDown, Copy, LoaderCircle, MonitorUp, Play, Plus, RotateCcw, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import { ErrorNotice } from '../../components/ui';
import { parameterNames, scriptGuides } from '../../content/scripts';
import type { Catalog, Config, Dataset, Preset, RunRequest, ScriptId } from '../../types';

export function defaultRequest(script: ScriptId, baseline: Config, device = String(baseline.device || 'cpu')): RunRequest {
  return { script, device, input: 'images', gt: 'GroundTruth', drafts: 'GroundTruthDraft', config: { ...baseline },
    ids: [], recursive: false, overwrite: false, timeout: 1800, tune_only: false, combine: true,
    dry_run: false, split_file: 'experiments/dataset_split.json', experiment_mode: 'automatic',
    experiments: [{ name: 'my-setting', parameters: { ...baseline } }] };
}

function ConfigFields({ config, catalog, onChange }: { config: Config; catalog: Catalog; onChange: (value: Config) => void }) {
  return <div className="form-grid">{Object.entries(catalog.parameter_help).map(([key, help]) => <label className="field" key={key}>
    <span>{parameterNames[key] || key} <code className="param-key">{key}</code></span>
    {key === 'text_det_limit_type' ? <select aria-label={key} value={String(config[key])} onChange={event => onChange({ ...config, [key]: event.target.value })}><option value="max">max — จำกัดด้านยาว</option><option value="min">min — จำกัดด้านสั้น</option></select> :
      <input aria-label={key} type="number" required value={Number(config[key])} min={key.includes('thresh') ? 0 : key === 'scale' || key === 'text_det_unclip_ratio' ? 0.01 : 1}
        max={key.includes('thresh') ? 1 : undefined} step={key === 'min_text_length' || key === 'text_det_limit_side_len' ? 1 : 'any'}
        onChange={event => onChange({ ...config, [key]: Number(event.target.value) })} />}
    <small>{help}</small>
  </label>)}</div>;
}

export function RunForm({ script, catalog, dataset, presets }: { script: ScriptId; catalog: Catalog; dataset: Dataset; presets: Preset[] }) {
  const navigate = useNavigate();
  const gpuBuild = Boolean(catalog.device?.gpu_build);
  const [request, setRequest] = useState(() => defaultRequest(script, catalog.baseline, gpuBuild ? 'gpu:0' : undefined));
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
  const custom = experiment && request.experiment_mode === 'custom';
  const editableConfig = !editor && (!experiment || custom);
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

  const folderSelect = <label className="field"><span>{script === 'create_gt' ? 'ต้องการให้อ่านภาพไหน' : 'โฟลเดอร์ภาพ'}</span><select value={request.input} onChange={event => update({ input: event.target.value, ids: [] })}>
    {folders.map(folder => <option key={folder} value={folder}>ทุกภาพในโฟลเดอร์ {folder}</option>)}
    {script === 'create_gt' && <optgroup label="หรือเลือกเพียงภาพเดียว">{dataset.images.map(image => <option key={image.path} value={image.path}>{image.file}</option>)}</optgroup>}
  </select></label>;

  // The chosen setting profile: front and centre only when the user is building their own trials.
  const presetBlock = editableConfig && <div className="space-y-2">
    <div className="flex flex-wrap items-center justify-between gap-2"><label htmlFor="preset" className="field-label">ชุดค่าที่ใช้อ่านภาพ</label><button type="button" className="text-link text-sm" onClick={() => applyPreset('baseline')}><RotateCcw size={14} />กลับไปใช้ค่ามาตรฐาน</button></div>
    <select id="preset" value={preset} onChange={event => applyPreset(event.target.value)}><option value="baseline">ค่ามาตรฐาน (แนะนำ)</option>{presets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}{preset === 'custom' && <option value="custom">ปรับแต่งเอง</option>}</select>
    <p className="field-hint">ค่ามาตรฐานใช้ได้กับงานทั่วไป หากเคยทดลองปรับค่าไว้ ชุดค่าที่ชนะจะมีให้เลือกที่นี่</p>
  </div>;

  return <form onSubmit={event => void run(event)} className="card overflow-hidden">
    <div className="section-heading"><div><h2>{editor ? 'เปิดโปรแกรมตรวจแก้' : 'เลือก แล้วกดเริ่ม'}</h2><p>{editor ? 'โปรแกรมจะเปิดเป็นหน้าต่างแยกบนเครื่องนี้' : 'ไม่ต้องแก้อะไรก็กดเริ่มได้เลย ระบบตั้งค่าที่เหมาะสมไว้ให้แล้ว'}</p></div></div>
    <div className="space-y-6 p-5 sm:p-7">
      {script === 'create_gt' && folderSelect}

      {script === 'evaluate_ocr' && <fieldset><legend className="field-label">ต้องการวัดภาพไหน</legend><p className="field-hint mb-3">ถ้าไม่ติ๊กเลย ระบบจะวัดทุกภาพที่มีเฉลย</p><div className="mb-3 flex flex-wrap gap-2"><button type="button" className="button button-small button-secondary" onClick={() => update({ ids: dataset.images.filter(image => image.gt && image.path.startsWith(request.input + '/')).map(image => image.id) })}>เลือกทุกภาพที่มีเฉลย</button><button type="button" className="button button-small button-secondary" disabled={!request.ids.length} onClick={() => update({ ids: [] })}>ล้างการเลือก{request.ids.length ? ` (${request.ids.length})` : ''}</button></div><div className="image-options">{dataset.images.filter(image => image.path.startsWith(request.input + '/')).map(image => <label key={image.path} className="image-choice"><input type="checkbox" checked={request.ids.includes(image.id)} onChange={event => update({ ids: event.target.checked ? [...request.ids, image.id] : request.ids.filter(id => id !== image.id) })} /><span>{image.file}</span><span className={image.gt ? 'choice-ok' : 'choice-missing'}>{image.gt ? 'มีเฉลย' : 'ยังไม่มีเฉลย'}</span></label>)}</div></fieldset>}

      {experiment && <>
        <label className="field"><span>วิธีทดลอง</span><select aria-label="วิธีทดลอง" value={request.experiment_mode} onChange={event => update({ experiment_mode: event.target.value as 'automatic' | 'custom' })}><option value="automatic">อัตโนมัติ — ให้ระบบลองให้ (แนะนำ)</option><option value="custom">กำหนดเอง — ตั้งชุดค่าที่อยากลองเอง</option></select><small>แบบอัตโนมัติเริ่มที่ {catalog.automatic_trials.length} ชุดค่า แล้วอาจเพิ่มชุดที่รวมค่าที่ดีที่สุดเข้าด้วยกัน</small></label>
        {custom && <div className="trial-box"><div className="mb-4 flex flex-wrap gap-2">{request.experiments.map((trial, index) => <button key={index} type="button" className={`trial-tab ${activeTrial === index ? 'trial-tab-active' : ''}`} onClick={() => { setActiveTrial(index); setPreset('custom'); }}>{trial.name || `ชุดที่ ${index + 1}`}</button>)}<button type="button" className="button button-small button-secondary" onClick={() => { update({ experiments: [...request.experiments, { name: `trial-${request.experiments.length + 1}`, parameters: { ...catalog.baseline } }] }); setActiveTrial(request.experiments.length); setPreset('baseline'); }}><Plus size={15} />เพิ่มชุด</button></div><div className="flex items-end gap-3"><label className="field flex-1"><span>ชื่อชุดทดลอง</span><input aria-label="ชื่อชุดทดลอง" required pattern={"[A-Za-z0-9][A-Za-z0-9_.\\-]{0,100}"} value={request.experiments[activeTrial]?.name || ''} onChange={event => update({ experiments: request.experiments.map((trial, index) => index === activeTrial ? { ...trial, name: event.target.value } : trial) })} /><small>ใช้ตัวอักษรอังกฤษ ตัวเลข จุด ขีดกลาง หรือขีดล่าง และห้ามซ้ำกัน</small></label>{request.experiments.length > 1 && <button type="button" className="icon-button icon-danger mb-7" aria-label="ลบชุดทดลองนี้" onClick={() => { update({ experiments: request.experiments.filter((_, index) => index !== activeTrial) }); setActiveTrial(0); }}><Trash2 size={19} /></button>}</div><div className="mt-5">{presetBlock}</div><p className="field-hint mt-3">ปรับค่าแต่ละตัวของชุดนี้ได้ใน “ตัวเลือกเพิ่มเติม” ด้านล่าง</p></div>}
      </>}

      {!editor && <label className="field"><span>ประมวลผลด้วย</span><select aria-label="ประมวลผลด้วย" value={request.device || 'cpu'} onChange={event => update({ device: event.target.value })}>
        <option value="cpu">CPU</option>
        <option value="gpu:0" disabled={!gpuBuild && request.device !== 'gpu:0'}>GPU (gpu:0){gpuBuild ? ' — แนะนำ' : ' — เครื่องนี้ยังไม่มี paddlepaddle-gpu'}</option>
      </select><small>{gpuBuild ? 'GPU เร็วกว่ามาก แต่เวลาที่วัดได้เทียบกับรอบที่รันบน CPU ไม่ได้ ให้เทียบเฉพาะรอบที่ใช้อุปกรณ์เดียวกัน' : 'Python ที่ใช้รันสคริปต์ติดตั้ง paddlepaddle แบบ CPU อยู่ ถ้าจะใช้ GPU ให้ติดตั้ง paddlepaddle-gpu ตาม README'}{experiment ? ' ใช้กับทุกชุดค่าในการทดลองนี้' : ''}</small></label>}

      {script === 'create_gt' && <Toggle checked={request.overwrite} onChange={overwrite => update({ overwrite })} title="อ่านใหม่ทับร่างเดิม" description="ปกติระบบจะข้ามภาพที่เคยอ่านแล้ว ติ๊กเมื่อต้องการให้อ่านใหม่ทั้งหมด เฉลยที่บันทึกไว้ไม่ถูกแตะ" />}
      {editor && <div className="notice notice-info"><MonitorUp size={21} className="shrink-0" /><div><strong>หน้าต่างโปรแกรมจะขึ้นบนจอของเครื่องนี้</strong><p className="mt-1">แก้ไขและกดบันทึกในหน้าต่างนั้น เสร็จแล้วปิดหน้าต่างได้เลย หน้าเว็บนี้จะอัปเดตจำนวนเฉลยให้เอง</p></div></div>}
      {experiment && <div className="space-y-4"><Toggle checked={request.dry_run} onChange={dry_run => update({ dry_run })} title="ตรวจแผนก่อน ยังไม่รันจริง" description="แสดงว่าจะลองชุดค่าอะไรบ้าง ใช้เวลาไม่กี่วินาที และไม่ต้องมีเฉลยครบ" /><Toggle checked={request.tune_only} onChange={tune_only => update({ tune_only })} title="ข้ามการทดสอบสุดท้าย" description="ทดลองกับชุดปรับค่าอย่างเดียว ไม่ต้องมีเฉลยของชุดทดสอบสุดท้าย" />{request.experiment_mode === 'automatic' && <Toggle checked={request.combine} onChange={combine => update({ combine })} title="ลองรวมค่าที่ดีที่สุดเข้าด้วยกัน" description="เพิ่มอีกหนึ่งชุดค่าที่นำค่าที่ดีที่สุดของแต่ละอย่างมารวมกัน" />}</div>}

      <details className="advanced"><summary><span>ตัวเลือกเพิ่มเติม<small>ปกติไม่ต้องแก้</small></span><ChevronDown size={19} /></summary><div className="space-y-6 pt-5">
        {script !== 'create_gt' && folderSelect}
        {script === 'create_gt' && <Toggle checked={request.recursive} onChange={recursive => update({ recursive })} title="รวมภาพในโฟลเดอร์ย่อยด้วย" />}
        {!custom && presetBlock}
        {editableConfig && <ConfigFields config={config} catalog={catalog} onChange={changeConfig} />}
        {!editor && <div className="fixed-config"><span className="field-label">ค่าที่กำหนดตายตัว (แก้ไม่ได้จากหน้านี้)</span><div className="mt-2 flex flex-wrap gap-2">{Object.entries(catalog.baseline).filter(([key]) => !(key in catalog.parameter_help) && key !== 'device').map(([key, value]) => <span key={key}>{key}: <b>{String(value)}</b></span>)}</div></div>}
        <div className="form-grid">
          {(editor || script === 'evaluate_ocr' || experiment) && <label className="field"><span>โฟลเดอร์เก็บเฉลย</span><input value={request.gt} onChange={event => update({ gt: event.target.value })} /></label>}
          {editor && <label className="field"><span>โฟลเดอร์เก็บร่าง</span><input value={request.drafts} onChange={event => update({ drafts: event.target.value })} /></label>}
          {!editor && <label className="field"><span>โฟลเดอร์เก็บผลลัพธ์ (ไม่บังคับ)</span><input placeholder={script === 'create_gt' ? 'GroundTruthDraft' : `${experiment ? 'experiment' : 'evaluation'}_output`} value={request.output || ''} onChange={event => update({ output: event.target.value || undefined })} /><small>{script === 'create_gt' ? 'ถ้าเปลี่ยน ต้องตั้งโฟลเดอร์เก็บร่างในขั้นที่ 2 ให้ตรงกัน' : 'ระบบแยกโฟลเดอร์ของแต่ละรอบให้อัตโนมัติ'}</small></label>}
          {experiment && <><label className="field"><span>ไฟล์รายการแบ่งภาพ</span><input required value={request.split_file} onChange={event => update({ split_file: event.target.value })} /></label><label className="field"><span>เวลาจำกัดต่อชุดค่า (วินาที)</span><input required type="number" min="1" step="any" value={request.timeout} onChange={event => update({ timeout: Number(event.target.value) })} /></label></>}
          <label className="field"><span>ฟอนต์ไทยบนภาพผลลัพธ์ (ไม่บังคับ)</span><input placeholder="เลือกให้อัตโนมัติ" value={request.font || ''} onChange={event => update({ font: event.target.value || undefined })} /><small>ถ้ากำหนดเอง ไฟล์ฟอนต์ต้องอยู่ในโฟลเดอร์ fonts ของโปรเจกต์</small></label>
          <label className="field"><span>ขนาดตัวอักษรบนภาพผลลัพธ์ (ไม่บังคับ)</span><input type="number" min="1" step="1" placeholder="อัตโนมัติ" value={request.font_size || ''} onChange={event => update({ font_size: event.target.value ? Number(event.target.value) : undefined })} /></label>
        </div>
        <div className="command-preview"><p className="field-label">คำสั่งที่ระบบจะใช้ (สำหรับผู้ดูแลระบบ)</p><pre>{previewError ? 'ยังสร้างคำสั่งไม่ได้ แก้ค่าตามข้อความด้านล่างก่อน' : command || 'กำลังตรวจสอบค่าที่เลือก…'}</pre>{command && <button type="button" className="text-link mt-2 text-sm" onClick={() => { void navigator.clipboard.writeText(command).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1500); }); }}>{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? 'คัดลอกแล้ว' : 'คัดลอกคำสั่ง'}</button>}</div>
      </div></details>

      <ErrorNotice message={error || (previewError && `ยังเริ่มไม่ได้: ${previewError}`)} />
      <div className="submit-row"><p>{editor ? 'ปิดโปรแกรมได้ด้วยปุ่มปิดหน้าต่างตามปกติ' : 'กดเริ่มแล้วระบบจะพาไปหน้าดูความคืบหน้า ปิดหน้าเว็บได้ งานยังทำต่อ'}</p><button className="button button-primary button-large" type="submit" disabled={busy || !dataset.images.length}>{busy ? <LoaderCircle size={19} className="animate-spin" /> : <Play size={19} />}{busy ? 'กำลังเริ่ม…' : request.dry_run && experiment ? 'ตรวจแผน' : scriptGuides[script].action}</button></div>
    </div>
  </form>;
}

function Toggle({ checked, onChange, title, description }: { checked: boolean; onChange: (value: boolean) => void; title: string; description?: string }) {
  return <label className="toggle-row"><input aria-label={title} type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} /><span><strong>{title}</strong>{description && <small>{description}</small>}</span></label>;
}
