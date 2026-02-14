/**
 * Prime Browser Bridge — Playwright HTTP API
 *
 * Manages isolated browser sessions per session_id.
 * Listens on port 3001 (localhost only).
 *
 * Endpoints:
 *   GET  /health
 *   POST /open        { url, session_id, headless? }
 *   POST /snapshot    { session_id, full_page? }     → { image: base64PNG }
 *   POST /click       { session_id, ref }
 *   POST /type        { session_id, ref, text }
 *   POST /fill        { session_id, selector, value }
 *   POST /scroll      { session_id, direction?, amount? }
 *   POST /navigate    { session_id, url }
 *   POST /extract     { session_id, selector }       → { text }
 *   POST /close       { session_id }
 *   GET  /sessions
 */

const express = require('express');
const { chromium } = require('playwright');

const app = express();
app.use(express.json({ limit: '10mb' }));

const PORT = parseInt(process.env.BROWSER_BRIDGE_PORT || '3001', 10);

// sessions: Map<session_id, { browser, context, page, lastActive }>
const sessions = new Map();

// ── Helpers ──────────────────────────────────────────────────────────────────

async function getSession(session_id) {
  const s = sessions.get(session_id);
  if (!s) throw new Error(`Session not found: ${session_id}`);
  s.lastActive = Date.now();
  return s;
}

async function closeSession(session_id) {
  const s = sessions.get(session_id);
  if (s) {
    try { await s.browser.close(); } catch (_) {}
    sessions.delete(session_id);
  }
}

// Cleanup idle sessions every 10 minutes
setInterval(async () => {
  const maxIdleMs = 30 * 60 * 1000; // 30 minutes
  const now = Date.now();
  for (const [id, s] of sessions) {
    if (now - s.lastActive > maxIdleMs) {
      console.log(`[bridge] Closing idle session: ${id}`);
      await closeSession(id);
    }
  }
}, 10 * 60 * 1000);

// ── Routes ────────────────────────────────────────────────────────────────────

app.get('/health', (req, res) => {
  res.json({ status: 'ok', sessions: sessions.size });
});

app.get('/sessions', (req, res) => {
  const list = Array.from(sessions.entries()).map(([id, s]) => ({
    session_id: id,
    last_active: new Date(s.lastActive).toISOString(),
  }));
  res.json({ sessions: list });
});

app.post('/open', async (req, res) => {
  const { url, session_id, headless = true } = req.body;
  if (!url || !session_id) {
    return res.status(400).json({ error: 'url and session_id required' });
  }
  try {
    // Close existing session if any
    await closeSession(session_id);

    const browser = await chromium.launch({ headless });
    const context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    });
    const page = await context.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

    sessions.set(session_id, { browser, context, page, lastActive: Date.now() });
    console.log(`[bridge] Opened: ${url} (session=${session_id})`);
    res.json({ status: 'ok', session_id, url });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/snapshot', async (req, res) => {
  const { session_id, full_page = false } = req.body;
  try {
    const { page } = await getSession(session_id);
    const buf = await page.screenshot({ fullPage: full_page });
    const image = buf.toString('base64');
    res.json({ status: 'ok', image });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/click', async (req, res) => {
  const { session_id, ref } = req.body;
  try {
    const { page } = await getSession(session_id);
    await page.click(ref, { timeout: 10000 });
    res.json({ status: 'ok' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/type', async (req, res) => {
  const { session_id, ref, text } = req.body;
  try {
    const { page } = await getSession(session_id);
    await page.click(ref, { timeout: 10000 });
    await page.keyboard.type(text);
    res.json({ status: 'ok' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/fill', async (req, res) => {
  const { session_id, selector, value } = req.body;
  try {
    const { page } = await getSession(session_id);
    await page.fill(selector, value, { timeout: 10000 });
    res.json({ status: 'ok' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/scroll', async (req, res) => {
  const { session_id, direction = 'down', amount = 300 } = req.body;
  try {
    const { page } = await getSession(session_id);
    const dy = direction === 'up' ? -amount : amount;
    await page.evaluate((dy) => window.scrollBy(0, dy), dy);
    res.json({ status: 'ok' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/navigate', async (req, res) => {
  const { session_id, url } = req.body;
  try {
    const { page } = await getSession(session_id);
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    res.json({ status: 'ok', url });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/extract', async (req, res) => {
  const { session_id, selector } = req.body;
  try {
    const { page } = await getSession(session_id);
    const text = await page.textContent(selector, { timeout: 10000 });
    res.json({ status: 'ok', text: (text || '').trim() });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/close', async (req, res) => {
  const { session_id } = req.body;
  await closeSession(session_id);
  res.json({ status: 'ok', session_id });
});

// ── Start ─────────────────────────────────────────────────────────────────────

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[bridge] Playwright bridge listening on port ${PORT}`);
});

process.on('SIGTERM', async () => {
  console.log('[bridge] SIGTERM — closing all sessions');
  for (const id of sessions.keys()) {
    await closeSession(id);
  }
  process.exit(0);
});
