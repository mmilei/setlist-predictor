// Captures the top of report.html for the README.   usage: node story/screenshot.mjs
import { chromium } from 'playwright';
import { pathToFileURL } from 'node:url';
import { mkdirSync } from 'node:fs';

mkdirSync('docs', { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1000, height: 1100 }, deviceScaleFactor: 2, colorScheme: 'light' });
await page.goto(pathToFileURL('report.html').href, { waitUntil: 'networkidle' });
await page.evaluate(async () => { await document.fonts.ready; });
await page.screenshot({ path: 'docs/report.png' });
await browser.close();
