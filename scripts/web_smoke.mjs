// Ende-zu-Ende-Test der gebauten Web-App mit Playwright (Chromium):
// startet `vite preview`, analysiert ein Beispielbild, speichert es im Tagebuch,
// prüft alle Seiten und schreibt Screenshots nach docs/screenshots/.
//
// Aufruf (aus dem Repo-Root, nach `make web`): node scripts/web_smoke.mjs
import { spawn } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium, devices } = require('playwright');
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const shots = join(root, 'docs', 'screenshots');
mkdirSync(shots, { recursive: true });
const PORT = 4179;
const URL = `http://127.0.0.1:${PORT}/`;

// eigene Prozessgruppe, damit beim Beenden auch der von npx gestartete Vite-Prozess endet
const server = spawn('npx', ['vite', 'preview', '--port', String(PORT), '--strictPort', '--host', '127.0.0.1'],
  { cwd: join(root, 'web'), stdio: 'pipe', detached: true });
const stopServer = () => { try { process.kill(-server.pid, 'SIGTERM'); } catch { /* schon beendet */ } };
server.stdout.resume();
server.stderr.resume();
for (let i = 0; ; i++) {
  try { if ((await fetch(URL)).ok) break; } catch { /* noch nicht bereit */ }
  if (i > 60) { stopServer(); throw new Error('vite preview startet nicht'); }
  await new Promise((r) => setTimeout(r, 500));
}

const errors = [];
const browser = await chromium.launch();
async function run(name, ctxOpts, fn) {
  const ctx = await browser.newContext(ctxOpts);
  const page = await ctx.newPage();
  page.on('pageerror', (e) => errors.push(`${name}: ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`${name}: ${m.text()}`); });
  try { await fn(page); } finally { await ctx.close(); }
}

try {
  await run('desktop', { viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 }, async (page) => {
    await page.goto(`${URL}#/check`);
    await page.getByText(/Modell bereit/).waitFor({ timeout: 60000 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(shots, 'check-start.png') });
    // Beispiel 3 (Basalzellkarzinom) analysieren
    await page.locator('[data-example]').nth(2).click();
    await page.locator('[data-crop] canvas').waitFor();
    await page.waitForTimeout(400);
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(shots, 'check-crop.png') });
    await page.locator('[data-go]').click();
    await page.getByText(/Ergebnis/).first().waitFor({ timeout: 60000 });
    await page.locator('[data-occ]').click();
    await page.getByText(/Heatmap ein\/aus/).waitFor({ timeout: 60000 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(shots, 'check-result.png'), fullPage: true });
    const zone = await page.locator('.zone-bg .text-xl').first().textContent();
    const percent = await page.locator('[data-result] .text-2xl').first().textContent();
    console.log(`Beispiel BCC: ${zone?.trim()} · Auffälligkeit ${percent?.trim()}`);
    // im Tagebuch speichern
    await page.locator('input[name="name"]').fill('Beispiel Rücken');
    await page.locator('select[name="site"]').selectOption('back');
    await page.getByRole('button', { name: /Speichern/ }).click();
    await page.getByText('Gespeichert.').waitFor({ timeout: 60000 });
    // zweites Foto derselben Stelle (Beispiel 1) für den Verlauf
    await page.goto(`${URL}#/diary`);
    await page.locator('a[href^="#/diary/"]').first().click();
    await page.getByRole('link', { name: /Neues Foto/ }).click();
    await page.locator('[data-example]').nth(0).click();
    await page.locator('[data-go]').click();
    await page.getByText(/Ergebnis/).first().waitFor({ timeout: 60000 });
    await page.getByRole('button', { name: /Speichern/ }).click();
    await page.getByText('Gespeichert.').waitFor({ timeout: 60000 });
    await page.getByRole('link', { name: /Zum Tagebuch/ }).click();
    await page.getByText(/Vergleich/).first().waitFor();
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(shots, 'diary-spot.png'), fullPage: true });
    await page.goto(`${URL}#/diary`);
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(shots, 'diary-list.png') });
    await page.goto(`${URL}#/abcde`);
    await page.locator('input[name="A"]').check();
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(shots, 'abcde.png'), fullPage: true });
    await page.goto(`${URL}#/about`);
    await page.getByText(/Die wichtigsten Zahlen/).waitFor();
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(shots, 'about.png'), fullPage: true });
  });

  await run('mobile', { ...devices['iPhone 13'] }, async (page) => {
    await page.goto(`${URL}#/check`);
    await page.getByText(/Modell bereit/).waitFor({ timeout: 60000 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(shots, 'mobile-start.png') });
    await page.locator('[data-example]').nth(3).click();
    await page.locator('[data-go]').click();
    await page.getByText(/Ergebnis/).first().waitFor({ timeout: 60000 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(shots, 'mobile-result.png') });
    const zone = await page.locator('.zone-bg .text-xl').first().textContent();
    console.log(`Beispiel Melanom (mobil): ${zone?.trim()}`);
  });

  await run('dark-en', { viewport: { width: 1280, height: 900 }, colorScheme: 'dark' }, async (page) => {
    await page.goto(`${URL}#/check`);
    await page.locator('[data-act="lang"]').click();
    await page.getByText(/Model ready/).waitFor({ timeout: 60000 });
    await page.locator('[data-example]').nth(1).click();
    await page.locator('[data-go]').click();
    await page.getByText(/Result/).first().waitFor({ timeout: 60000 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(shots, 'result-dark-en.png'), fullPage: true });
  });
} finally {
  await browser.close();
  stopServer();
}

if (errors.length) {
  console.error('Fehler im Browser:\n' + errors.join('\n'));
  process.exit(1);
}
console.log('Web-Smoke-Test ok, Screenshots in docs/screenshots/');
