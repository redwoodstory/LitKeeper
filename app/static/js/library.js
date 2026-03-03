const metadataModal = new MetadataModal();

function initializeLibraryFilters() {
  const sortBy = document.getElementById('sortBy');
  const categoryFilter = document.getElementById('categoryFilter');
  const sortOrderToggle = document.getElementById('sortOrderToggle');

  const savedSortBy = localStorage.getItem('library_sort_by') || 'date';
  const savedCategory = localStorage.getItem('library_category') || 'all';
  const savedSortOrder = localStorage.getItem('library_sort_order') || 'desc';

  if (sortBy) {
    sortBy.value = savedSortBy;
  }
  if (categoryFilter) {
    categoryFilter.value = savedCategory;
  }
  if (sortOrderToggle) {
    sortOrderToggle.value = savedSortOrder;
    updateSortOrderIcon(sortOrderToggle, savedSortOrder);
  }

  const hasSavedPreferences = localStorage.getItem('library_sort_by') || 
                               localStorage.getItem('library_category') || 
                               localStorage.getItem('library_sort_order');
  
  if (hasSavedPreferences) {
    document.body.addEventListener('htmx:afterSwap', function onSwap(e) {
      if (e.detail.target.id === 'library-content') {
        e.detail.target.style.visibility = '';
        document.body.removeEventListener('htmx:afterSwap', onSwap);
      }
    });
    triggerLibraryFilter();
  }
}

function updateSortOrderIcon(button, order) {
  const svg = button.querySelector('svg path');
  if (order === 'asc') {
    svg.setAttribute('d', 'M5 15l7-7 7 7');
    button.setAttribute('title', 'Ascending order');
  } else {
    svg.setAttribute('d', 'M19 9l-7 7-7-7');
    button.setAttribute('title', 'Descending order');
  }
}

function triggerLibraryFilter() {
  const sortBy = document.getElementById('sortBy');
  if (sortBy) {
    htmx.trigger(sortBy, 'change');
  }
}

const sortOrderToggle = document.getElementById('sortOrderToggle');
if (sortOrderToggle) {
  let pendingOrder = null;
  
  sortOrderToggle.addEventListener('click', function(e) {
    const currentOrder = this.value;
    const newOrder = currentOrder === 'desc' ? 'asc' : 'desc';
    pendingOrder = newOrder;
    this.value = newOrder;
    localStorage.setItem('library_sort_order', newOrder);
    updateSortOrderIcon(this, newOrder);
  });
  
  sortOrderToggle.addEventListener('htmx:configRequest', function(e) {
    if (pendingOrder) {
      e.detail.parameters.sort_order = pendingOrder;
      pendingOrder = null;
    }
  });
}

const sortBy = document.getElementById('sortBy');
if (sortBy) {
  sortBy.addEventListener('change', function() {
    localStorage.setItem('library_sort_by', this.value);
  });
}

const categoryFilter = document.getElementById('categoryFilter');
if (categoryFilter) {
  categoryFilter.addEventListener('change', function() {
    localStorage.setItem('library_category', this.value);
  });
}

async function initOfflineMode() {
  const cached = window.offlineIndicators?.getOfflineCachedSet
    ? await window.offlineIndicators.getOfflineCachedSet()
    : new Set();

  document.getElementById('downloadCard')?.classList.add('hidden');
  document.getElementById('libraryFilters')?.classList.add('hidden');
  document.querySelectorAll('[data-offline-hide]').forEach(el => el.classList.add('hidden'));

  const allCards = document.querySelectorAll('[data-story-filename]');
  let visible = 0;
  allCards.forEach(card => {
    const show = cached.has(card.dataset.storyFilename);
    card.classList.toggle('hidden', !show);
    if (show) visible++;
  });

  const countEl = document.getElementById('libraryCount');
  if (countEl) {
    countEl.textContent = visible === 0
      ? 'No stories saved offline'
      : visible === 1 ? '1 story saved offline'
      : `${visible} stories saved offline`;
  }

  if (visible === 0) {
    const content = document.getElementById('library-content');
    if (content) {
      content.innerHTML = `<div class="text-center text-gray-500 dark:text-gray-400 py-12">
        <svg class="w-20 h-20 mx-auto mb-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M18.364 5.636a9 9 0 010 12.728M15.536 8.464a5 5 0 010 7.072M6.343 6.343a9 9 0 000 12.728M9.172 9.172a5 5 0 000 7.07M12 12h.01"></path>
        </svg>
        <p class="text-lg font-medium">No stories saved offline</p>
        <p class="text-sm mt-1">Connect to the internet and sync stories for offline reading</p>
      </div>`;
    }
  }
}

