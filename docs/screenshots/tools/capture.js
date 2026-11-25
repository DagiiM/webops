// Capture the README screenshots. See docs/screenshots/README.md for the full recipe.
//   NODE_PATH=$(npm root -g) node capture.js <base-url> <output-dir>
// Needs a server running against the seeded demo database (tools/seed_demo.py) as a NON-ROOT user, so the managed
// databases deployed below are real. Everything on screen is fictional demo data.
const { chromium } = require('playwright');
const { execSync } = require('child_process');
const path = require('path');

const BASE = process.argv[2] || 'http://webops.example:8767';       // webops.example resolves to the local demo server (see launch args)
const OUT = process.argv[3] || path.join(__dirname, '..');
const SHELL = process.env.WEBOPS_SHELL_CMD;            // runs ids.py in the panel's Django shell; %s is replaced by its path
const shot = (page, name, opts = {}) => page.screenshot({ path: path.join(OUT, name + '.png'), ...opts });
const HIDE = '.webops-toast-container,[class*="toast"],#uiProgress{display:none!important}';

// The theme is chosen before each navigation (window.name survives it), so every page is loaded exactly once.
// Loading pages twice used to trip the panel's own per-IP rate limit.
const THEME_INIT = () => { try { localStorage.setItem('webops-theme', window.name === 'light' ? 'light' : 'dark'); } catch (e) {} };
async function open(page, url, themeName = 'dark') {
  await page.evaluate(t => { window.name = t; }, themeName).catch(() => {});
  await page.goto(BASE + url, { waitUntil: 'load' });
  await page.addStyleTag({ content: HIDE });
  await page.waitForTimeout(500);
}

