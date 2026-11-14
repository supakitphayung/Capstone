import { useRef, useState } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Download,
  Expand,
  ImageOff,
} from 'lucide-react';
import { artifactUrl } from '../../api/client';
import { Empty, number, percent, Status } from '../../components/ui';
import type { ImageReport, Metrics, Report } from '../../types';

function accuracyLabel(metrics?: Metrics) {
  if (!metrics) {
    return '—';
  }

  return `${number(metrics.accuracy_percent, 1)}%`;
}

function metricCardClass(index: number) {
  if (index === 0) {
    return 'metric-card metric-featured';
  }

  return 'metric-card';
}

export function MetricCards({ metrics }: { metrics?: Metrics }) {
  const cards = [
    {
      label: 'คะแนนรวม',
      value: percent(metrics?.end_to_end?.f1),
      hint: 'หากรอบเจอและอ่านถูกทั้งข้อความ',
      technical: 'End-to-end F1',
    },
    {
      label: 'หาตำแหน่งข้อความ',
      value: percent(metrics?.detection?.f1),
      hint: 'ตีกรอบตรงกับเฉลย',
      technical: 'Detection F1',
    },
    {
      label: 'ตัวอักษรที่อ่านผิด',
      value: percent(metrics?.matched_cer, 2),
      hint: 'ยิ่งน้อยยิ่งดี',
      technical: 'Matched CER',
    },
    {
      label: 'อ่านถูกทั้งข้อความ',
      value: accuracyLabel(metrics),
      hint: 'จากข้อความทั้งหมดในเฉลย',
      technical: 'Accuracy',
    },
  ];

  return (
    <div className="metric-grid">
      {cards.map((card, index) => (
        <div className={metricCardClass(index)} key={card.label}>
          <p>{card.label}</p>
          <strong>{card.value}</strong>
          <small>{card.hint}</small>
          <code>{card.technical}</code>
        </div>
      ))}
    </div>
  );
}

function seconds(value: number | null | undefined) {
  if (value == null) {
    return '—';
  }

  return `${number(value, 2)} วินาที`;
}

function completedCount(trial: Report) {
  const fromImages = trial.images?.filter(image => (
    image.status === 'completed'
  )).length;

  return trial.completed_images ?? fromImages ?? 0;
}

function averageSeconds(total: number | null | undefined, count: number) {
  if (!count || total == null) {
    return undefined;
  }

  return total / count;
}

