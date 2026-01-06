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
  headerVisible = !headerVisible;
  
  if (headerVisible) {
    readerHeader.style.transform = 'translateY(0)';
    readerFooter.style.transform = 'translateY(0)';
    
    if (headerTimeout) clearTimeout(headerTimeout);
    headerTimeout = setTimeout(() => {
      if (headerVisible) toggleHeader();
    }, 3000);
  } else {
    readerHeader.style.transform = 'translateY(-100%)';
    readerFooter.style.transform = 'translateY(100%)';
    if (headerTimeout) clearTimeout(headerTimeout);
  }
}

function showHeaderTemporarily() {
  if (!headerVisible) {
    headerVisible = true;
    readerHeader.style.transform = 'translateY(0)';
    readerFooter.style.transform = 'translateY(0)';
  }
  
  if (headerTimeout) clearTimeout(headerTimeout);
  headerTimeout = setTimeout(() => {
    if (headerVisible) toggleHeader();
  }, 3000);
}

function getInitialTheme() {
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme) return savedTheme;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function setTheme(theme) {
  html.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
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
    applyThemeStyles(theme);
  }
}

function applyThemeStyles(theme) {
  const isDark = theme === 'dark';
  const styles = `
    @namespace epub "http://www.idpf.org/2007/ops";
    html {
      color-scheme: ${isDark ? 'dark' : 'light'};
    }
    body {
      color: ${isDark ? '#e5e7eb' : '#1a1a1a'} !important;
      background: ${isDark ? '#0f1419' : '#ffffff'} !important;
    }
    p, li, blockquote, dd {
      line-height: ${localStorage.getItem('epubLineHeight') || '1.6'};
    }
  `;
  view.renderer.setStyles?.(styles);
}

function toggleTheme() {
  const currentTheme = html.getAttribute('data-theme');
  setTheme(currentTheme === 'dark' ? 'light' : 'dark');
}

setTheme(getInitialTheme());
themeToggle.addEventListener('click', toggleTheme);

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

const savedFont = localStorage.getItem('fontFamily') || "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif";
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
    }
    p, li, blockquote, dd {
      line-height: ${lineHeight};
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
  
  showHeaderTemporarily();

  try {
    const response = await fetch(epubUrl);
    if (!response.ok) {
      throw new Error('Failed to fetch EPUB file: ' + response.status);
    }
    const blob = await response.blob();
    console.log('[Foliate] EPUB file loaded, size:', blob.size);

    const file = new File([blob], 'book.epub', { type: 'application/epub+zip' });
    console.log('[Foliate] Created File object with name:', file.name);

    view = document.createElement('foliate-view');
    const viewerContainer = document.getElementById('viewer');
    viewerContainer.appendChild(view);

    await view.open(file);
    console.log('[Foliate] Book opened successfully');

    const isMobile = window.innerWidth <= 768;
    view.renderer.setAttribute('flow', 'paginated');
    view.renderer.setAttribute('animated', '');
    view.renderer.setAttribute('margin', '0');
    view.renderer.setAttribute('gap', '0');
    if (!isMobile) {
      view.renderer.setAttribute('max-inline-size', savedWidth);
    }

    updateReaderStyles();

    view.addEventListener('load', (e) => {
      console.log('[Foliate] Content loaded, setting up tap zones');
      const { doc } = e.detail;
      
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

    if (progressToUse && progressToUse.cfi) {
      console.log('[Progress] Restoring from CFI:', progressToUse.cfi);
      try {
        await view.goTo(progressToUse.cfi);
        setTimeout(() => { isInitialLoad = false; }, 500);
      } catch (e) {
        console.warn('[Progress] Failed to restore from CFI, starting from beginning');
        isInitialLoad = false;
      }
    } else if (progressToUse && progressToUse.percentage !== null && progressToUse.percentage !== undefined) {
      console.log('[Progress] Restoring from percentage:', progressToUse.percentage);
      await view.goToFraction(progressToUse.percentage);
      setTimeout(() => { isInitialLoad = false; }, 500);
    } else {
      console.log('[Progress] No saved position, starting from beginning');
      isInitialLoad = false;
    }

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
    document.getElementById('viewer').innerHTML = '<div style="padding: 2rem; text-align: center;"><p>Error loading EPUB file: ' + error.message + '</p></div>';
  }
}

initializeReader();
