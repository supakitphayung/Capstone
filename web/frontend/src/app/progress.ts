import type { Dataset, ResultEntry, ScriptId } from '../types';

export interface StepState { id: ScriptId; done: boolean; started: boolean; detail: string }

/** Where the dataset stands in the four-step workflow; `current` is the first unfinished step (-1 = all done). */
export function workflow(dataset?: Dataset, results?: ResultEntry[]) {
  const images = dataset?.images || [];
  const total = images.length;
  // An image with saved GT no longer needs a draft.
  const covered = images.filter(image => image.draft || image.gt).length;
  const saved = images.filter(image => image.gt).length;
  const evaluations = (results || []).filter(result => result.kind === 'evaluation').length;
  const experiments = (results || []).filter(result => result.kind === 'experiment').length;
  const steps: StepState[] = [
    { id: 'create_gt', done: total > 0 && covered === total, started: covered > 0, detail: `อ่านแล้ว ${covered} จาก ${total} ภาพ` },
    { id: 'gt_editor', done: total > 0 && saved === total, started: saved > 0, detail: `มีเฉลยแล้ว ${saved} จาก ${total} ภาพ` },
    { id: 'evaluate_ocr', done: evaluations > 0, started: evaluations > 0, detail: evaluations ? `วัดแล้ว ${evaluations} ครั้ง` : 'ยังไม่เคยวัด' },
    { id: 'experiment_ocr', done: experiments > 0, started: experiments > 0, detail: experiments ? `ทดลองแล้ว ${experiments} ครั้ง` : 'ยังไม่เคยทดลอง (ไม่บังคับ)' },
  ];
  return { total, covered, saved, evaluations, experiments, steps, current: steps.findIndex(step => !step.done) };
}
