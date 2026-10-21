import { BookOpen, Boxes, ChevronRight, CircleDot, FlaskConical, History, LayoutDashboard, Menu, Monitor, ScanLine, Settings2, SquarePen, X } from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { api } from '../api/client';
import { useResource } from './hooks';

const navigation = [
  { to: '/', label: 'ภาพรวม', icon: LayoutDashboard, end: true },
  { to: '/scripts/create_gt', label: 'สร้าง Draft', icon: ScanLine, number: '01' },
  { to: '/scripts/gt_editor', label: 'GT Editor', icon: SquarePen, number: '02' },
  { to: '/scripts/evaluate_ocr', label: 'ประเมิน OCR', icon: Settings2, number: '03' },
  { to: '/scripts/experiment_ocr', label: 'ทดลอง Parameter', icon: FlaskConical, number: '04' },
  { to: '/history', label: 'ประวัติและผลลัพธ์', icon: History },
  { to: '/guide', label: 'คู่มือการทำงาน', icon: BookOpen },
];

export function Layout() {
  const [open, setOpen] = useState(false);
  const health = useResource(api.health, 30000);
  return <div className="app-shell">
    {open && <button className="sidebar-overlay" aria-label="ปิดเมนู" onClick={() => setOpen(false)} />}
    <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
      <NavLink to="/" className="brand" onClick={() => setOpen(false)}><span className="brand-icon"><ScanLine size={23} /></span><span>OCR<span className="font-normal text-slate-400"> Workbench</span><small>CAPSTONE WORKSPACE</small></span></NavLink>
      <div className="px-6 pb-3 pt-9"><p className="eyebrow text-slate-400">WORKSPACE</p></div>
      <nav className="space-y-1 px-3" aria-label="เมนูหลัก">{navigation.map(({ to, label, icon: Icon, number, end }) => <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-active' : ''}`}><Icon size={18} /><span className="flex-1">{label}</span>{number && <span className="nav-number">{number}</span>}</NavLink>)}</nav>
      <div className="sidebar-footer"><div className="flex items-center gap-2 text-sm font-semibold"><Monitor size={16} />Local workspace</div><p>ทำงานกับไฟล์บนเครื่องนี้</p><div className="mt-4 flex items-center gap-2 text-xs"><span className={`connection-dot ${health.data && !health.error ? 'bg-emerald-500' : 'bg-amber-400'}`} />{health.error ? 'Backend ยังไม่พร้อม' : health.data ? 'เชื่อมต่อ FastAPI แล้ว' : 'กำลังเชื่อมต่อ…'}</div></div>
    </aside>
    <div className="workspace">
      <header className="topbar"><div className="flex items-center gap-3"><button type="button" className="icon-button lg:hidden" aria-label={open ? 'ปิดเมนู' : 'เปิดเมนู'} onClick={() => setOpen(!open)}>{open ? <X size={20} /> : <Menu size={20} />}</button><Boxes size={17} className="text-slate-400" /><span className="hidden text-sm text-slate-400 sm:inline">Capstone</span><ChevronRight size={14} className="text-slate-300" /><span className="text-sm font-medium">OCR Workbench</span></div><div className="flex items-center gap-2"><span className="local-badge"><CircleDot size={12} />LOCAL</span><span className="avatar">CW</span></div></header>
      <main className="main-content"><Outlet /></main>
      <footer className="page-footer"><span>OCR Workbench · PP-OCRv5 Mobile</span><span>สร้างร่าง → ตรวจ GT → ประเมิน → ทดลอง</span></footer>
    </div>
  </div>;
}