// Intercepts story card clicks while offline — navigates directly to reader, bypassing the HTMX modal
document.addEventListener('click', async (e) => {
  if (navigator.onLine) return;
  const card = e.target.closest('[data-story-filename]');
  if (!card) return;
  e.stopPropagation();

  const htmlFile = card.dataset.storyFilename;
  const epubStoryId = card.dataset.epubStoryId;

  const [epubSet, htmlSet] = await Promise.all([
    epubStoryId ? (window.offlineIndicators?.getOfflineEpubSet?.() ?? Promise.resolve(new Set())) : Promise.resolve(new Set()),
    window.offlineIndicators?.getOfflineCachedSet?.() ?? Promise.resolve(new Set()),
  ]);

  const epubAvailable = epubStoryId && epubSet.has(String(epubStoryId));
  const htmlAvailable = htmlSet.has(htmlFile);

  if (epubAvailable && htmlAvailable) {
    showOfflineFormatPicker(htmlFile, epubStoryId);
  } else if (epubAvailable) {
    window.location.href = `/epub/reader/${epubStoryId}`;
  } else if (htmlAvailable) {
    window.location.href = `/read/${htmlFile}`;
  } else {
    window.offlineIndicators?.showToast('This story isn\'t available offline — sync it while connected.', 'warning');
  }
}, true);

function showOfflineFormatPicker(htmlFile, epubStoryId) {
  const existing = document.getElementById('offline-format-picker');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.id = 'offline-format-picker';
  overlay.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm';
  overlay.innerHTML = `
    <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 mx-4 w-full max-w-xs">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-white text-center mb-1">Read Story</h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 text-center mb-5">Choose a format</p>
      <div class="flex flex-col gap-3">
        <a href="/read/${htmlFile}"
           class="flex items-center justify-center gap-2 px-4 py-3 bg-slate-900 dark:bg-white text-white dark:text-slate-900 rounded-xl font-medium text-sm hover:bg-slate-800 dark:hover:bg-slate-100 transition-all duration-200">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
          </svg>
          Read as HTML
        </a>
        <a href="/epub/reader/${epubStoryId}"
           class="flex items-center justify-center gap-2 px-4 py-3 bg-white dark:bg-gray-700 text-slate-900 dark:text-white border border-slate-200 dark:border-gray-600 rounded-xl font-medium text-sm hover:bg-slate-50 dark:hover:bg-gray-600 transition-all duration-200">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
          </svg>
          Read as EPUB
        </a>
        <button onclick="document.getElementById('offline-format-picker').remove()"
                class="px-4 py-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-200">
          Cancel
        </button>
      </div>
    </div>`;

  overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
  document.body.appendChild(overlay);
}

document.addEventListener('DOMContentLoaded', () => {
  if (navigator.onLine) {
    initializeLibraryFilters();
  } else {
    initOfflineMode();
  }
});

window.addEventListener('offline', initOfflineMode);

window.addEventListener('online', () => {
  delete document.documentElement.dataset.offline;
  document.getElementById('downloadCard')?.classList.remove('hidden');
  document.getElementById('libraryFilters')?.classList.remove('hidden');
  document.querySelectorAll('[data-offline-hide]').forEach(el => el.classList.remove('hidden'));
  document.querySelectorAll('[data-story-filename]').forEach(card => card.classList.remove('hidden'));
  initializeLibraryFilters();
});
