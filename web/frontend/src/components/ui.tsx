import type { ReactNode } from 'react';
import { AlertCircle, ArrowRight, LoaderCircle } from 'lucide-react';
import { Link } from 'react-router-dom';

export const activeStatus = (status: string) => status === 'running' || status === 'cancelling';
const labels: Record<string, string> = {
  running: 'กำลังทำงาน', cancelling: 'กำลังหยุด', completed: 'สำเร็จ', completed_with_errors: 'สำเร็จบางส่วน',
  failed: 'ไม่สำเร็จ', cancelled: 'ยกเลิกแล้ว', interrupted: 'ถูกขัดจังหวะ',
  correct: 'ถูกต้อง', wrong_text: 'อ่านผิด', missed: 'หาไม่เจอ', extra: 'ตีกรอบเกิน', ignore: 'ไม่นับคะแนน',
};
export function Status({ status }: { status: string }) {
  return <span className={`status status-${status}`}>{activeStatus(status) && <LoaderCircle size={14} className="animate-spin" />}{labels[status] || status}</span>;
}
export function ErrorNotice({ message }: { message?: string }) {
  return message ? <div role="alert" className="notice notice-error"><AlertCircle size={20} className="shrink-0" /><span>{message}</span></div> : null;
}
export function Loading() { return <div role="status" className="loading"><LoaderCircle className="animate-spin" size={22} />กำลังโหลดข้อมูล…</div>; }
export function PageTitle({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-description">{description}</p></div>{action}</div>;
}
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty"><p className="empty-title">{title}</p><div className="mt-2">{children}</div></div>;
}
export function TextLink({ to, children }: { to: string; children: ReactNode }) { return <Link to={to} className="text-link">{children}<ArrowRight size={16} /></Link>; }
export const number = (value: number | null | undefined, digits = 4) => value == null ? '—' : value.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
/** A 0–1 ratio shown as a percentage, which reads more naturally than 0.9773. */
export const percent = (value: number | null | undefined, digits = 1) => value == null ? '—' : `${number(value * 100, digits)}%`;
export const date = (value?: string | null) => value ? new Date(value).toLocaleString('th-TH', { dateStyle: 'medium', timeStyle: 'short' }) : '—';
