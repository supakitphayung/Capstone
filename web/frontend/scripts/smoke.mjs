// Run against a local backend serving the production build; no OCR inference.
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright';

const base = process.env.OCR_WEB_URL || 'http://127.0.0.1:8000';
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.OCR_CHROME_PATH || (existsSync(chrome) ? chrome : undefined) });
const context = await browser.newContext({ viewport: { width: 1440, height: 1050 } });
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
try {
  await page.goto(base);
  await page.getByRole('heading', { name: 'จากภาพต้นฉบับ สู่ผลที่วัดได้' }).waitFor();
  await page.getByText('เชื่อมต่อ FastAPI แล้ว').waitFor();
  const dataset = await (await context.request.get(`${base}/api/dataset`)).json();
  const results = await (await context.request.get(`${base}/api/results`)).json();
  await page.screenshot({ path: join(tmpdir(), 'ocr-workbench-overview.png'), fullPage: true });

  for (const [id, title] of [['create_gt', 'สร้างร่าง Ground Truth'], ['gt_editor', 'ตรวจแก้ Ground Truth'], ['evaluate_ocr', 'ประเมินความแม่นยำ OCR'], ['experiment_ocr', 'ทดลองและเลือก Parameter']]) {
    await page.locator(`nav[aria-label="เมนูหลัก"] a[href="/scripts/${id}"]`).click();
    await page.getByRole('heading', { name: title, exact: true }).waitFor();
    await page.getByRole('button', { name: id === 'gt_editor' ? 'เปิด GT Editor' : 'เริ่มรัน Script', exact: true }).waitFor();
  }

  await page.getByLabel('ชุดการทดลอง').selectOption('custom');
  await page.getByLabel('ชื่อชุดทดลอง').fill('browser-check');
  await page.getByText('ตั้งค่าขั้นสูง', { exact: true }).click();
  await page.getByLabel('text_det_limit_side_len', { exact: true }).fill('1600');
  assert.equal(await page.getByLabel('ชื่อชุดทดลอง').evaluate(input => input.checkValidity()), true);
  const preview = page.waitForResponse(response => response.url().endsWith('/api/jobs/preview') && response.status() === 200);
  await page.getByLabel('Tune only', { exact: true }).check();
  await preview;
  await page.screenshot({ path: join(tmpdir(), 'ocr-workbench-experiment.png'), fullPage: true });

  if (dataset.images.length) {
    await page.getByLabel('Dry-run: ตรวจแผนก่อนรันจริง', { exact: true }).check();
    await page.getByRole('button', { name: 'ตรวจแผน Dry-run', exact: true }).click();
    await page.waitForURL('**/jobs/*');
    await page.getByText('สำเร็จ', { exact: true }).first().waitFor({ timeout: 30000 });
    await page.getByLabel('Logs ของงาน').getByText('browser-check', { exact: false }).waitFor();
  }

  if (results.length) {
    await page.goto(`${base}/results/${results[0].id}`);
    await page.getByRole('heading', { name: /ผลการทดลอง Parameter|ผลประเมิน OCR/ }).waitFor();
    await page.getByText('เวลา OCR รวม', { exact: true }).first().waitFor();
    const framed = page.locator('.report-image img').first();
    if (await framed.count()) {
      await framed.waitFor();
      await framed.evaluate(image => image.decode());
    }
    await page.screenshot({ path: join(tmpdir(), 'ocr-workbench-result.png'), fullPage: true });
  }

  await page.goto(`${base}/guide`);
  await page.getByRole('heading', { name: 'เข้าใจทุกขั้น ก่อนดูคะแนน' }).waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'เปิดเมนู', exact: true }).click();
  await page.getByRole('navigation', { name: 'เมนูหลัก' }).getByRole('link', { name: 'ภาพรวม', exact: true }).click();
  await page.getByRole('heading', { name: 'จากภาพต้นฉบับ สู่ผลที่วัดได้' }).waitFor();
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Mobile page must not overflow horizontally');
  await page.screenshot({ path: join(tmpdir(), 'ocr-workbench-mobile.png'), fullPage: true });
  for (const path of ['/scripts/create_gt', '/scripts/experiment_ocr', '/history', '/guide', ...(results.length ? [`/results/${results[0].id}`] : [])]) {
    await page.goto(`${base}${path}`);
    await page.locator('h1').waitFor();
    if (path.startsWith('/scripts/')) await page.getByRole('button', { name: 'เริ่มรัน Script', exact: true }).waitFor();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `Mobile overflow: ${path}`);
  }
  assert.deepEqual(errors, [], 'Browser console/page errors');
  console.log('Browser smoke passed: routes, custom form, real CLI dry-run, reports, images, mobile navigation.');
  console.log(`Screenshots: ${tmpdir()}/ocr-workbench-{overview,experiment,result,mobile}.png`);
} finally {
  await browser.close();
}
