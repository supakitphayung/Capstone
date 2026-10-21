import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import { RunForm, defaultRequest } from './runner/RunForm';
import { JobPanel } from './runner/JobPanel';
import { ReportView } from './results/ReportView';
import type { Catalog, Dataset, Job, Metrics, Preset } from '../types';

const baseline = { device: 'cpu', cpu_threads: 4, text_recognition_batch_size: 1,
  text_det_limit_side_len: 2560, text_det_limit_type: 'max', text_det_thresh: .3,
  text_det_box_thresh: .6, text_det_unclip_ratio: 1.5, text_rec_score_thresh: 0,
  scale: 1, min_text_length: 2 };
const catalog: Catalog = { scripts: [], baseline, parameter_help: {
  text_det_limit_side_len: 'ขนาด detector', text_det_thresh: 'เกณฑ์พิกเซล',
  text_det_limit_type: 'max หรือ min', min_text_length: 'ความยาวขั้นต่ำ' }, automatic_trials: [] };
const dataset: Dataset = { folders: {}, images: [{ id: '1', file: '1.png', path: 'images/1.png', draft: true, gt: true, draft_preview: null, gt_preview: null }] };
const presets: Preset[] = [{ id: 'saved', name: 'รอบก่อน · winner', config: { ...baseline, text_det_limit_side_len: 1600 } }];
const job: Job = { id: 'job123', script: 'create_gt', status: 'running', created_utc: '2026-10-21T00:00:00Z', finished_utc: null, returncode: null, command: 'python create_gt.py', output: 'GroundTruthDraft', error: null, result_ids: [], log_sources: ['console'] };

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function form(script: 'create_gt' | 'experiment_ocr' | 'gt_editor' = 'create_gt') {
  vi.spyOn(api, 'preview').mockResolvedValue({ command: 'python script.py', output: null });
  return render(<MemoryRouter><Routes><Route path="/" element={<RunForm script={script} catalog={catalog} dataset={dataset} presets={presets} />} /><Route path="/jobs/:id" element={<p>หน้าติดตามงาน</p>} /></Routes></MemoryRouter>);
}

describe('run configuration', () => {
  it('selects a saved preset, edits advanced parameters, resets to baseline and starts a job', async () => {
    const start = vi.spyOn(api, 'start').mockResolvedValue(job);
    form();
    fireEvent.change(screen.getByLabelText('ค่าเริ่มต้นของ OCR'), { target: { value: 'saved' } });
    expect(screen.getByLabelText('text_det_limit_side_len')).toHaveValue(1600);
    fireEvent.change(screen.getByLabelText('text_det_thresh'), { target: { value: '.2' } });
    fireEvent.click(screen.getByRole('button', { name: 'คืนค่า Baseline' }));
    expect(screen.getByLabelText('text_det_limit_side_len')).toHaveValue(2560);
    fireEvent.click(screen.getByLabelText('สร้าง draft ทับของเดิม (overwrite)'));
    fireEvent.click(screen.getByRole('button', { name: 'เริ่มรัน Script' }));
    await screen.findByText('หน้าติดตามงาน');
    expect(start.mock.calls[0][0]).toMatchObject({ config: baseline, overwrite: true });
  });
  it('supports named custom trials, preset selection and tune-only', async () => {
    const start = vi.spyOn(api, 'start').mockResolvedValue({ ...job, script: 'experiment_ocr' });
    form('experiment_ocr');
    fireEvent.change(screen.getByLabelText('ชุดการทดลอง'), { target: { value: 'custom' } });
    fireEvent.change(screen.getByLabelText('ค่าเริ่มต้นของ OCR'), { target: { value: 'saved' } });
    fireEvent.change(screen.getByLabelText('ชื่อชุดทดลอง'), { target: { value: 'compact' } });
    fireEvent.click(screen.getByLabelText(/Tune only/));
    fireEvent.click(screen.getByRole('button', { name: 'เริ่มรัน Script' }));
    await screen.findByText('หน้าติดตามงาน');
    expect(start.mock.calls[0][0]).toMatchObject({ experiment_mode: 'custom', tune_only: true,
      experiments: [{ name: 'compact', parameters: { text_det_limit_side_len: 1600 } }] });
  });
  it('shows a rejected concurrent run without losing selected parameters', async () => {
    vi.spyOn(api, 'start').mockRejectedValue(new Error('มีงานกำลังทำงานอยู่'));
    form();
    fireEvent.click(screen.getByRole('button', { name: 'เริ่มรัน Script' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('มีงานกำลังทำงานอยู่');
    expect(screen.getByLabelText('text_det_limit_side_len')).toHaveValue(2560);
  });
  it('launches the original desktop editor without OCR configuration controls', async () => {
    const start = vi.spyOn(api, 'start').mockResolvedValue({ ...job, script: 'gt_editor' });
    form('gt_editor');
    expect(screen.queryByLabelText('ค่าเริ่มต้นของ OCR')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'เปิด GT Editor' }));
    await screen.findByText('หน้าติดตามงาน');
    expect(start.mock.calls[0][0].script).toBe('gt_editor');
  });
  it('builds an independent baseline copy for every form', () => {
    const first = defaultRequest('create_gt', baseline), second = defaultRequest('create_gt', baseline);
    first.config.text_det_thresh = .1;
    expect(second.config.text_det_thresh).toBe(.3);
  });
});

describe('job tracking and results', () => {
  it('shows live output and cancels the selected job', async () => {
    vi.spyOn(api, 'job').mockResolvedValue(job);
    vi.spyOn(api, 'logs').mockResolvedValue({ text: 'กำลังอ่านภาพ 1.png\n', offset: 10 });
    const cancel = vi.spyOn(api, 'cancel').mockResolvedValue({ ...job, status: 'cancelled' });
    render(<MemoryRouter><JobPanel id="job123" /></MemoryRouter>);
    expect(await screen.findByLabelText('Logs ของงาน')).toHaveTextContent('กำลังอ่านภาพ');
    fireEvent.click(await screen.findByRole('button', { name: 'ยกเลิกงานนี้' }));
    await waitFor(() => expect(cancel).toHaveBeenCalledWith('job123'));
  });
  it('displays corpus and per-image times separately and opens region details', () => {
    const metrics: Metrics = { end_to_end: { precision: 1, recall: 1, f1: 1 }, detection: { precision: 1, recall: 1, f1: 1 },
      matched_cer: 0, accuracy_percent: 100, total_gt_positions: 2, total_detections: 2,
      correct_positions: 2, matched_positions: 2, wrong_text_positions: 0, missed_positions: 0,
      extra_positions: 0, ignored_gt_positions: 0, ignored_detections: 0,
      details: { pos1: { status: 'correct', expected: 'ยา', got: 'ยา', iou: .9, cer: 0 } } };
    render(<MemoryRouter><ReportView report={{ status: 'completed', metrics, ocr_seconds: 10, completed_images: 2, model_load_seconds: 1, elapsed_seconds: 12,
      images: [{ id: '1', filename: '1.png', status: 'completed', ocr_seconds: 4, metrics }, { id: '2', filename: '2.png', status: 'completed', ocr_seconds: 6, metrics }] }} /></MemoryRouter>);
    expect(screen.getByText('เวลา OCR รวม').parentElement).toHaveTextContent('10.000');
    expect(screen.getByText('เวลา OCR เฉลี่ยต่อภาพ').parentElement).toHaveTextContent('5.000');
    fireEvent.click(screen.getByRole('button', { name: '2.png' }));
    expect(screen.getAllByText('ยา').length).toBe(2);
  });
});
