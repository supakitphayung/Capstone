export type ScriptId = 'create_gt' | 'gt_editor' | 'evaluate_ocr' | 'experiment_ocr';
export type Config = Record<string, string | number | boolean>;
export interface Trial { name: string; parameters: Config }
export interface Catalog {
  scripts: { id: ScriptId; title: string; file: string; step: number }[];
  baseline: Config;
  parameter_help: Record<string, string>;
  automatic_trials: { name: string; config: Config }[];
}
export interface DatasetImage { id: string; file: string; path: string; draft: boolean; gt: boolean; draft_preview: string | null; gt_preview: string | null }
export interface Dataset { images: DatasetImage[]; folders: Record<string, boolean> }
export interface Preset { id: string; name: string; config: Config }
export interface RunRequest {
  script: ScriptId; input: string; gt: string; drafts: string; config: Config;
  ids: string[]; recursive: boolean; overwrite: boolean; timeout: number;
  tune_only: boolean; combine: boolean; dry_run: boolean; split_file: string;
  experiment_mode: 'automatic' | 'custom'; experiments: Trial[];
  output?: string; font?: string; font_size?: number;
}
export interface Job {
  id: string; script: ScriptId; status: string; created_utc: string; finished_utc: string | null;
  returncode: number | null; command: string; output: string | null; error: string | null;
  result_ids?: string[]; log_sources?: string[];
  progress?: { stage: string; completed_images: number; expected_images: number | null; completed_trials: number; model_loaded: boolean } | null;
  draft_report?: { processed: number; failures: { image: string; error: string }[] } | null;
}
export interface Rates { precision: number; recall: number; f1: number }
export interface RegionDetail { status: string; expected?: string; text?: string; got?: string; iou?: number; cer?: number | null }
export interface Metrics {
  end_to_end: Rates; detection: Rates; matched_cer: number | null; accuracy_percent: number;
  total_gt_positions: number; total_detections: number; correct_positions: number;
  matched_positions: number; wrong_text_positions: number; missed_positions: number; extra_positions: number;
  ignored_gt_positions: number; ignored_detections: number;
  details?: Record<string, RegionDetail>; extras?: { text: string }[];
}
export interface ImageReport {
  id: string; filename: string; status: string; error?: string; ocr_seconds?: number;
  elapsed_seconds?: number; metrics?: Metrics; framed_path?: string | null;
}
export interface Report {
  status: string; name?: string; config?: Config; metrics?: Metrics; images?: ImageReport[];
  ocr_seconds?: number; model_load_seconds?: number | null; peak_rss_mb?: number;
  completed_images?: number; expected_images?: number; elapsed_seconds?: number; error?: string;
}
export interface Comparison { status: string; dataset_id: string; best_trial: string | null; trials: Report[]; holdout: Report | null }
export interface ResultEntry { id: string; kind: 'experiment' | 'evaluation'; name: string; path: string; status: string; created_utc: string | null; best_trial?: string | null }
export interface ResultDetail extends ResultEntry { report: Report | Comparison; selected_config_path: string | null }
export interface Health { status: string; python: string; root: string; dependencies: Record<string, boolean>; error: string | null }
