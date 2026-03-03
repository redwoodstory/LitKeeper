// Reads OPFS directly from the page context (no SW message round-trip needed).
// Applies offline badge overlays to story cards and manages sync button state.

async function getOfflineCachedSet() {
  if (!navigator.storage?.getDirectory) return new Set();
  try {
    const root = await navigator.storage.getDirectory();
    const cached = new Set();
    for await (const entry of root.values()) {
      if (entry.kind === 'file' && entry.name.endsWith('.html')) {
        cached.add(entry.name);
      }
    }
    return cached;
  } catch {
    return new Set();
  }
}

// Returns a Set of story IDs (as strings) whose EPUB is saved in OPFS under epubs/.
async function getOfflineEpubSet() {
  if (!navigator.storage?.getDirectory) return new Set();
  try {
    const root = await navigator.storage.getDirectory();
    const epubDir = await root.getDirectoryHandle('epubs').catch(() => null);
    if (!epubDir) return new Set();
    const cached = new Set();
    for await (const entry of epubDir.values()) {
      if (entry.kind === 'file' && entry.name.endsWith('.epub')) {
        cached.add(entry.name.slice(0, -5)); // strip .epub → story ID string
      }
    }
    return cached;
  } catch {
    return new Set();
  }
}

async function applyOfflineBadges() {
  const cached = await getOfflineCachedSet();
  document.querySelectorAll('[data-story-filename]').forEach(card => {
    const badge = card.querySelector('.offline-badge');
    if (badge) badge.classList.toggle('hidden', !cached.has(card.dataset.storyFilename));
  });
}

// Sets a sync button into the "Saved Offline" state (green, clickable for removal).
async function updateSyncButton(btn, filename) {
  if (!btn || !filename) return;
  let isCached = false;
  try {
    const root = await navigator.storage.getDirectory();
    await root.getFileHandle(filename);
    isCached = true;
  } catch { /* not cached */ }

  if (isCached) {
    btn.dataset.offlineState = 'cached';
    btn.disabled = false;
    btn.innerHTML = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
    </svg> Saved Offline`;
    btn.className = 'px-3 py-1.5 text-xs font-medium text-green-600 dark:text-green-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md border border-green-300 dark:border-green-700 hover:border-red-200 dark:hover:border-red-800 transition-all duration-200 inline-flex items-center gap-1.5';
    btn.title = 'Tap to remove offline copy';
  } else {
    delete btn.dataset.offlineState;
    btn.disabled = false;
    btn.innerHTML = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
    </svg> Sync for Offline`;
    btn.className = 'px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700/50 rounded-md border border-slate-200/60 dark:border-slate-700 transition-all duration-200 inline-flex items-center gap-1.5';
    btn.title = 'Cache for offline reading';
  }
}

// Removes all HTML stories and EPUB files from OPFS.
async function clearAllOffline() {
  if (!navigator.storage?.getDirectory) return { cleared: 0 };
  try {
    const root = await navigator.storage.getDirectory();
    let cleared = 0;
    for await (const entry of root.values()) {
      if (entry.kind === 'file') {
        await root.removeEntry(entry.name);
        cleared++;
      } else if (entry.kind === 'directory' && entry.name === 'epubs') {
        const epubDir = await root.getDirectoryHandle('epubs');
        for await (const epub of epubDir.values()) {
          await epubDir.removeEntry(epub.name);
          cleared++;
        }
      }
    }
    return { cleared };
  } catch (e) {
    return { cleared: 0, error: e.message };
  }
}

// Shows a temporary toast notification. type: 'info' | 'success' | 'error' | 'warning'
function showToast(message, type = 'info') {
  const existing = document.getElementById('lk-toast');
  if (existing) existing.remove();

  const colors = {
    info: 'bg-blue-500',
    success: 'bg-green-500',
    error: 'bg-red-500',
    warning: 'bg-amber-500',
  };

  const toast = document.createElement('div');
  toast.id = 'lk-toast';
  toast.className = `fixed bottom-4 right-4 ${colors[type] ?? colors.info} text-white text-sm font-medium px-4 py-2.5 rounded-lg shadow-lg z-[100] flex items-center gap-2 transition-opacity duration-300`;
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// Disables [data-requires-online] elements when offline, re-enables when online.
// Buttons/inputs/selects get the disabled attribute; links get pointer-events-none + opacity.
function applyOnlineRequirements() {
  const offline = !navigator.onLine;
  document.querySelectorAll('[data-requires-online]').forEach(el => {
    if (el.tagName === 'BUTTON' || el.tagName === 'INPUT' || el.tagName === 'SELECT') {
      el.disabled = offline;
    } else if (el.tagName === 'A') {
      el.classList.toggle('opacity-50', offline);
      el.classList.toggle('pointer-events-none', offline);
      el.classList.toggle('cursor-not-allowed', offline);
    }
    el.title = offline ? 'Not available offline' : (el.dataset.originalTitle || '');
  });
}

// Run on initial page load
document.addEventListener('DOMContentLoaded', () => {
  applyOfflineBadges();
  applyOnlineRequirements();
});

window.addEventListener('online', applyOnlineRequirements);
window.addEventListener('offline', applyOnlineRequirements);

// Re-apply badges and update modal sync button after any HTMX swap
document.addEventListener('htmx:afterSettle', (e) => {
  applyOfflineBadges();
  applyOnlineRequirements();
  const syncBtn = e.detail.elt?.querySelector?.('[data-sync-filename]');
  if (syncBtn) updateSyncButton(syncBtn, syncBtn.dataset.syncFilename);
});

// Show a toast when any HTMX request fails because we're offline
document.addEventListener('htmx:sendError', () => {
  if (!navigator.onLine) showToast('You\'re offline — this action requires a connection', 'warning');
});

window.offlineIndicators = { applyOfflineBadges, updateSyncButton, clearAllOffline, showToast, getOfflineCachedSet, getOfflineEpubSet };
window.showToast = showToast;
