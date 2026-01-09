const CACHE_VERSION = 'v11';
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
  // Homepage: Cache first for offline support
  else if (url.pathname === '/' || url.pathname === '/index.html') {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          console.log('[Cache] Serving homepage from cache');
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
          console.log('[Cache] Homepage not cached, offline unavailable');
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
  // API calls: Network first with cache fallback
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
});
