import '../foliate-js/view.js';

const storyId = window.STORY_ID;
const epubUrl = window.EPUB_URL;
let view;
let currentFraction = 0;
let headerVisible = true;
let headerTimeout = null;

const html = document.documentElement;
const themeToggle = document.getElementById('themeToggle');
const settingsToggle = document.getElementById('settingsToggle');
const settingsPanel = document.getElementById('settingsPanel');
const tocToggle = document.getElementById('tocToggle');
const tocPanel = document.getElementById('tocPanel');
const prevBtn = document.getElementById('prev');
const nextBtn = document.getElementById('next');
const progressFill = document.getElementById('progressFill');
const locationInfo = document.getElementById('locationInfo');
const readerHeader = document.querySelector('.reader-header');
const readerFooter = document.querySelector('.reader-footer');

function toggleHeader() {
  const isMobile = window.innerWidth <= 768;
  if (!isMobile) return;
  
  headerVisible = !headerVisible;
  
  if (headerVisible) {
    readerHeader.style.transform = 'translateY(0)';
    
    if (headerTimeout) clearTimeout(headerTimeout);
    headerTimeout = setTimeout(() => {
      if (headerVisible) toggleHeader();
    }, 3000);
  } else {
    readerHeader.style.transform = 'translateY(-100%)';
    if (headerTimeout) clearTimeout(headerTimeout);
  }
}

function showHeaderTemporarily() {
  const isMobile = window.innerWidth <= 768;
  if (!isMobile) return;
  
  if (!headerVisible) {
    headerVisible = true;
    readerHeader.style.transform = 'translateY(0)';
  }
  
  if (headerTimeout) clearTimeout(headerTimeout);
  headerTimeout = setTimeout(() => {
    if (headerVisible) toggleHeader();
  }, 3000);
}

let savedThemePreference = 'system';

async function fetchThemePreference() {
  try {
    const response = await fetch('/settings/theme-preference');
    const data = await response.json();
    if (data.success) {
      savedThemePreference = data.theme;
      return data.theme;
    }
  } catch (error) {
    console.error('Error fetching theme preference:', error);
  }
  return 'system';
}

function getSystemTheme() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function setTheme(theme) {
  html.setAttribute('data-theme', theme);
  const sunIcon = themeToggle.querySelector('.sun-icon');
  const moonIcon = themeToggle.querySelector('.moon-icon');
  if (theme === 'dark') {
    sunIcon.style.display = 'block';
    moonIcon.style.display = 'none';
  } else {
    sunIcon.style.display = 'none';
    moonIcon.style.display = 'block';
  }
  
  if (view?.renderer) {
    updateReaderStyles();
  }
}

function applyThemePreference(preference) {
  if (preference === 'system') {
    setTheme(getSystemTheme());
  } else {
    setTheme(preference);
  }
  savedThemePreference = preference;
}

async function initTheme() {
  const preference = await fetchThemePreference();
  applyThemePreference(preference);
}

async function toggleTheme() {
  let newPreference;
  if (savedThemePreference === 'system') {
    const currentTheme = html.getAttribute('data-theme');
    newPreference = currentTheme === 'dark' ? 'light' : 'dark';
  } else if (savedThemePreference === 'dark') {
    newPreference = 'light';
  } else {
    newPreference = 'dark';
  }

  try {
    const response = await fetch('/settings/theme-preference', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme: newPreference })
    });
    if (response.ok) {
      applyThemePreference(newPreference);
    }
  } catch (error) {
    console.error('Error saving theme preference:', error);
  }
}

initTheme();
themeToggle.addEventListener('click', toggleTheme);

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
  if (savedThemePreference === 'system') {
    setTheme(e.matches ? 'dark' : 'light');
  }
});

window.addEventListener('pageshow', async (event) => {
  if (event.persisted || performance.getEntriesByType('navigation')[0]?.type === 'back_forward') {
    const preference = await fetchThemePreference();
    applyThemePreference(preference);
  }
});

settingsToggle.addEventListener('click', (e) => {
  e.stopPropagation();
  settingsPanel.classList.toggle('active');
  tocPanel.classList.remove('active');
});

