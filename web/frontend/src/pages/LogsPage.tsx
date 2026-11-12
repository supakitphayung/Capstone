import { Fragment, useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, RefreshCw, ScrollText } from 'lucide-react';
import { api } from '../api/client';
import { useResource } from '../app/hooks';
import { Empty, ErrorNotice, Loading, PageTitle } from '../components/ui';
import type { ResponseLogEntry } from '../types';

const time = (value: string) => new Date(value).toLocaleString('th-TH', { dateStyle: 'short', timeStyle: 'medium' });
const size = (bytes: number | null) => bytes == null ? '—' : bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`;
const pretty = (value: unknown) => typeof value === 'string' ? value : JSON.stringify(value, null, 2);

export function LogsPage() {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [live, setLive] = useState(true);
  const [open, setOpen] = useState('');
  const logs = useResource(() => api.responseLogs({ q: search, errors_only: filter === 'errors', method: filter === 'post' ? 'POST' : '' }), live ? 3000 : 0);
  const { refresh } = logs;
  useEffect(() => { void refresh(); }, [search, filter, refresh]);
  const entries = logs.data?.entries || [];
  return <div className="space-y-6">
    <PageTitle eyebrow="สำหรับผู้ดูแลระบบ" title="บันทึกของระบบ" description="ทุกครั้งที่หน้าเว็บคุยกับระบบจะถูกบันทึกไว้ที่นี่ ใช้เมื่อต้องการตรวจสอบปัญหาหรือส่งให้ผู้ดูแล กดที่แถวเพื่อดูเนื้อหา" action={<button className="button button-secondary" onClick={() => void logs.refresh()}><RefreshCw size={16} />รีเฟรช</button>} />
    <ErrorNotice message={logs.error} />
    <section className="card overflow-hidden">
      <div className="log-toolbar">
        <input aria-label="ค้นหาใน log" type="search" placeholder="ค้นหาข้อความในบันทึก…" value={search} onChange={event => setSearch(event.target.value)} />
        <select aria-label="ตัวกรอง log" value={filter} onChange={event => setFilter(event.target.value)}>
          <option value="all">ทุกรายการ</option>
          <option value="errors">เฉพาะที่ผิดพลาด</option>
          <option value="post">เฉพาะคำสั่งที่กดจากเว็บ</option>
        </select>
        <label className="flex shrink-0 items-center gap-2"><input type="checkbox" checked={live} onChange={event => setLive(event.target.checked)} />อัปเดตอัตโนมัติ</label>
      </div>
      {logs.loading ? <Loading /> : entries.length ? <div className="table-scroll"><table className="log-table">
        <thead><tr><th /><th>เวลา</th><th>ประเภท</th><th>ที่อยู่</th><th>ผล</th><th>ใช้เวลา</th><th>ขนาด</th></tr></thead>
        <tbody>{entries.map(entry => <Fragment key={entry.id}>
          <tr className={`cursor-pointer ${open === entry.id ? 'selected-row' : ''}`} onClick={() => setOpen(open === entry.id ? '' : entry.id)}>
            <td className="w-8"><button className="text-slate-400" aria-expanded={open === entry.id} aria-label={`ดูรายละเอียด ${entry.method} ${entry.path}`}>{open === entry.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</button></td>
            <td className="numeric">{time(entry.time)}</td>
            <td><span className={`method method-${entry.method.toLowerCase()}`}>{entry.method}</span></td>
            <td className="log-path">{entry.path}{entry.query && <span className="text-slate-400">?{entry.query}</span>}</td>
            <td><span className={`status ${entry.status >= 400 ? 'status-failed' : 'status-completed'}`}>{entry.status}</span></td>
            <td className="numeric">{entry.duration_ms.toFixed(1)} ms</td>
            <td className="numeric">{size(entry.size)}</td>
          </tr>
          {open === entry.id && <tr><td colSpan={7} className="log-detail"><Detail entry={entry} /></td></tr>}
        </Fragment>)}</tbody>
      </table></div> : <Empty title="ไม่มีรายการที่ตรงกับตัวกรอง">ลองล้างคำค้นหาหรือเปลี่ยนตัวกรอง</Empty>}
    </section>
    <div className="notice notice-info"><ScrollText size={19} className="shrink-0" /><div>
      <p>บันทึกเก็บเป็นไฟล์แยกรายวันที่ <code>{logs.data?.folder || '.webui/logs'}/responses-YYYYMMDD.jsonl</code> หน้านี้แสดง {entries.length} รายการล่าสุด</p>
      <p>หน้าเว็บถามระบบซ้ำทุกไม่กี่วินาที คำตอบที่เหมือนครั้งก่อนจึงบันทึกเพียงครั้งเดียว เนื้อหาที่ยาวเกิน 16,000 อักขระถูกตัด และไฟล์ภาพบันทึกเฉพาะผล</p>
    </div></div>
  </div>;
}

function Detail({ entry }: { entry: ResponseLogEntry }) {
  return <div className="space-y-4">
    {entry.request != null && <div><p className="field-label mb-2">ข้อมูลที่หน้าเว็บส่งไป</p><pre className="json-view">{pretty(entry.request)}</pre></div>}
    <div><p className="field-label mb-2">ข้อมูลที่ระบบตอบกลับ{entry.truncated && ' — ตัดให้เหลือ 16,000 อักขระแรก'}</p>
      {entry.response != null ? <pre className="json-view">{pretty(entry.response)}</pre> : <p className="muted">ไม่ได้เก็บเนื้อหา ({entry.content_type || 'ไม่มี content-type'})</p>}</div>
  </div>;
}
