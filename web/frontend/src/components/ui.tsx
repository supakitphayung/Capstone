import type { ReactNode } from 'react';
import { AlertCircle, ArrowUpRight, LoaderCircle } from 'lucide-react';
import { Link } from 'react-router-dom';

export const activeStatus = (status: string) => status === 'running' || status === 'cancelling';
const labels: Record<string, string> = { running: 'กำลังทำงาน', cancelling: 'กำลังหยุด', completed: 'สำเร็จ', completed_with_errors: 'สำเร็จบางส่วน', failed: 'ไม่สำเร็จ', cancelled: 'ยกเลิกแล้ว', interrupted: 'หยุดติดตาม', correct: 'ถูกทั้งหมด', wrong_text: 'ข้อความผิด', missed: 'หาไม่เจอ', ignore: 'Ignore' };
export function Status({ status }: { status: string }) {
  return <span className={`status status-${status}`}>{activeStatus(status) && <LoaderCircle size={12} className="animate-spin" />}{labels[status] || status}</span>;
}
export function ErrorNotice({ message }: { message?: string }) {
  return message ? <div role="alert" className="notice notice-error"><AlertCircle size={18} className="shrink-0" /><span>{message}</span></div> : null;
}
export function Loading() { return <div role="status" className="flex items-center justify-center gap-3 p-12 text-slate-500"><LoaderCircle className="animate-spin" size={20} />กำลังโหลดข้อมูล…</div>; }
export function PageTitle({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-description">{description}</p></div>{action}</div>;
}
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty"><p className="font-semibold text-slate-700">{title}</p><div className="mt-2 text-sm text-slate-500">{children}</div></div>;
}
export function TextLink({ to, children }: { to: string; children: ReactNode }) { return <Link to={to} className="text-link">{children}<ArrowUpRight size={15} /></Link>; }
export const number = (value: number | null | undefined, digits = 4) => value == null ? 'n/a' : value.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
export const date = (value?: string | null) => value ? new Date(value).toLocaleString('th-TH', { dateStyle: 'medium', timeStyle: 'short' }) : '—';