tocToggle.addEventListener('click', (e) => {
  e.stopPropagation();
  tocPanel.classList.toggle('active');
  settingsPanel.classList.remove('active');
});

document.querySelectorAll('.close-panel').forEach(btn => {
  btn.addEventListener('click', () => {
    tocPanel.classList.remove('active');
  });
});

document.addEventListener('click', (e) => {
  if (!settingsPanel.contains(e.target) && !settingsToggle.contains(e.target)) {
    settingsPanel.classList.remove('active');
  }
});

const fontSelect = document.getElementById('fontSelect');
const fontSizeRange = document.getElementById('fontSizeRange');
const fontSizeValue = document.getElementById('fontSizeValue');
const lineHeightRange = document.getElementById('lineHeightRange');
const lineHeightValue = document.getElementById('lineHeightValue');
const widthRange = document.getElementById('widthRange');
const widthValue = document.getElementById('widthValue');

const savedFont = localStorage.getItem('fontFamily') || "ProximaNovaMedium, system-ui, -apple-system, 'Segoe UI', Roboto, Ubuntu, Cantarell, 'Noto Sans', Helvetica, Arial, sans-serif";
const savedFontSize = localStorage.getItem('epubFontSize') || '18';
const savedLineHeight = localStorage.getItem('epubLineHeight') || '1.6';

fontSelect.value = savedFont;
fontSizeRange.value = savedFontSize;
fontSizeValue.textContent = savedFontSize + 'px';
lineHeightRange.value = savedLineHeight;
lineHeightValue.textContent = savedLineHeight;

function updateReaderStyles() {
  if (!view?.renderer) return;

  const theme = html.getAttribute('data-theme');
  const isDark = theme === 'dark';
  const fontSize = fontSizeRange.value;
  const lineHeight = lineHeightRange.value;
  const fontFamily = fontSelect.value;
  const margin = parseInt(marginRange.value) || 0;

  const styles = `
    @namespace epub "http://www.idpf.org/2007/ops";
    html {
      color-scheme: ${isDark ? 'dark' : 'light'};
    }
    body {
      color: ${isDark ? '#e5e7eb' : '#1a1a1a'} !important;
      background: ${isDark ? '#0f1419' : '#ffffff'} !important;
      font-family: ${fontFamily} !important;
      font-size: ${fontSize}px !important;
      line-height: ${lineHeight} !important;
      padding-left: ${margin}px !important;
      padding-right: ${margin}px !important;
    }
    p, li, blockquote, dd, h1, h2, h3, h4, h5, h6 {
      line-height: ${lineHeight} !important;
      font-family: ${fontFamily} !important;
    }
    div, span {
      font-family: ${fontFamily} !important;
    }
  `;
  view.renderer.setStyles?.(styles);
}

fontSelect.addEventListener('change', (e) => {
  const font = e.target.value;
  localStorage.setItem('fontFamily', font);
  updateReaderStyles();
});

fontSizeRange.addEventListener('input', (e) => {
  const size = e.target.value;
  fontSizeValue.textContent = size + 'px';
  localStorage.setItem('epubFontSize', size);
  updateReaderStyles();
});

lineHeightRange.addEventListener('input', (e) => {
  const height = e.target.value;
  lineHeightValue.textContent = height;
  localStorage.setItem('epubLineHeight', height);
  updateReaderStyles();
});

const savedWidth = localStorage.getItem('epubReadingWidth') || '800';
widthRange.value = savedWidth;
widthValue.textContent = savedWidth + 'px';

if (window.innerWidth <= 768) {
  document.documentElement.style.setProperty('--max-width', '100%');
} else {
  document.documentElement.style.setProperty('--max-width', savedWidth + 'px');
}

widthRange.addEventListener('input', (e) => {
  const width = e.target.value;
  widthValue.textContent = width + 'px';
  localStorage.setItem('epubReadingWidth', width);

  if (window.innerWidth > 768) {
    document.documentElement.style.setProperty('--max-width', width + 'px');
    if (view?.renderer) {
      view.renderer.setAttribute('max-inline-size', width);
    }
  }
});

const marginRange = document.getElementById('marginRange');
const marginValue = document.getElementById('marginValue');
const savedMargin = localStorage.getItem('epubMobileMargin') || '16';
marginRange.value = savedMargin;
marginValue.textContent = savedMargin + 'px';