export function TrialTable({
  trials,
  best,
  selected,
  onSelect,
}: {
  trials: Report[];
  best: string | null;
  selected: string;
  onSelect: (name: string) => void;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>ชุดค่า</th>
            <th>สถานะ</th>
            <th>คะแนนรวม</th>
            <th>หาตำแหน่ง</th>
            <th>ตัวอักษรผิด</th>
            <th>อ่านถูกทั้งข้อความ</th>
            <th>เวลาอ่านรวม</th>
            <th>เฉลี่ยต่อภาพ</th>
            <th>หน่วยความจำ</th>
          </tr>
        </thead>
        <tbody>
          {trials.map((trial, index) => {
            const count = completedCount(trial);
            const average = averageSeconds(trial.ocr_seconds, count);
            const rowClass = selected === trial.name ? 'selected-row' : '';

            return (
              <tr key={trial.name || index} className={rowClass}>
                <td>
                  <button
                    className="row-link"
                    onClick={() => onSelect(trial.name || '')}
                  >
                    {trial.name}
                    <span className="sr-only"> — ดูรายละเอียด</span>
                  </button>
                  {best === trial.name && (
                    <span className="winner-badge">ชนะ</span>
                  )}
                </td>
                <td>
                  <Status status={trial.status} />
                </td>
                <td className="numeric font-semibold">
                  {percent(trial.metrics?.end_to_end?.f1, 2)}
                </td>
                <td className="numeric">
                  {percent(trial.metrics?.detection?.f1, 2)}
                </td>
                <td className="numeric">
                  {percent(trial.metrics?.matched_cer, 2)}
                </td>
                <td className="numeric">
                  {trial.metrics
                    ? `${number(trial.metrics.accuracy_percent, 2)}%`
                    : '—'}
                </td>
                <td className="numeric">{seconds(trial.ocr_seconds)}</td>
                <td className="numeric">{seconds(average)}</td>
                <td className="numeric">
                  {trial.peak_rss_mb == null
                    ? '—'
                    : `${number(trial.peak_rss_mb, 0)} MB`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {!trials.length && (
        <Empty title="ยังไม่มีชุดค่าที่ลองเสร็จ">
          ระหว่างรอ ดูความคืบหน้าได้จากหน้าของงาน
        </Empty>
      )}
    </div>
  );
}

function countClass(value: number, tone: string) {
  if (value) {
    return `count-${tone}`;
  }

  return '';
}

export function ReportView({ report }: { report: Report }) {
  const images = report.images || [];
  const [filename, setFilename] = useState(images[0]?.filename || '');

  const image = images.find(item => item.filename === filename) || images[0];
  const detailsRef = useRef<HTMLDivElement>(null);

  const choose = (next: string, scroll = true) => {
    setFilename(next);

    if (scroll) {
      window.setTimeout(() => {
        detailsRef.current?.scrollIntoView?.({
          behavior: 'smooth',
          block: 'start',
        });
      }, 0);
    }
  };

  const metrics = report.metrics;
  const count = report.completed_images
    ?? images.filter(item => item.status === 'completed').length;

  const counts = metrics
    ? [
      ['อ่านถูก', metrics.correct_positions, 'good'],
      ['อ่านผิด', metrics.wrong_text_positions, 'bad'],
      ['หาไม่เจอ', metrics.missed_positions, 'bad'],
      ['ตีกรอบเกิน', metrics.extra_positions, 'bad'],
      ['ไม่นับคะแนน', metrics.ignored_gt_positions, ''],
    ]
    : [];

  return (
    <div className="space-y-5">
      {metrics && (
        <p className="result-summary">
          จากข้อความในเฉลยทั้งหมด <b>{metrics.total_gt_positions}</b> จุด คอมพิวเตอร์อ่านถูกทั้งข้อความ <b>{metrics.correct_positions}</b> จุด
        </p>
      )}

      <MetricCards metrics={metrics} />

      {report.error && (
        <div className="notice notice-error">{report.error}</div>
      )}

      {metrics && (
        <div className="count-strip">
          {counts.map(([label, value, tone]) => (
            <span
              key={String(label)}
              className={countClass(Number(value), String(tone))}
            >
              <b>{value}</b>
              {label}
            </span>
          ))}
        </div>
      )}

      <div className="card">
        <div className="timing-grid">
          <Timing
            label="เวลาอ่านภาพทั้งหมด"
            value={report.ocr_seconds}
            hint={`${count} ภาพที่อ่านสำเร็จ`}
          />
          <Timing
            label="เวลาอ่านเฉลี่ยต่อภาพ"
            value={averageSeconds(report.ocr_seconds, count)}
            hint="เวลาทั้งหมด ÷ จำนวนภาพ"
          />
          <Timing
            label="เวลาเตรียมโปรแกรม"
            value={report.model_load_seconds}
            hint="ทำครั้งเดียวก่อนเริ่มอ่าน"
          />
          <Timing
            label="เวลารวมทั้งงาน"
            value={report.elapsed_seconds}
            hint="รวมเตรียม อ่าน และบันทึกผล"
          />
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="section-heading">
          <div>
            <h2>ผลของแต่ละภาพ</h2>
            <p>
              กดที่แถวของภาพใดก็ได้ ระบบจะเลื่อนลงไปแสดงภาพที่ระบายสีและข้อความของแต่ละจุด
            </p>
          </div>
          <span className="pill">{images.length} ภาพ</span>
        </div>

        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>ภาพ</th>
                <th>สถานะ</th>
                <th>คะแนนรวม</th>
                <th>ตัวอักษรผิด</th>
                <th>เวลาอ่าน</th>
              </tr>
            </thead>
            <tbody>
              {images.map(item => {
                const selected = image?.filename === item.filename;
                const rowClass = `clickable-row ${selected ? 'selected-row' : ''}`;

                return (
                  <tr
                    key={item.filename}
                    className={rowClass}
                    onClick={() => choose(item.filename)}
                  >
                    <td>
                      <button
                        className="row-link"
                        onClick={event => {
                          event.stopPropagation();
                          choose(item.filename);
                        }}
                      >
                        {item.filename}
                      </button>
                      {selected && (
                        <span className="viewing-badge">กำลังดู</span>
                      )}
                    </td>
                    <td>
                      <Status status={item.status} />
                    </td>
                    <td className="numeric">
                      {percent(item.metrics?.end_to_end?.f1)}
                    </td>
                    <td className="numeric">
                      {percent(item.metrics?.matched_cer, 2)}
                    </td>
                    <td className="numeric">{seconds(item.ocr_seconds)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {!images.length && (
          <Empty title="ยังไม่มีผลของแต่ละภาพ">
            ผลจะปรากฏเมื่อระบบอ่านและเทียบภาพเสร็จ
          </Empty>
        )}
      </div>

      {image && (
        <div ref={detailsRef} className="image-details-anchor">
          <ImageDetails
            key={image.filename}
            image={image}
            names={images.map(item => item.filename)}
            onChoose={next => choose(next, false)}
          />
        </div>
      )}

      {report.config && (
        <details className="card details-card">
          <summary>
            <span>
              ชุดค่าที่ใช้ในรอบนี้
              <small>สำหรับผู้ดูแลระบบ</small>
            </span>
          </summary>
          <pre className="json-view mx-5 mb-5">
            {JSON.stringify(report.config, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

function Timing({
  label,
  value,
  hint,
}: {
  label: string;
  value: number | null | undefined;
  hint: string;
}) {
  return (
    <div>
      <p>{label}</p>
      <strong>
        {number(value, 2)}
        <span> วินาที</span>
      </strong>
      <small>{hint}</small>
    </div>
  );
}

function ImageDetails({
  image,
  names,
  onChoose,
}: {
  image: ImageReport;
  names: string[];
  onChoose: (filename: string) => void;
}) {
  const details = Object.entries(image.metrics?.details || {});
  const position = names.indexOf(image.filename);

  return (
    <div className="card overflow-hidden">
      <div className="section-heading">
        <div>
          <h2>{image.filename}</h2>
          <p className="legend">
            <span className="legend-good">เขียว = ถูก</span>
            <span className="legend-bad">แดง = ผิด หาไม่เจอ หรือตีกรอบเกิน</span>
            <span className="legend-skip">เทา = ไม่นับคะแนน</span>
          </p>
        </div>

        {image.framed_path && (
          <div className="flex gap-2">
            <a
              className="button button-secondary button-small"
              target="_blank"
              rel="noreferrer"
              href={artifactUrl(image.framed_path)}
            >
              <Expand size={15} />
              ดูภาพเต็ม
            </a>
            <a
              className="button button-secondary button-small"
              aria-label="ดาวน์โหลดภาพผลลัพธ์"
              href={artifactUrl(image.framed_path, true)}
            >
              <Download size={15} />
            </a>
          </div>
        )}
      </div>

      {names.length > 1 && (
        <div className="image-switcher">
          <button
            className="button button-secondary button-small"
            disabled={position <= 0}
            onClick={() => onChoose(names[position - 1])}
          >
            <ChevronLeft size={16} />
            ภาพก่อนหน้า
          </button>

          <label>
            <span>ภาพที่ {position + 1} จาก {names.length}</span>
            <select
              aria-label="เลือกภาพที่จะดู"
              value={image.filename}
              onChange={event => onChoose(event.target.value)}
            >
              {names.map(name => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </label>

          <button
            className="button button-secondary button-small"
            disabled={position >= names.length - 1}
            onClick={() => onChoose(names[position + 1])}
          >
            ภาพถัดไป
            <ChevronRight size={16} />
          </button>
        </div>
      )}

      {image.error && (
        <div className="notice notice-error m-5">{image.error}</div>
      )}

      {image.framed_path ? (
        <div className="report-image">
          <img
            src={artifactUrl(image.framed_path)}
            alt={`ผลวัดความแม่นยำของ ${image.filename}`}
            loading="lazy"
          />
        </div>
      ) : (
        <div className="empty">
          <ImageOff className="mx-auto mb-3" />
          <p>ยังไม่มีภาพผลลัพธ์</p>
        </div>
      )}

      {!!details.length && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>จุดที่</th>
                <th>ผล</th>
                <th>เฉลย</th>
                <th>คอมพิวเตอร์อ่านได้</th>
                <th>กรอบทับกัน</th>
                <th>ตัวอักษรผิด</th>
              </tr>
            </thead>
            <tbody>
              {details.map(([key, detail]) => (
                <tr key={key}>
                  <td className="numeric">{key.replace(/^pos/, '')}</td>
                  <td>
                    <Status status={detail.status} />
                  </td>
                  <td className="region-text">
                    {detail.expected ?? detail.text ?? '—'}
                  </td>
                  <td className="region-text">{detail.got ?? '—'}</td>
                  <td className="numeric">{percent(detail.iou, 0)}</td>
                  <td className="numeric">{percent(detail.cer, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!!image.metrics?.extras?.length && (
        <div className="extras">
          <strong>ตีกรอบเกิน — คอมพิวเตอร์อ่านได้ แต่ไม่มีในเฉลย</strong>
          <ul>
            {image.metrics.extras.map((extra, index) => (
              <li key={index}>{extra.text}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
