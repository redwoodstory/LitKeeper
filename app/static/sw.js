const CACHE_VERSION = 'v15';
const STATIC_CACHE = `litkeeper-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `litkeeper-dynamic-${CACHE_VERSION}`;

// Critical assets that MUST be cached persistently (won't be evicted)
const STATIC_ASSETS = [
  '/',
  '/static/reader/reader.css',
  '/static/reader/reader.js',
  '/static/manifest.json',
  '/static/vendor/htmx.min.js',
  '/static/vendor/alpine.min.js',
  '/static/vendor/tailwind.js',
  '/static/vendor/jszip.min.js',
  '/static/vendor/epub.min.js',
  '/static/epub/epub_reader.css',
  '/static/epub/epub_reader.js',
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
  '/static/fonts/roboto-400.ttf'
];

// OPFS helper functions
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
      console.log('[OPFS] Initialized successfully');
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
      console.log('[OPFS] Saved story:', filename);
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
    } catch (error) {
      console.log('[OPFS] Story not found:', filename);
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
      console.log('[OPFS] Deleted story:', filename);
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

  // ---- Binary helpers for EPUB files ----
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
      console.log('[OPFS] Saved epub:', filename);
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
      return new Response(buffer, {
        headers: { 'Content-Type': 'application/epub+zip' }
      });
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

// Install event - cache static assets and request persistent storage
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...');
  event.waitUntil(
    Promise.all([
      // Cache critical assets (skip homepage, will cache on first visit)
      caches.open(STATIC_CACHE).then((cache) => {
        console.log('[Service Worker] Caching static assets');
        const assetsToCache = STATIC_ASSETS.filter(asset => asset !== '/');
        return cache.addAll(assetsToCache).catch((error) => {
          console.error('[Service Worker] Failed to cache assets:', error);
        });
      }),
      // Request persistent storage to prevent eviction
      navigator.storage && navigator.storage.persist
        ? navigator.storage.persist().then((persistent) => {
          console.log('[Service Worker] Persistent storage:', persistent ? 'granted' : 'denied');
        })
        : Promise.resolve()
    ])
  );
  self.skipWaiting();
});

// Activate event - clean up old caches and initialize OPFS
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating...');
  console.log('[Service Worker] Scope:', self.registration.scope);

  event.waitUntil(
    Promise.all([
      // Clean up old caches
      caches.keys().then((cacheNames) => {
        console.log('[Service Worker] Found caches:', cacheNames);
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
              console.log('[Service Worker] Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      }),
      // Initialize OPFS
      opfsStorage.init().then(() => {
        console.log('[Service Worker] OPFS initialized');
      }).catch((error) => {
        console.log('[Service Worker] OPFS init failed (this is okay):', error);
      }),
      // Claim all clients immediately
      self.clients.claim().then(() => {
        console.log('[Service Worker] Successfully claimed all clients');
        return self.clients.matchAll();
      }).then((clients) => {
        console.log('[Service Worker] Controlling', clients.length, 'clients');
        clients.forEach((client) => {
          console.log('[Service Worker] Client URL:', client.url);
        });
      }).catch((error) => {
        console.error('[Service Worker] Failed to claim clients:', error);
      })
    ]).then(() => {
      console.log('[Service Worker] Activation complete');
    })
  );
});

// Fetch event - OPFS for HTML stories, cache for everything else
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // TEMPORARY: Bypass all caching (set to false to re-enable caching)
  const DISABLE_CACHE = true;
  if (DISABLE_CACHE) {
    event.respondWith(fetch(request));
    return;
  }

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip chrome-extension and other non-http(s) requests
  if (!url.protocol.startsWith('http')) {
    return;
  }

  // HTML Stories: Use OPFS with cache fallback
  if (url.pathname.startsWith('/read/') && url.pathname.endsWith('.html')) {
    event.respondWith(handleStoryRequest(request, url));
  }
  // Homepage: Network first (server-rendered HTML must always be fresh), cache fallback for offline
  else if (url.pathname === '/' || url.pathname === '/index.html') {
    event.respondWith(
      fetch(request).then((response) => {
        if (response && response.status === 200) {
          const responseToCache = response.clone();
          caches.open(STATIC_CACHE).then((cache) => {
            cache.put(request, responseToCache);
          });
        }
        return response;
      }).catch(() => {
        return caches.match(request).then((cachedResponse) => {
          if (cachedResponse) {
            console.log('[Cache] Serving homepage from cache (offline)');
            return cachedResponse;
          }
          return new Response('Offline - Homepage not cached', {
            status: 503,
            statusText: 'Service Unavailable',
            headers: { 'Content-Type': 'text/plain' }
          });
        });
      })
    );
  }
  // JavaScript files: Network first for instant updates
  else if (url.pathname.startsWith('/static/js/')) {
    event.respondWith(
      fetch(request).then((response) => {
        if (response && response.status === 200) {
          const responseToCache = response.clone();
          caches.open(STATIC_CACHE).then((cache) => {
            cache.put(request, responseToCache);
          });
        }
        return response;
      }).catch(() => {
        return caches.match(request).then((cachedResponse) => {
          if (cachedResponse) {
            console.log('[Cache] Serving JS from cache (offline):', url.pathname);
            return cachedResponse;
          }
          return new Response('// Offline - JS not cached', {
            status: 503,
            headers: { 'Content-Type': 'application/javascript' }
          });
        });
      })
    );
  }
  // Other static assets: Cache first (CSS, images, etc.)
  else if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          console.log('[Cache] Serving static asset:', url.pathname);
          return cachedResponse;
        }
        return fetch(request).then((response) => {
          if (response && response.status === 200) {
            const responseToCache = response.clone();
            caches.open(STATIC_CACHE).then((cache) => {
              cache.put(request, responseToCache);
            });
          }
          return response;
        }).catch(() => {
          console.log('[Cache] Static asset not available offline:', url.pathname);
          return new Response('Offline', { status: 503 });
        });
      })
    );
  }
  // EPUB binary files: OPFS-first (persistent, not evictable)
  // epub.js fetches /epub/file/<id> (the full binary) and individual
  // /epub/file/<id>/<path> resources. We store the binary in OPFS;
  // internal resources are served from the network (they're extracted
  // on-the-fly by epub.js from the cached binary, no extra requests needed
  // once the binary itself is cached at the reader level).
  else if (url.pathname.startsWith('/epub/file/') && !url.pathname.split('/epub/file/')[1].includes('/')) {
    // Top-level epub binary: OPFS-first
    event.respondWith((async () => {
      const storyId = url.pathname.split('/').pop();
      const filename = `${storyId}.epub`;
      const opfsResponse = await opfsStorage.getEpubResponse(filename);
      if (opfsResponse) {
        console.log('[OPFS] Serving epub from OPFS:', filename);
        return opfsResponse;
      }
      // Not in OPFS — fetch and store
      try {
        const response = await fetch(request);
        if (response && response.status === 200) {
          const buffer = await response.arrayBuffer();
          await opfsStorage.saveEpub(filename, buffer);
          return new Response(buffer, {
            headers: { 'Content-Type': 'application/epub+zip' }
          });
        }
        return response;
      } catch {
        return new Response('EPUB not available offline', { status: 503 });
      }
    })());
  }
  // EPUB reader pages and internal resources: SW cache-first
  else if (url.pathname.startsWith('/epub/')) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(request).then((response) => {
          if (response && response.status === 200) {
            const responseToCache = response.clone();
            caches.open(DYNAMIC_CACHE).then((cache) => {
              cache.put(request, responseToCache);
            });
          }
          return response;
        }).catch(() => {
          return new Response('EPUB not available offline', { status: 503 });
        });
      })
    );
  }
  // Sync banner: Always fetch fresh (never cache dynamic state)
  else if (url.pathname === '/sync-banner') {
    event.respondWith(
      fetch(request).catch(() => {
        return new Response('', { status: 204 });
      })
    );
  }
  // Library filter: Network first, NO CACHING (always fresh data)
  else if (url.pathname === '/library/filter') {
    event.respondWith(
      fetch(request).catch(() => {
        console.log('[Cache] Library filter offline');
        return new Response('Offline', { status: 503 });
      })
    );
  }
  // Story mutation APIs: Network only, invalidate cache on success
  else if (url.pathname.match(/\/api\/story\/(delete|toggle-auto-update)\//) || 
           url.pathname.match(/\/api\/(queue|save|format\/generate-)/) ||
           request.method !== 'GET') {
    event.respondWith(
      fetch(request).then(async (response) => {
        if (response && response.ok) {
          const cache = await caches.open(DYNAMIC_CACHE);
          const keys = await cache.keys();
          const filterKeys = keys.filter(req => req.url.includes('/library/filter'));
          await Promise.all(filterKeys.map(key => cache.delete(key)));
          console.log('[Cache] Invalidated library filter cache after mutation');
        }
        return response;
      })
    );
  }
  // Other API calls: Network first with cache fallback
  else if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const responseToCache = response.clone();
          caches.open(DYNAMIC_CACHE).then((cache) => {
            cache.put(request, responseToCache);
          });
          return response;
        })
        .catch(() => {
          console.log('[Cache] API offline, trying cache:', url.pathname);
          return caches.match(request);
        })
    );
  }
  // Everything else: Cache first with network fallback
  else {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(request).catch(() => {
          return new Response('Offline', { status: 503 });
        });
      })
    );
  }
});

// Handle story requests with OPFS
async function handleStoryRequest(request, url) {
  const filename = url.pathname.split('/').pop();

  try {
    // Try OPFS first (if supported)
    if (opfsStorage.initialized || await opfsStorage.init()) {
      const storyContent = await opfsStorage.getStory(filename);
      if (storyContent) {
        console.log('[OPFS] Serving story from OPFS:', filename);
        return new Response(storyContent, {
          headers: {
            'Content-Type': 'text/html; charset=utf-8',
            'X-Source': 'OPFS'
          }
        });
      }
    } else {
      console.log('[OPFS] Not supported, using cache only');
    }

    // Not in OPFS, try cache
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      console.log('[Cache] Serving story from cache:', filename);
      // Try to migrate to OPFS in background (if supported)
      if (opfsStorage.initialized) {
        cachedResponse.clone().text().then((content) => {
          opfsStorage.saveStory(filename, content);
        }).catch(() => {
          console.log('[OPFS] Migration failed, cache still works');
        });
      }
      return cachedResponse;
    }

    // Not cached, fetch from network
    const response = await fetch(request);
    if (response && response.status === 200) {
      const responseClone = response.clone();
      const content = await responseClone.text();

      // Try to save to OPFS (primary storage)
      if (opfsStorage.initialized) {
        await opfsStorage.saveStory(filename, content).catch((error) => {
          console.log('[OPFS] Save failed, falling back to cache:', error);
        });
      }

      // Always cache as fallback
      caches.open(DYNAMIC_CACHE).then((cache) => {
        cache.put(request, response.clone());
      });

      console.log('[Network] Fetched and saved story:', filename);
    }
    return response;
  } catch (error) {
    console.error('[Service Worker] Story fetch error:', error);
    // Last resort: try cache
    const fallback = await caches.match(request);
    if (fallback) {
      return fallback;
    }
    return new Response('Story not available offline', {
      status: 503,
      statusText: 'Service Unavailable',
      headers: { 'Content-Type': 'text/plain' }
    });
  }
}

// Message event - handle storage management commands
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
          stories: stories
        }
      });
    } catch (error) {
      event.ports[0].postMessage({ success: false, error: error.message });
    }
  }

  if (event.data && event.data.type === 'DELETE_STORY') {
    const filename = event.data.filename;
    const deleted = await opfsStorage.deleteStory(filename);
    event.ports[0].postMessage({ success: deleted });
  }

  if (event.data && event.data.type === 'CLEAR_ALL') {
    try {
      // Clear OPFS
      const stories = await opfsStorage.listStories();
      await Promise.all(stories.map(story => opfsStorage.deleteStory(story)));

      // Clear caches
      const cacheNames = await caches.keys();
      await Promise.all(cacheNames.map(cacheName => caches.delete(cacheName)));

      console.log('[Service Worker] All storage cleared');
      event.ports[0].postMessage({ success: true });
    } catch (error) {
      event.ports[0].postMessage({ success: false, error: error.message });
    }
  }

  if (event.data && event.data.type === 'SYNC_ALL_STORIES') {
    const readerUrls = event.data.reader_urls || event.data.urls || [];
    const epubUrls = event.data.epub_urls || [];
    const port = event.ports[0];
    const BATCH_SIZE = 5;
    const total = readerUrls.length + epubUrls.length;

    // Mark this sync as active so CANCEL_SYNC can stop it
    self._syncCancelled = false;

    let cached = 0;
    let skipped = 0;
    let failed = 0;

    await opfsStorage.init();

    // --- Phase 1: JSON reader pages → OPFS ---
    for (let i = 0; i < readerUrls.length; i += BATCH_SIZE) {
      if (self._syncCancelled) {
        port.postMessage({ cancelled: true, cached, skipped, failed });
        return;
      }

      const batch = readerUrls.slice(i, i + BATCH_SIZE);

      await Promise.all(batch.map(async (url) => {
        const filename = url.split('/').pop();
        try {
          if (await opfsStorage.hasStory(filename)) {
            skipped++;
            port.postMessage({ done: cached + skipped + failed, total, url, skipped: true });
            return;
          }
          const response = await fetch(url);
          if (response && response.status === 200) {
            const content = await response.text();
            await opfsStorage.saveStory(filename, content);
            cached++;
          } else {
            failed++;
          }
        } catch (err) {
          console.error('[SW Sync] Failed to cache reader:', url, err);
          failed++;
        }
        port.postMessage({ done: cached + skipped + failed, total, url, skipped: false });
      }));
    }

    // --- Phase 2: EPUB binary files → OPFS ---
    for (let i = 0; i < epubUrls.length; i += BATCH_SIZE) {
      if (self._syncCancelled) {
        port.postMessage({ cancelled: true, cached, skipped, failed });
        return;
      }

      const batch = epubUrls.slice(i, i + BATCH_SIZE);

      await Promise.all(batch.map(async (url) => {
        // Only cache /epub/file/<id> (the binary), skip the reader page
        // The reader page is a dynamic Flask template — it's light and
        // better served fresh; the binary is what matters for offline.
        if (!url.startsWith('/epub/file/')) {
          // Cache the reader page in the SW cache (it's tiny)
          try {
            const cache = await caches.open(DYNAMIC_CACHE);
            const existing = await cache.match(url);
            if (existing) {
              skipped++;
              port.postMessage({ done: cached + skipped + failed, total, url, skipped: true });
              return;
            }
            const response = await fetch(url);
            if (response && response.status === 200) {
              await cache.put(url, response);
              cached++;
            } else { failed++; }
          } catch (err) {
            console.error('[SW Sync] Failed to cache epub reader page:', url, err);
            failed++;
          }
          port.postMessage({ done: cached + skipped + failed, total, url, skipped: false });
          return;
        }

        // EPUB binary → OPFS
        const storyId = url.split('/').pop();
        const filename = `${storyId}.epub`;
        try {
          if (await opfsStorage.hasEpub(filename)) {
            skipped++;
            port.postMessage({ done: cached + skipped + failed, total, url, skipped: true });
            return;
          }
          const response = await fetch(url);
          if (response && response.status === 200) {
            const buffer = await response.arrayBuffer();
            await opfsStorage.saveEpub(filename, buffer);
            cached++;
          } else {
            failed++;
          }
        } catch (err) {
          console.error('[SW Sync] Failed to cache epub binary in OPFS:', url, err);
          failed++;
        }
        port.postMessage({ done: cached + skipped + failed, total, url, skipped: false });
      }));
    }

    port.postMessage({ complete: true, cached, skipped, failed });
  }

  if (event.data && event.data.type === 'CANCEL_SYNC') {
    self._syncCancelled = true;
  }

  if (event.data && event.data.type === 'INVALIDATE_LIBRARY_CACHE') {
    try {
      const cache = await caches.open(DYNAMIC_CACHE);
      const keys = await cache.keys();
      const filterKeys = keys.filter(req => req.url.includes('/library/filter'));
      await Promise.all(filterKeys.map(key => cache.delete(key)));
      console.log('[Service Worker] Library cache invalidated');
      event.ports[0].postMessage({ success: true });
    } catch (error) {
      event.ports[0].postMessage({ success: false, error: error.message });
    }
  }
});