function applyMobileVisibility() {
  const isMobile = window.innerWidth <= 768;
  document.querySelectorAll('.desktop-only-setting').forEach(el => {
    el.style.display = isMobile ? 'none' : '';
  });
  document.querySelectorAll('.mobile-only-setting').forEach(el => {
    el.style.display = isMobile ? '' : 'none';
  });
}
applyMobileVisibility();
window.addEventListener('resize', applyMobileVisibility);

marginRange.addEventListener('input', (e) => {
  const margin = e.target.value;
  marginValue.textContent = margin + 'px';
  localStorage.setItem('epubMobileMargin', margin);
  updateReaderStyles();
});

class ProgressDB {
  constructor() {
    this.dbName = 'LitKeeperProgress';
    this.version = 1;
    this.storeName = 'reading_progress';
    this.db = null;
  }

  async init() {
    if (this.db) return this.db;

    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.version);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve(this.db);
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(this.storeName)) {
          db.createObjectStore(this.storeName, { keyPath: 'story_id' });
        }
      };
    });
  }

  async saveProgress(storyId, progressData) {
    const db = await this.init();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([this.storeName], 'readwrite');
      const store = transaction.objectStore(this.storeName);
      const data = { story_id: storyId, ...progressData };
      const request = store.put(data);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  async getProgress(storyId) {
    const db = await this.init();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([this.storeName], 'readonly');
      const store = transaction.objectStore(this.storeName);
      const request = store.get(storyId);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async markSynced(storyId, synced) {
    const progress = await this.getProgress(storyId);
    if (progress) {
      progress.synced = synced;
      await this.saveProgress(storyId, progress);
    }
  }
}

const progressDB = new ProgressDB();

async function syncProgressToServer() {
  try {
    const localProgress = await progressDB.getProgress(storyId);

    if (!localProgress || localProgress.synced) {
      return;
    }

    const response = await fetch(`/epub/api/progress/${storyId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        current_chapter: localProgress.current_chapter,
        scroll_position: localProgress.scroll_position,
        cfi: localProgress.cfi,
        percentage: localProgress.percentage
      })
    });

    if (response.ok) {
      await progressDB.markSynced(storyId, true);
      console.log('[Sync] Progress synced to server');
    }
  } catch (error) {
    console.log('[Sync] Failed to sync progress, will retry later');
  }
}

async function saveProgress(fraction, cfi) {
  const progressData = {
    current_chapter: 0,
    scroll_position: 0,
    cfi: cfi || '',
    percentage: fraction,
    timestamp: new Date().toISOString(),
    synced: false
  };

  console.log('[Progress] Saving position:', {
    fraction: fraction,
    cfi: cfi,
    percentage: fraction
  });

  await progressDB.saveProgress(storyId, progressData);

  try {
    const response = await fetch(`/epub/api/progress/${storyId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        current_chapter: 0,
        scroll_position: 0,
        cfi: cfi || '',
        percentage: fraction
      })
    });

    if (response.ok) {
      await progressDB.markSynced(storyId, true);
    }
  } catch (error) {
    console.log('[Offline] Progress saved to IndexedDB, will sync when online');
  }
}

