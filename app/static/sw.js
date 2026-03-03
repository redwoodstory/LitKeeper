// ─── Config ───────────────────────────────────────────────────────────────────

const CACHE_VERSION = 'v33';
const STATIC_CACHE  = `litkeeper-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `litkeeper-dynamic-${CACHE_VERSION}`;
const COVERS_CACHE  = `litkeeper-covers-${CACHE_VERSION}`;

const IS_DEV = self.location.hostname === 'localhost' || self.location.hostname === '127.0.0.1';

// ─── Static assets to precache ───────────────────────────────────────────────

const STATIC_ASSETS = [
  '/',
  '/settings',
  '/queue',
  '/auth/lock',
  '/static/reader/reader.css',
  '/static/reader/reader.js',
  '/static/js/theme.js',
  '/static/js/offline-indicators.js',
  '/static/js/library.js',
  '/static/js/metadata-modal.js',
  '/static/js/story-modal.js',
  '/static/js/sync.js',
  '/static/js/sw-status.js',
  '/static/manifest.json',
  '/static/vendor/htmx.min.js',
  '/static/vendor/alpine.min.js',
  '/static/vendor/tailwind.js',
  '/static/vendor/jszip.min.js',
  '/static/vendor/epub.min.js',
  '/static/epub/epub_reader.css',
  '/static/epub/epub_reader.js',
  // foliate-js: static imports (required for epub_reader.js module to load)
  '/static/foliate-js/view.js',
  '/static/foliate-js/epubcfi.js',
  '/static/foliate-js/progress.js',
  '/static/foliate-js/overlayer.js',
  '/static/foliate-js/text-walker.js',
  // foliate-js: dynamic imports for EPUB rendering
  '/static/foliate-js/epub.js',
  '/static/foliate-js/paginator.js',
  '/static/foliate-js/fixed-layout.js',
  '/static/foliate-js/vendor/zip.js',
  '/static/fonts/PlayfairDisplay-Regular.ttf',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon.svg',
  '/static/fonts/fonts.css',
  '/static/fonts/inter-200.ttf',
  '/static/fonts/inter-300.ttf',
  '/static/fonts/inter-400.ttf',
  '/static/fonts/lora-300.ttf',
  '/static/fonts/lora-400.ttf',
  '/static/fonts/ibmplexsans-200.ttf',
  '/static/fonts/ibmplexsans-300.ttf',
  '/static/fonts/ibmplexsans-400.ttf',
  '/static/fonts/opensans-300.ttf',
  '/static/fonts/opensans-400.ttf',
  '/static/fonts/roboto-300.ttf',
  '/static/fonts/roboto-400.ttf',
];

// ─── OPFS Storage ─────────────────────────────────────────────────────────────
// Stores story HTML, epub reader pages, and epub binaries persistently.
// OPFS is never cleared by SW version bumps — the only durable offline store.

class OPFSStorage {
  constructor() {
    this.root = null;
    this.initialized = false;
  }

  async init() {
    if (this.initialized) return true;
    try {
      this.root = await navigator.storage.getDirectory();
      this.initialized = true;
      return true;
    } catch (error) {
      console.error('[OPFS] Initialization failed:', error);
      return false;
    }
  }

  async saveStory(filename, content) {
    try {
      await this.init();
      const fileHandle = await this.root.getFileHandle(filename, { create: true });
      const writable = await fileHandle.createWritable();
      await writable.write(content);
      await writable.close();
      return true;
    } catch (error) {
      console.error('[OPFS] Save failed:', error);
      return false;
    }
  }

  async getStory(filename) {
    try {
      await this.init();
      const fileHandle = await this.root.getFileHandle(filename);
      const file = await fileHandle.getFile();
      return await file.text();
    } catch {
      return null;
    }
  }

  async hasStory(filename) {
    try {
      await this.init();
      await this.root.getFileHandle(filename);
      return true;
    } catch {
      return false;
    }
  }

  async deleteStory(filename) {
    try {
      await this.init();
      await this.root.removeEntry(filename);
      return true;
    } catch (error) {
      console.error('[OPFS] Delete failed:', error);
      return false;
    }
  }

  async listStories() {
    try {
      await this.init();
      const stories = [];
      for await (const entry of this.root.values()) {
        if (entry.kind === 'file' && entry.name.endsWith('.html')) {
          stories.push(entry.name);
        }
      }
      return stories;
    } catch (error) {
      console.error('[OPFS] List failed:', error);
      return [];
    }
  }

  async _getEpubDir() {
    await this.init();
    return this.root.getDirectoryHandle('epubs', { create: true });
  }

  async saveEpub(filename, arrayBuffer) {
    try {
      const dir = await this._getEpubDir();
      const fileHandle = await dir.getFileHandle(filename, { create: true });
      const writable = await fileHandle.createWritable();
      await writable.write(arrayBuffer);
      await writable.close();
      return true;
    } catch (error) {
      console.error('[OPFS] Epub save failed:', error);
      return false;
    }
  }

  async hasEpub(filename) {
    try {
      const dir = await this._getEpubDir();
      await dir.getFileHandle(filename);
      return true;
    } catch {
      return false;
    }
  }

  async getEpubResponse(filename) {
    try {
      const dir = await this._getEpubDir();
      const fileHandle = await dir.getFileHandle(filename);
      const file = await fileHandle.getFile();
      const buffer = await file.arrayBuffer();
      return new Response(buffer, { headers: { 'Content-Type': 'application/epub+zip' } });
    } catch {
      return null;
    }
  }

  async deleteEpub(filename) {
    try {
      const dir = await this._getEpubDir();
      await dir.removeEntry(filename);
      return true;
    } catch {
      return false;
    }
  }
}

const opfsStorage = new OPFSStorage();

// ─── Install ─────────────────────────────────────────────────────────────────

self.addEventListener('install', (event) => {
  event.waitUntil(
    Promise.all([
      caches.open(STATIC_CACHE).then(async (cache) => {
        const results = await Promise.allSettled(STATIC_ASSETS.map(a => cache.add(a)));
        const failed = results.filter(r => r.status === 'rejected');
        if (failed.length) console.warn('[SW] Pre-cache failures:', failed.length);
      }),
      navigator.storage?.persist?.().catch(() => {}),
    ])
  );
  self.skipWaiting();
});

// ─── Activate ────────────────────────────────────────────────────────────────

self.addEventListener('activate', (event) => {
  const currentCaches = new Set([STATIC_CACHE, DYNAMIC_CACHE, COVERS_CACHE]);

  event.waitUntil(
    Promise.all([
      caches.keys().then(keys =>
        Promise.all(keys.filter(k => !currentCaches.has(k)).map(k => caches.delete(k)))
      ),
      opfsStorage.init(),
      self.clients.claim().then(() => {
        // Re-warm key Flask pages that the install-time cache.add() may have missed
        // (install-time Vary: Cookie mismatches can cause 200→stored-as-opaque failures).
        if (!IS_DEV) {
          caches.open(STATIC_CACHE).then(cache => {
            ['/settings', '/auth/lock'].forEach(path => {
              fetch(path).then(res => { if (res?.status === 200) cache.put(path, res); }).catch(() => {});
            });
          });
        }
      }),
    ])
  );
});

// ─── Fetch ───────────────────────────────────────────────────────────────────
// Order is significant: first matching branch wins.
// OPFS-backed routes must come before the navigate catch-all.

self.addEventListener('fetch', (event) => {
  // Only handle same-origin requests
  if (!event.request.url.startsWith(self.location.origin)) return;

  const url = new URL(event.request.url);
  const { pathname } = url;

  // Dev bypass: pass all requests to network when online so code changes are visible immediately
  if (IS_DEV && navigator.onLine) {
    event.respondWith(fetch(event.request));
    return;
  }

  // HTML story reader pages → OPFS-first
  if (pathname.startsWith('/read/') && pathname.endsWith('.html')) {
    event.respondWith(handleStoryRequest(event.request, url));
    return;
  }

  // EPUB reader shell pages → network-first, saved to OPFS so they survive SW bumps
  if (pathname.startsWith('/epub/reader/')) {
    event.respondWith(handleEpubReaderRequest(event.request, url));
    return;
  }

  // EPUB binary files (top-level only, not internal resources) → OPFS-first
  if (pathname.startsWith('/epub/file/')) {
    const afterPrefix = pathname.split('/epub/file/')[1];
    if (afterPrefix && !afterPrefix.includes('/')) {
      event.respondWith(handleEpubBinaryRequest(event.request, url));
      return;
    }
  }

  // Cover images → cache-first with ignoreVary.
  // Flask emits Vary: Cookie on every response (before_request touches session).
  // Without ignoreVary: true, cached covers are invisible to cache.match().
  if (pathname.startsWith('/api/cover/')) {
    event.respondWith(handleCoverRequest(event.request));
    return;
  }

  // Page navigations → network-first; falls back through DYNAMIC then STATIC cache
  if (event.request.mode === 'navigate') {
    event.respondWith(handleNavigationRequest(event.request, url));
    return;
  }

  // App JS and reader scripts → network-first (picks up code changes without a hard refresh)
  if (pathname.startsWith('/static/js/') ||
      pathname.startsWith('/static/reader/') ||
      pathname.startsWith('/static/epub/')) {
    event.respondWith(networkFirst(event.request, STATIC_CACHE));
    return;
  }

  // All other static assets → cache-first
  if (pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(event.request, STATIC_CACHE));
    return;
  }

  // Endpoints that must always be fresh → let browser fetch directly (no SW interception)
  if (pathname === '/sync-banner' || pathname === '/library/filter') {
    return;
  }

  // Other API calls → network-first with cache fallback
  if (pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(event.request, DYNAMIC_CACHE));
    return;
  }
});

// ─── Caching strategies ───────────────────────────────────────────────────────

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request, { ignoreVary: true });
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response?.status === 200) {
      caches.open(cacheName).then(c => c.put(request, response.clone()));
    }
    return response;
  } catch {
    return new Response('', { status: 503 });
  }
}

async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response?.status === 200) {
      caches.open(cacheName).then(c => c.put(request, response.clone()));
    }
    return response;
  } catch {
    const cached = await caches.match(request, { ignoreVary: true });
    if (cached) return cached;
    return new Response('', { status: 503 });
  }
}

async function handleCoverRequest(request) {
  const cache = await caches.open(COVERS_CACHE);
  const cached = await cache.match(request, { ignoreVary: true });
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response?.status === 200) {
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('', { status: 503 });
  }
}

// ─── Route handler functions ──────────────────────────────────────────────────

async function handleStoryRequest(request, url) {
  const filename = decodeURIComponent(url.pathname.split('/').pop());

  let opfsInitOk = false;
  let opfsContent = null;
  try {
    opfsInitOk = opfsStorage.initialized || await opfsStorage.init();
    if (opfsInitOk) opfsContent = await opfsStorage.getStory(filename);
  } catch (e) {
    console.error('[SW] OPFS read error:', e);
  }

  if (opfsContent) {
    return new Response(opfsContent, {
      headers: { 'Content-Type': 'text/html; charset=utf-8', 'X-Source': 'OPFS' },
    });
  }

  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }

  try {
    const response = await fetch(request);
    if (response?.status === 200) {
      const content = await response.clone().text();
      if (opfsInitOk) opfsStorage.saveStory(filename, content).catch(() => {});
      caches.open(DYNAMIC_CACHE).then(c => c.put(request, response.clone()));
    }
    return response;
  } catch {
    const msg = `Story not available offline\n\nfilename: ${filename}\nopfs_init: ${opfsInitOk}\nopfs_read: ${opfsContent !== null ? 'ok' : 'null'}`;
    return new Response(msg, { status: 503 });
  }
}

async function handleEpubReaderRequest(request, url) {
  try {
    const response = await fetch(request);
    if (response?.status === 200) {
      const storyId = url.pathname.split('/').pop();
      response.clone().text()
        .then(html => opfsStorage.saveStory(`epub_reader_${storyId}.html`, html))
        .catch(() => {});
    }
    return response;
  } catch {
    const storyId = url.pathname.split('/').pop();
    const html = await opfsStorage.getStory(`epub_reader_${storyId}.html`);
    if (html) return new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
    return offlineEpubReaderResponse();
  }
}

async function handleEpubBinaryRequest(request, url) {
  const storyId = url.pathname.split('/').pop();
  const filename = `${storyId}.epub`;

  const opfsResponse = await opfsStorage.getEpubResponse(filename);
  if (opfsResponse) return opfsResponse;

  try {
    const response = await fetch(request);
    if (response?.status === 200) {
      const buffer = await response.arrayBuffer();
      await opfsStorage.saveEpub(filename, buffer);
      return new Response(buffer, { headers: { 'Content-Type': 'application/epub+zip' } });
    }
    return response;
  } catch {
    return new Response('EPUB not available offline', { status: 503 });
  }
}

async function handleNavigationRequest(request, url) {
  try {
    const response = await fetch(request);
    if (response?.status === 200) {
      caches.open(DYNAMIC_CACHE).then(c => c.put(request, response.clone()));
    }
    return response;
  } catch {
    const dynCache = await caches.open(DYNAMIC_CACHE);
    const dynMatch = await dynCache.match(request, { ignoreVary: true });
    if (dynMatch) return dynMatch;

    const staticCache = await caches.open(STATIC_CACHE);
    const staticMatch = await staticCache.match(request, { ignoreVary: true });
    if (staticMatch) return staticMatch;

    if (url.pathname === '/' || url.pathname === '/library') {
      const home = await staticCache.match('/', { ignoreVary: true });
      if (home) return home;
    }

    const isHome = url.pathname === '/' || url.pathname === '/library';
    return new Response(
      `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Offline – LitKeeper</title><style>body{font-family:sans-serif;text-align:center;padding:4rem 1rem;background:#111827;color:#f9fafb}h2{font-size:1.5rem;margin-bottom:.75rem}p{color:#9ca3af}a{color:#60a5fa;text-decoration:underline}</style></head><body><h2>You're offline</h2><p>${isHome ? 'Open LitKeeper while connected at least once to enable offline access.' : "This page isn't available offline."}</p>${isHome ? '' : '<p><a href="/">Go to Library</a></p>'}</body></html>`,
      { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    );
  }
}

