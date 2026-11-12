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
  await page.getByRole('heading', { name: 'ทำตามทีละขั้น ระบบจะบอกว่าต้องทำอะไรต่อ' }).waitFor();
  await page.getByText('ระบบพร้อมใช้งาน').waitFor();
  const dataset = await (await context.request.get(`${base}/api/dataset`)).json();
  const results = await (await context.request.get(`${base}/api/results`)).json();
  await page.screenshot({ path: join(tmpdir(), 'ocr-workbench-overview.png'), fullPage: true });

  const steps = [['create_gt', 'ให้คอมพิวเตอร์อ่านข้อความจากภาพ', 'เริ่มอ่านภาพ'], ['gt_editor', 'ตรวจแก้ให้เป็นเฉลย', 'เปิดโปรแกรมตรวจแก้'], ['evaluate_ocr', 'วัดความแม่นยำ', 'เริ่มวัดความแม่นยำ'], ['experiment_ocr', 'ลองปรับค่าหาแบบที่แม่นที่สุด', 'เริ่มทดลอง']];
  for (const [id, title, action] of steps) {
    await page.locator(`nav[aria-label="เมนูหลัก"] a[href="/scripts/${id}"]`).click();
    await page.getByRole('heading', { name: title, exact: true }).waitFor();
    await page.getByRole('button', { name: action, exact: true }).waitFor();
  }

  await page.getByLabel('วิธีทดลอง').selectOption('custom');
  await page.getByLabel('ชื่อชุดทดลอง').fill('browser-check');
  await page.locator('details.advanced > summary').click();
  await page.getByLabel('text_det_limit_side_len', { exact: true }).fill('1600');
  assert.equal(await page.getByLabel('ชื่อชุดทดลอง').evaluate(input => input.checkValidity()), true);
  // Dry-run first: a real run is rejected until every image has saved GT.
  await page.getByLabel('ตรวจแผนก่อน ยังไม่รันจริง', { exact: true }).check();
  const preview = page.waitForResponse(response => response.url().endsWith('/api/jobs/preview') && response.status() === 200);
  await page.getByLabel('ข้ามการทดสอบสุดท้าย', { exact: true }).check();
  await preview;
  await page.screenshot({ path: join(tmpdir(), 'ocr-workbench-experiment.png'), fullPage: true });

  if (dataset.images.length) {
    await page.getByRole('button', { name: 'ตรวจแผน', exact: true }).click();
    await page.waitForURL('**/jobs/*');
    await page.getByText('สำเร็จ', { exact: true }).first().waitFor({ timeout: 30000 });
    await page.getByText('รายละเอียดการทำงาน', { exact: false }).first().click();
    await page.getByLabel('รายละเอียดการทำงาน').getByText('browser-check', { exact: false }).waitFor();
  }

  if (results.length) {
    await page.goto(`${base}/results/${results[0].id}`);
    await page.getByRole('heading', { name: /ผลทดลองปรับค่า|ผลวัดความแม่นยำ/ }).waitFor();
    await page.getByText('เวลาอ่านภาพทั้งหมด', { exact: true }).first().waitFor();
    const framed = page.locator('.report-image img').first();
    if (await framed.count()) {
      await framed.waitFor();
      await framed.evaluate(image => image.decode());
    }
    await page.screenshot({ path: join(tmpdir(), 'ocr-workbench-result.png'), fullPage: true });
  }

  await page.goto(`${base}/guide`);
  await page.getByRole('heading', { name: 'คู่มือและคำศัพท์' }).waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'เปิดเมนู', exact: true }).click();
  await page.getByRole('navigation', { name: 'เมนูหลัก' }).getByRole('link', { name: 'หน้าแรก', exact: true }).click();
  await page.getByRole('heading', { name: 'ทำตามทีละขั้น ระบบจะบอกว่าต้องทำอะไรต่อ' }).waitFor();
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Mobile page must not overflow horizontally');
  await page.screenshot({ path: join(tmpdir(), 'ocr-workbench-mobile.png'), fullPage: true });
  for (const path of ['/scripts/create_gt', '/scripts/experiment_ocr', '/history', '/guide', ...(results.length ? [`/results/${results[0].id}`] : [])]) {
    await page.goto(`${base}${path}`);
    await page.locator('h1').waitFor();
    if (path.startsWith('/scripts/')) await page.getByRole('button', { name: steps.find(step => path.endsWith(step[0]))[2], exact: true }).waitFor();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `Mobile overflow: ${path}`);
  }
  assert.deepEqual(errors, [], 'Browser console/page errors');
  console.log('Browser smoke passed: routes, custom form, real CLI dry-run, reports, images, mobile navigation.');
  console.log(`Screenshots: ${tmpdir()}/ocr-workbench-{overview,experiment,result,mobile}.png`);
} finally {
  await browser.close();
}