async function initializeReader() {
  console.log('[Foliate] Starting initialization...');
  console.log('[Foliate] EPUB URL:', epubUrl);

  let isInitialLoad = true;
  let hasSavedProgress = false;

  showHeaderTemporarily();

  try {
    const response = await fetch(epubUrl);
    if (!response.ok) {
      throw new Error('Failed to fetch EPUB file: ' + response.status);
    }
    const blob = await response.blob();
    console.log('[Foliate] EPUB loaded, size:', blob.size, 'bytes');

    const file = new File([blob], 'book.epub', { type: 'application/epub+zip' });
    console.log('[Foliate] File object created, size:', file.size);

    view = document.createElement('foliate-view');
    const viewerContainer = document.getElementById('viewer');
    viewerContainer.appendChild(view);
    console.log('[Foliate] View element created');

    const isMobile = window.innerWidth <= 768;
    console.log('[Foliate] Is mobile:', isMobile, 'viewport:', window.innerWidth, 'x', window.innerHeight);
    console.log('[Foliate] Opening file...');
    
    try {
      if (isMobile) {
        const timeout = new Promise((_, reject) => 
          setTimeout(() => reject(new Error('EPUB open timeout (30s) - file may be too large for mobile')), 30000)
        );
        await Promise.race([view.open(file), timeout]);
      } else {
        await view.open(file);
      }
      console.log('[Foliate] Book opened successfully');
    } catch (openError) {
      console.error('[Foliate] ERROR opening book:', openError.message);
      console.error('[Foliate] File size:', file.size, 'bytes');
      console.error('[Foliate] Is mobile:', isMobile);
      throw new Error('Failed to open EPUB: ' + openError.message);
    }
    
    console.log('[Foliate] Setting renderer attributes...');
    view.renderer.setAttribute('flow', 'paginated');
    view.renderer.setAttribute('animated', '');
    view.renderer.setAttribute('margin', '0');
    view.renderer.setAttribute('gap', '0');
    
    if (isMobile) {
      view.renderer.setAttribute('max-inline-size', '100%');
      view.renderer.setAttribute('max-block-size', '100%');
      console.log('[Foliate] Mobile renderer configured');
    } else {
      view.renderer.setAttribute('max-inline-size', savedWidth);
    }
    console.log('[Foliate] Renderer attributes set');

    console.log('[Foliate] Updating styles...');
    updateReaderStyles();
    console.log('[Foliate] Styles updated');
    
    setTimeout(() => {
      const dims = 'view:' + view.offsetWidth + 'x' + view.offsetHeight + 
                   ' container:' + viewerContainer.offsetWidth + 'x' + viewerContainer.offsetHeight;
      console.log('[Foliate] Dimensions:', dims);
      
      if (view.offsetHeight === 0 || view.offsetWidth === 0) {
        console.error('[Foliate] View has zero dimensions! Forcing reflow...');
        view.style.display = 'none';
        void view.offsetHeight;
        view.style.display = 'block';
      }
    }, 200);

    view.addEventListener('load', (e) => {
      console.log('[Foliate] Content loaded event fired');
      const { doc } = e.detail;
      console.log('[Foliate] Document:', doc ? 'exists' : 'null');
      
      doc.addEventListener('click', (clickEvent) => {
        const selection = doc.getSelection();
        if (selection && selection.toString().length > 0) return;
        
        const iframe = clickEvent.view.frameElement;
        if (!iframe) return;
        
        const iframeRect = iframe.getBoundingClientRect();
        const clickX = clickEvent.clientX - clickEvent.view.scrollX + iframeRect.left;
        const clickY = clickEvent.clientY + iframeRect.top;
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const leftZone = viewportWidth * 0.25;
        const rightZone = viewportWidth * 0.75;
        const topZone = viewportHeight * 0.2;
        
        console.log('[Tap] Click at', clickX, clickY, 'viewport:', viewportWidth, 'x', viewportHeight, 'zones:', { leftZone, rightZone, topZone });
        
        if (clickY < topZone || (clickX >= leftZone && clickX <= rightZone)) {
          console.log('[Tap] Toggle header');
          toggleHeader();
        } else if (clickX < leftZone) {
          console.log('[Tap] Going left');
          view.goLeft();
        } else if (clickX > rightZone) {
          console.log('[Tap] Going right');
          view.goRight();
        }
      });
    });

    view.addEventListener('relocate', async (e) => {
      const { fraction, location, tocItem, cfi } = e.detail;
      currentFraction = fraction;
      
      progressFill.style.width = (fraction * 100) + '%';
      locationInfo.textContent = `${Math.round(fraction * 100)}%`;
      
      console.log('[Progress] Relocated:', {
        fraction: fraction,
        location: location,
        cfi: cfi,
        isInitialLoad: isInitialLoad
      });

      if (isInitialLoad) {
        console.log('[Progress] Skipping save on initial load');
        isInitialLoad = false;
        return;
      }

      await saveProgress(fraction, cfi);
    });

    const { book } = view;
    const toc = book.toc;
    if (toc) {
      const tocContent = document.getElementById('tocContent');
      tocContent.innerHTML = '';
      
      function renderTocItems(items) {
        items.forEach(item => {
          const div = document.createElement('div');
          div.className = 'toc-item';
          div.textContent = item.label;
          div.addEventListener('click', async () => {
            try {
              await view.goTo(item.href);
              tocPanel.classList.remove('active');
            } catch (e) {
              console.error('Failed to navigate to TOC item:', e);
            }
          });
          tocContent.appendChild(div);
          
          if (item.subitems && item.subitems.length > 0) {
            renderTocItems(item.subitems);
          }
        });
      }
      
      renderTocItems(toc);
    }

    const localProgress = await progressDB.getProgress(storyId);
    let progressToUse = window.INITIAL_PROGRESS;

    if (localProgress) {
      const localTime = new Date(localProgress.timestamp || 0).getTime();
      const serverTime = progressToUse?.last_read_at ? new Date(progressToUse.last_read_at).getTime() : 0;

      if (localTime > serverTime) {
        console.log('[IndexedDB] Using local progress (newer than server)');
        progressToUse = localProgress;
      }
    }

    let lastLocation = null;
    if (progressToUse && progressToUse.cfi) {
      hasSavedProgress = true;
      console.log('[Progress] Restoring from CFI:', progressToUse.cfi);
      lastLocation = progressToUse.cfi;
    } else if (progressToUse && progressToUse.percentage !== null && progressToUse.percentage !== undefined) {
      hasSavedProgress = true;
      console.log('[Progress] Restoring from percentage:', progressToUse.percentage);
      lastLocation = { fraction: progressToUse.percentage };
    } else {
      console.log('[Progress] No saved position, starting from beginning');
    }

    console.log('[Foliate] Initializing view with lastLocation:', lastLocation);
    await view.init({ lastLocation });
    setTimeout(() => { isInitialLoad = false; }, 500);

    prevBtn.addEventListener('click', () => view.goLeft());
    nextBtn.addEventListener('click', () => view.goRight());

    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') {
        view.goLeft();
      } else if (e.key === 'ArrowRight') {
        view.goRight();
      }
    });


    syncProgressToServer();

    window.addEventListener('online', () => {
      console.log('[Sync] Connection restored, syncing progress...');
      syncProgressToServer();
    });

  } catch (error) {
    console.error('[Foliate] Error loading EPUB:', error);
    console.error('[Foliate] Error details:', {
      name: error.name,
      message: error.message,
      stack: error.stack,
      cause: error.cause
    });
    
    let errorTitle = 'Failed to Load EPUB';
    let errorMessage = error.message;
    let additionalInfo = 'Check the browser console for more details.';
    
    if (error.message.includes('corrupted or malformed')) {
      errorTitle = 'EPUB File is Corrupted or Malformed';
      errorMessage = 'The EPUB file appears to be damaged or incomplete. It may need to be re-downloaded or regenerated.';
      additionalInfo = 'File size: ' + blob.size + ' bytes. This file may be too small or have structural issues.';
    } else if (error.message.includes('timeout')) {
      errorTitle = 'EPUB Loading Timeout';
      errorMessage = 'The EPUB file took too long to load. It may be too large for this device.';
      additionalInfo = 'Try using a desktop browser or a smaller file.';
    }
    
    document.getElementById('viewer').innerHTML = `
      <div style="padding: 2rem; text-align: center; color: var(--text-color);">
        <h2 style="color: #ef4444; margin-bottom: 1rem;">${errorTitle}</h2>
        <p style="margin-bottom: 1rem;">${errorMessage}</p>
        <p style="font-size: 0.875rem; color: var(--secondary-text);">${additionalInfo}</p>
        <button onclick="window.location.reload()" style="margin-top: 1rem; padding: 0.5rem 1rem; background: var(--accent-color); color: white; border: none; border-radius: 6px; cursor: pointer;">Retry</button>
        <button onclick="window.history.back()" style="margin-top: 1rem; margin-left: 0.5rem; padding: 0.5rem 1rem; background: var(--secondary-bg); color: var(--text-color); border: 1px solid var(--border-color); border-radius: 6px; cursor: pointer;">Go Back</button>
      </div>
    `;
  }
}

initializeReader();