function offlineEpubReaderResponse() {
  return new Response(
    '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Offline</title><style>body{font-family:sans-serif;text-align:center;padding:4rem 1rem;background:#111827;color:#f9fafb}h2{font-size:1.5rem;margin-bottom:.75rem}p{color:#9ca3af;margin:.5rem 0}a{color:#60a5fa;text-decoration:underline}</style></head><body><h2>EPUB not available offline</h2><p>Go online and run <a href="/settings">Sync All Offline</a> from Settings.</p><p><a href="/">Go to Library</a></p></body></html>',
    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
  );
}

// ─── Message handlers ────────────────────────────────────────────────────────

self.addEventListener('message', async (event) => {
  if (event.data && event.data.type === 'GET_STORAGE_INFO') {
    try {
      const estimate = await navigator.storage.estimate();
      const persistent = await navigator.storage.persisted();
      const stories = await opfsStorage.listStories();

      event.ports[0].postMessage({
        success: true,
        storage: {
          usage: estimate.usage,
          quota: estimate.quota,
          persistent: persistent,
          storiesCount: stories.length,
          stories: stories,
        },
      });
    } catch (error) {
      event.ports[0].postMessage({ success: false, error: error.message });
    }
  }

  if (event.data && event.data.type === 'TEST_OPFS_READ') {
    const filename = event.data.filename;
    const result = { filename, steps: {} };
    try {
      result.steps.navigator_storage = !!navigator.storage;
      result.steps.get_directory = false;
      const root = await navigator.storage.getDirectory();
      result.steps.get_directory = true;
      result.steps.get_file_handle = false;
      const fh = await root.getFileHandle(filename);
      result.steps.get_file_handle = true;
      result.steps.get_file = false;
      const file = await fh.getFile();
      result.steps.get_file = true;
      result.steps.read_text = false;
      const text = await file.text();
      result.steps.read_text = true;
      result.steps.size = text.length;
      result.success = true;
    } catch (e) {
      result.success = false;
      result.error = e.message;
    }
    event.ports[0].postMessage(result);
    return;
  }

  if (event.data && event.data.type === 'DELETE_STORY') {
    const deleted = await opfsStorage.deleteStory(event.data.filename);
    event.ports[0].postMessage({ success: deleted });
  }

  if (event.data && event.data.type === 'CLEAR_ALL') {
    try {
      const stories = await opfsStorage.listStories();
      await Promise.all(stories.map(s => opfsStorage.deleteStory(s)));
      const cacheNames = await caches.keys();
      await Promise.all(cacheNames.map(n => caches.delete(n)));
      event.ports[0].postMessage({ success: true });
    } catch (error) {
      event.ports[0].postMessage({ success: false, error: error.message });
    }
  }

  if (event.data && event.data.type === 'SYNC_ALL_STORIES') {
    const readerUrls = event.data.reader_urls || event.data.urls || [];
    const epubUrls   = event.data.epub_urls   || [];
    const coverUrls  = event.data.cover_urls  || [];
    const port = event.ports[0];
    const BATCH_SIZE = 5;
    const total = readerUrls.length + epubUrls.length + coverUrls.length;

    self._syncCancelled = false;

    let cached = 0, skipped = 0, failed = 0;
    const failedUrls = [];

    await opfsStorage.init();

    // Phase 1: HTML reader pages → OPFS
    for (let i = 0; i < readerUrls.length; i += BATCH_SIZE) {
      if (self._syncCancelled) { port.postMessage({ cancelled: true, cached, skipped, failed }); return; }

      await Promise.all(readerUrls.slice(i, i + BATCH_SIZE).map(async (url) => {
        const filename = url.split('/').pop();
        try {
          if (await opfsStorage.hasStory(filename)) {
            skipped++;
            port.postMessage({ done: cached + skipped + failed, total, url, skipped: true });
            return;
          }
          const response = await fetch(url);
          if (response?.status === 200) {
            const text = await response.text();
            await opfsStorage.saveStory(filename, text);
            caches.open(DYNAMIC_CACHE).then(c =>
              c.put(url, new Response(text, { headers: { 'Content-Type': 'text/html; charset=utf-8' } }))
            );
            cached++;
          } else { failed++; failedUrls.push(url); }
        } catch (err) {
          console.error('[SW Sync] Reader failed:', url, err);
          failed++; failedUrls.push(url);
        }
        port.postMessage({ done: cached + skipped + failed, total, url, skipped: false });
      }));
    }

    // Phase 2: EPUB binaries and reader shell pages → OPFS
    for (let i = 0; i < epubUrls.length; i += BATCH_SIZE) {
      if (self._syncCancelled) { port.postMessage({ cancelled: true, cached, skipped, failed }); return; }

      await Promise.all(epubUrls.slice(i, i + BATCH_SIZE).map(async (url) => {
        if (!url.startsWith('/epub/file/')) {
          // EPUB reader shell page
          const storyId = url.split('/').pop();
          const opfsKey = `epub_reader_${storyId}.html`;
          try {
            if (await opfsStorage.hasStory(opfsKey)) {
              skipped++;
              port.postMessage({ done: cached + skipped + failed, total, url, skipped: true });
              return;
            }
            const response = await fetch(url);
            if (response?.status === 200) {
              await opfsStorage.saveStory(opfsKey, await response.text());
              cached++;
            } else { failed++; failedUrls.push(url); }
          } catch (err) {
            console.error('[SW Sync] EPUB reader page failed:', url, err);
            failed++; failedUrls.push(url);
          }
          port.postMessage({ done: cached + skipped + failed, total, url, skipped: false });
          return;
        }

        // EPUB binary
        const storyId = url.split('/').pop();
        const filename = `${storyId}.epub`;
        try {
          if (await opfsStorage.hasEpub(filename)) {
            skipped++;
            port.postMessage({ done: cached + skipped + failed, total, url, skipped: true });
            return;
          }
          const response = await fetch(url);
          if (response?.status === 200) {
            await opfsStorage.saveEpub(filename, await response.arrayBuffer());
            cached++;
          } else { failed++; failedUrls.push(url); }
        } catch (err) {
          console.error('[SW Sync] EPUB binary failed:', url, err);
          failed++; failedUrls.push(url);
        }
        port.postMessage({ done: cached + skipped + failed, total, url, skipped: false });
      }));
    }

    // Phase 3: Cover images → COVERS_CACHE (ignoreVary, only cache 200 responses)
    for (let i = 0; i < coverUrls.length; i += BATCH_SIZE) {
      if (self._syncCancelled) { port.postMessage({ cancelled: true, cached, skipped, failed }); return; }

      await Promise.all(coverUrls.slice(i, i + BATCH_SIZE).map(async (url) => {
        try {
          const cache = await caches.open(COVERS_CACHE);
          const existing = await cache.match(url, { ignoreVary: true });
          if (existing) {
            skipped++;
            port.postMessage({ done: cached + skipped + failed, total, url, skipped: true });
            return;
          }
          const response = await fetch(url);
          if (response?.status === 200) {
            await cache.put(url, response);
            cached++;
          } else { failed++; failedUrls.push(url); }
        } catch (err) {
          console.error('[SW Sync] Cover failed:', url, err);
          failed++; failedUrls.push(url);
        }
        port.postMessage({ done: cached + skipped + failed, total, url, skipped: false });
      }));
    }

    port.postMessage({ complete: true, cached, skipped, failed, failedUrls });
  }

  if (event.data && event.data.type === 'CANCEL_SYNC') {
    self._syncCancelled = true;
  }

  if (event.data && event.data.type === 'INVALIDATE_LIBRARY_CACHE') {
    try {
      const cache = await caches.open(DYNAMIC_CACHE);
      const keys = await cache.keys();
      await Promise.all(keys.filter(r => r.url.includes('/library/filter')).map(k => cache.delete(k)));
      event.ports[0].postMessage({ success: true });
    } catch (error) {
      event.ports[0].postMessage({ success: false, error: error.message });
    }
  }
});
