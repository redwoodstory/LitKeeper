window.syncStory = async function(filename, button, storyId = null) {
  // Second click while confirming: remove from OPFS
  if (button.dataset.offlineState === 'confirming') {
    button.innerHTML = '⏳ Removing…';
    try {
      const root = await navigator.storage.getDirectory();
      await root.removeEntry(filename);
      // Also remove EPUB from OPFS if present
      if (storyId) {
        const epubDir = await root.getDirectoryHandle('epubs').catch(() => null);
        if (epubDir) await epubDir.removeEntry(`${storyId}.epub`).catch(() => {});
      }
      delete button.dataset.offlineState;
      button.className = 'px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700/50 rounded-md border border-slate-200/60 dark:border-slate-700 transition-all duration-200 inline-flex items-center gap-1.5';
      button.innerHTML = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
      </svg> Sync for Offline`;
      if (window.offlineIndicators) window.offlineIndicators.applyOfflineBadges();
    } catch {
      button.innerHTML = '❌ Failed';
      setTimeout(() => window.offlineIndicators?.updateSyncButton(button, filename), 2000);
    }
    return;
  }

  // First click when already cached: enter confirmation state
  if (button.dataset.offlineState === 'cached') {
    button.dataset.offlineState = 'confirming';
    button.className = 'px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md border border-red-200 dark:border-red-800 transition-all duration-200 inline-flex items-center gap-1.5';
    button.innerHTML = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
    </svg> Remove? Tap again`;
    // Revert to cached state after 3s if not confirmed
    setTimeout(() => {
      if (button.dataset.offlineState === 'confirming') {
        window.offlineIndicators?.updateSyncButton(button, filename);
      }
    }, 3000);
    return;
  }

  // Normal sync: not yet cached
  if (!navigator.onLine) {
    window.showToast?.('You\'re offline — connect to sync for offline reading', 'warning');
    return;
  }

  const originalText = button.innerHTML;
  button.disabled = true;
  button.innerHTML = '⏳ Syncing…';

  try {
    const response = await fetch(`/read/${filename}`);
    if (response.ok) {
      // Fire-and-forget: pre-cache EPUB binary and reader page via SW
      if (storyId) {
        fetch(`/epub/file/${storyId}`).catch(() => {});
        fetch(`/epub/reader/${storyId}`).catch(() => {});
      }
      if (window.offlineIndicators) {
        window.offlineIndicators.updateSyncButton(button, filename);
        window.offlineIndicators.applyOfflineBadges();
      } else {
        button.innerHTML = '✅ Synced!';
        setTimeout(() => { button.innerHTML = originalText; button.disabled = false; }, 2000);
      }
    } else {
      throw new Error('Failed to fetch story');
    }
  } catch (error) {
    console.error('Sync error:', error);
    button.innerHTML = '❌ Failed';
    setTimeout(() => { button.innerHTML = originalText; button.disabled = false; }, 2000);
  }
};