(async () => {
  const getIds = () => JSON.parse(execSync(SHELL.replace('%s', path.join(__dirname, 'ids.py')), { encoding: 'utf8' }).trim().split('\n').pop());
  let ids = null;
  const browser = await chromium.launch({ args: ['--host-resolver-rules=MAP webops.example 127.0.0.1'] });
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 860 }, deviceScaleFactor: 1 });
  await ctx.addInitScript(THEME_INIT);
  const page = await ctx.newPage();

  // Logged-out sign-in page first.
  await open(page, '/auth/login/');
  await shot(page, '01-sign-in');

  await page.fill('input[name=username]', 'admin');
  await page.fill('input[name=password]', 'admin-pass-123');
  await Promise.all([page.waitForNavigation().catch(() => {}), page.click('button[type=submit]')]);

  // Real managed databases, deployed through the real page.
  for (const [engine, name] of [['postgresql', 'orders'], ['redis', 'cache'], ['sqlite', 'notes']]) {
    await page.goto(BASE + '/databases/deploy/');
    await page.check(`input[name=engine][value=${engine}]`, { force: true });
    await page.fill('#db-name', name);
    await Promise.all([page.waitForNavigation({ timeout: 90000 }), page.click('#deployBtn')]);
  }

  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true });
  await phone.addInitScript(THEME_INIT);
  const mp = await phone.newPage();
  await mp.goto(BASE + '/auth/login/');
  await mp.fill('input[name=username]', 'admin'); await mp.fill('input[name=password]', 'admin-pass-123');
  await Promise.all([mp.waitForNavigation().catch(() => {}), mp.click('button[type=submit]')]);
  await open(mp, '/', 'dark');                                       await shot(mp, '18-overview-phone');
  await open(mp, '/deployments/', 'dark');                           await shot(mp, '19-deployments-phone');
  await phone.close();

  ids = getIds();                                       // marks the demo worker as just seen
  await open(page, '/', 'dark');                       await shot(page, '02-overview-dark');
  // The sidebar footer: account menu open, then the collapsed rail.
  await page.click('#userMenuTrigger'); await page.waitForTimeout(400);
  await shot(page, '20-sidebar-account-menu');
  await page.keyboard.press('Escape'); await page.waitForTimeout(200);
  await page.click('#btn-toggle-sidebar'); await page.waitForTimeout(700);
  await shot(page, '21-sidebar-collapsed');
  await page.click('#btn-toggle-sidebar'); await page.waitForTimeout(500);
  ids = getIds();
  await open(page, '/', 'light');                      await shot(page, '03-overview-light');
  ids = getIds();
  await open(page, '/deployments/', 'dark');           await shot(page, '04-deployments');

  // New deployment with the safety review result. The repository does not exist, so the analysis response is
  // mocked here; the panel itself produces exactly this shape (see apps/deployments/services/ai_assist.py).
  await page.route('**/deployments/ai-assist/', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
    ok: true, provider: null, notices: [], plan: null,
    safety: { verdict: 'review', decision: 'needs_operator', ai: { status: 'ran', summary: 'A small landing page that loads one external analytics script.', provider: 'OpenAI' },
              findings: [{ severity: 'review', title: 'Password form posts to another site', detail: 'login.html has a password field whose form submits to an external address.' },
                         { severity: 'warn', title: 'Secret-looking file in the repository', detail: '.env.local is committed. Treat it as exposed.' }] },
    analysis: { owner: 'acme', repo: 'storefront', kind: 'static', kinds: [], manifests: [], details: {}, static_candidate: true, private: false, language: 'HTML',
                description: '', env_vars: [], verdict: 'can_deploy', reason: 'A plain static site.', suggest: { name: 'storefront', branch: 'main', static_only: true } } }) }));
  await open(page, '/deployments/create/', 'dark');
  await page.fill('#repo_url', 'https://github.com/acme/storefront');
  await page.click('#aiAssistRun');
  await page.waitForSelector('#aiAssistOut:not([hidden])');
  await page.evaluate(() => { document.getElementById('aiAssist').scrollIntoView({ block: 'start' }); window.scrollBy(0, -250); });
  await page.waitForTimeout(300);
  await shot(page, '05-new-deployment-safety-review');
  await page.unroute('**/deployments/ai-assist/');

  await open(page, `/deployments/${ids.care}/`, 'dark');
  // The demo deployment was never cloned, so a background file-tree request raises an error toast. Hide it.
  await page.evaluate(() => document.querySelectorAll('body *').forEach(e => { if (!e.children.length && /Repository not cloned yet/.test(e.textContent || '')) e.style.display = 'none'; }));
  await shot(page, '06-deployment-safety-report');
  ids = getIds();
  await open(page, '/deployments/', 'light');                        await shot(page, '07-operator-approval-light');
  await open(page, '/deployments/llm/', 'dark');                     await shot(page, '08-llm-models');
  await open(page, `/deployments/llm/${ids.llm}/`, 'dark');
  await page.locator('#api-h').scrollIntoViewIfNeeded();             await page.waitForTimeout(300); await shot(page, '09-llm-public-api');
  await open(page, '/api/llm/keys/', 'dark');                        await shot(page, '10-llm-api-keys');
  await open(page, '/databases/', 'dark');                           await shot(page, '11-databases');
  await open(page, '/databases/deploy/', 'dark');                    await shot(page, '12-deploy-a-database');
  await open(page, '/databases/', 'dark');
  const dbHref = await page.locator('tr:has-text("orders") a:has-text("View")').first().getAttribute('href');
  await open(page, dbHref, 'dark');                                  await shot(page, '13-database-detail');
  await open(page, '/api/ai/providers/', 'dark');                    await shot(page, '14-ai-providers');
  ids = getIds();
  await open(page, '/deployments/workers/', 'dark');                 await shot(page, '15-build-workers');
  await open(page, `/deployments/workers/jobs/${ids.job}/`, 'dark'); await shot(page, '16-build-job-log');
  await open(page, '/api/tokens/', 'light');                         await shot(page, '17-api-tokens-light');

  await browser.close();
  console.log('captured to', OUT);
})();
