import { BookOpen, Check, FolderClock, Home, LoaderCircle, Menu, ScanText, ScrollText, ShieldCheck, X } from 'lucide-react';
import { useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import { api } from '../api/client';
import { activeStatus } from '../components/ui';
import { scriptGuides, scriptOrder } from '../content/scripts';
import { useResource } from './hooks';
import { workflow } from './progress';

const other = [
  { to: '/history', label: 'ผลลัพธ์ที่ผ่านมา', icon: FolderClock },
  { to: '/guide', label: 'คู่มือและคำศัพท์', icon: BookOpen },
  { to: '/logs', label: 'บันทึกของระบบ', icon: ScrollText },
];

export function Layout() {
  const [open, setOpen] = useState(false);
  const health = useResource(api.health, 30000);
  const dataset = useResource(api.dataset, 10000);
  const jobs = useResource(api.jobs, 3000);
  const results = useResource(api.results, 15000);
  const progress = workflow(dataset.data, results.data);
  const running = jobs.data?.find(job => activeStatus(job.status));
  const close = () => setOpen(false);
  const item = ({ isActive }: { isActive: boolean }) => `nav-item ${isActive ? 'nav-active' : ''}`;
  return <div className="app-shell">
    {open && <button className="sidebar-overlay" aria-label="ปิดเมนู" onClick={close} />}
    <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
      <NavLink to="/" className="brand" onClick={close}><span className="brand-icon"><ScanText size={22} /></span><span>OCR Workbench<small>ตรวจการอ่านข้อความจากภาพ</small></span></NavLink>
      <nav aria-label="เมนูหลัก">
        <NavLink to="/" end onClick={close} className={item}><Home size={19} /><span className="flex-1">หน้าแรก</span></NavLink>
        <p className="nav-section">ทำตามลำดับ</p>
        {scriptOrder.map((id, index) => { const step = progress.steps[index]; return <NavLink key={id} to={`/scripts/${id}`} onClick={close} className={item}>
          <span className={`nav-step ${step.done ? 'nav-step-done' : ''}`}>{step.done ? <Check size={13} /> : index + 1}</span>
          <span className="flex-1">{scriptGuides[id].step}</span>
          {index < 2 && !step.done && progress.total > 0 && <span className="nav-count" title={step.detail}>{index === 0 ? progress.covered : progress.saved}/{progress.total}</span>}
        </NavLink>; })}
        <p className="nav-section">อื่น ๆ</p>
        {other.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} onClick={close} className={item}><Icon size={19} /><span className="flex-1">{label}</span></NavLink>)}
      </nav>
      <div className="sidebar-footer"><span className={`connection-dot ${health.data && !health.error ? 'connection-ok' : ''}`} />{health.error ? 'ระบบยังไม่พร้อม ลองรีเฟรชหน้านี้' : health.data ? 'ระบบพร้อมใช้งาน' : 'กำลังเชื่อมต่อ…'}</div>
    </aside>
    <div className="workspace">
      <header className="topbar">
        <div className="flex min-w-0 items-center gap-3"><button type="button" className="icon-button lg:hidden" aria-label={open ? 'ปิดเมนู' : 'เปิดเมนู'} onClick={() => setOpen(!open)}>{open ? <X size={22} /> : <Menu size={22} />}</button><span className="topbar-note"><ShieldCheck size={17} className="shrink-0" /><span>ทำงานบนเครื่องนี้เท่านั้น ภาพและข้อมูลไม่ถูกส่งออกไปที่อื่น</span></span></div>
        {running && <Link to={`/jobs/${running.id}`} className="running-badge"><LoaderCircle size={16} className="animate-spin" /><span className="hidden sm:inline">กำลังทำงาน:</span> {scriptGuides[running.script].step}</Link>}
      </header>
      <main className="main-content"><Outlet /></main>
      <footer className="page-footer">อ่านภาพ → ตรวจแก้เฉลย → วัดความแม่นยำ → ลองปรับค่า</footer>
    </div>
  </div>;
}
