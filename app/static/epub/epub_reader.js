(function() {
  const storyId = window.STORY_ID;
  const epubUrl = window.EPUB_URL;
  let book;
  let rendition;
  let currentLocation;

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
    
    if (rendition) {
      rendition.themes.select(theme);
      
      // Force update by directly modifying iframe styles
      setTimeout(() => {
        const iframe = document.querySelector('iframe');
        if (iframe && iframe.contentDocument && iframe.contentDocument.body) {
          const iframeBody = iframe.contentDocument.body;
          if (theme === 'dark') {
            iframeBody.style.color = '#e5e7eb';
            iframeBody.style.background = '#0f1419';
          } else {
            iframeBody.style.color = '#1a1a1a';
            iframeBody.style.background = '#ffffff';
          }
        }
      }, 10);
    }
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

  fontSelect.addEventListener('change', (e) => {
    const font = e.target.value;
    localStorage.setItem('fontFamily', font);
    if (rendition) {
      rendition.themes.default({
        'body': {
          'font-family': font + ' !important'
        },
        'p': {
          'font-family': font + ' !important'
        },
        'div': {
          'font-family': font + ' !important'
        }
      });
    }
  });

  fontSizeRange.addEventListener('input', (e) => {
    const size = e.target.value;
    fontSizeValue.textContent = size + 'px';
    localStorage.setItem('epubFontSize', size);
    if (rendition) {
      rendition.themes.fontSize(size + 'px');
      // Force re-render to apply font size immediately
      const currentLocation = rendition.currentLocation();
      if (currentLocation && currentLocation.start) {
        rendition.display(currentLocation.start.cfi);
      }
    }
  });

  lineHeightRange.value = savedLineHeight;
  lineHeightValue.textContent = savedLineHeight;

  lineHeightRange.addEventListener('input', (e) => {
    const height = e.target.value;
    lineHeightValue.textContent = height;
    localStorage.setItem('epubLineHeight', height);
    if (rendition) {
      rendition.themes.override('line-height', height);
    }
  });

  const savedWidth = localStorage.getItem('epubReadingWidth') || '800';
  widthRange.value = savedWidth;
  widthValue.textContent = savedWidth + 'px';
  document.documentElement.style.setProperty('--max-width', savedWidth + 'px');

  widthRange.addEventListener('input', (e) => {
    const width = e.target.value;
    widthValue.textContent = width + 'px';
    document.documentElement.style.setProperty('--max-width', width + 'px');
    localStorage.setItem('epubReadingWidth', width);
    if (rendition) {
      rendition.resize();
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
          cfi: localProgress.cfi
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

  async function saveProgress(location) {
    const progressData = {
      current_chapter: location.start.index,
      scroll_position: 0,
      cfi: location.start.cfi,
      timestamp: new Date().toISOString(),
      synced: false
    };

    await progressDB.saveProgress(storyId, progressData);

    try {
      const response = await fetch(`/epub/api/progress/${storyId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          current_chapter: location.start.index,
          scroll_position: 0,
          cfi: location.start.cfi
        })
      });

      if (response.ok) {
        await progressDB.markSynced(storyId, true);
      }
    } catch (error) {
      console.log('[Offline] Progress saved to IndexedDB, will sync when online');
    }
  }

  // Check if ePub is available (try both ePub and window.ePub)
  console.log('[EPUB] Starting initialization...');
  console.log('[EPUB] window.ePub:', typeof window.ePub);
  console.log('[EPUB] window.Epub:', typeof window.Epub);
  console.log('[EPUB] typeof ePub:', typeof ePub);
  
  const ePubConstructor = window.ePub || window.Epub || (typeof ePub !== 'undefined' ? ePub : undefined);
  
  if (typeof ePubConstructor === 'undefined') {
    console.error('[EPUB] EPUB.js library not loaded');
    console.log('[EPUB] Available globals:', Object.keys(window).filter(k => k.toLowerCase().includes('epub')));
    document.getElementById('viewer').innerHTML = '<div style="padding: 2rem; text-align: center;"><p>Error: EPUB.js library failed to load. Please refresh the page.</p></div>';
    return;
  }

  console.log('[EPUB] ePubConstructor found:', typeof ePubConstructor);
  console.log('[EPUB] Initializing EPUB with URL:', epubUrl);
  
  const cleanUrl = epubUrl.replace(/\/$/, '');
  console.log('[EPUB] Clean URL:', cleanUrl);
  console.log('[EPUB] Starting fetch...');

  // Load EPUB as ArrayBuffer to avoid path resolution issues
  fetch(cleanUrl)
    .then(response => {
      console.log('[EPUB] Fetch response received:', response.status, response.statusText);
      if (!response.ok) {
        throw new Error('Failed to fetch EPUB file: ' + response.status + ' ' + response.statusText);
      }
      console.log('[EPUB] Converting to ArrayBuffer...');
      return response.arrayBuffer();
    })
    .then(arrayBuffer => {
      console.log('[EPUB] EPUB file loaded, size:', arrayBuffer.byteLength);
      console.log('[EPUB] Creating book object...');
      
      // Initialize EPUB book with ArrayBuffer
      book = ePubConstructor(arrayBuffer);
      
      console.log('[EPUB] Book object created:', book);
      console.log('[EPUB] Creating rendition...');
      
      rendition = book.renderTo('viewer', {
        width: '100%',
        height: '100%',
        spread: 'none',
        allowScriptedContent: true
      });
      
      console.log('[EPUB] Rendition created:', rendition);
      console.log('[EPUB] Initializing reader...');
      
      initializeReader();
    })
    .catch(error => {
      console.error('[EPUB] Error loading EPUB:', error);
      console.error('[EPUB] Error stack:', error.stack);
      document.getElementById('viewer').innerHTML = '<div style="padding: 2rem; text-align: center;"><p>Error loading EPUB file: ' + error.message + '</p></div>';
    });

  function initializeReader() {

    rendition.themes.register('light', {
      body: {
        'color': '#1a1a1a',
        'background': '#ffffff'
      }
    });

    rendition.themes.register('dark', {
      body: {
        'color': '#e5e7eb',
        'background': '#0f1419'
      }
    });

    // Apply default styles including font family
    rendition.themes.default({
      '::selection': {
        'background': 'rgba(74, 144, 226, 0.3)'
      },
      'body': {
        'font-family': savedFont + ' !important'
      },
      'p': {
        'margin': '1.5em 0',
        'line-height': savedLineHeight,
        'font-family': savedFont + ' !important'
      },
      'div': {
        'font-family': savedFont + ' !important'
      },
      'span': {
        'font-family': savedFont + ' !important'
      }
    });

    rendition.themes.fontSize(savedFontSize + 'px');
    rendition.themes.select(getInitialTheme());

    progressDB.getProgress(storyId).then(localProgress => {
      let progressToUse = window.INITIAL_PROGRESS;

      if (localProgress) {
        const localTime = new Date(localProgress.timestamp || 0).getTime();
        const serverTime = progressToUse?.last_read_at ? new Date(progressToUse.last_read_at).getTime() : 0;

        if (localTime > serverTime) {
          console.log('[IndexedDB] Using local progress (newer than server)');
          progressToUse = localProgress;
        }
      }

      let startLocation;
      if (progressToUse && progressToUse.cfi) {
        startLocation = progressToUse.cfi;
      } else if (progressToUse && progressToUse.current_chapter !== null && progressToUse.current_chapter !== undefined) {
        startLocation = book.spine.get(progressToUse.current_chapter)?.href;
      }

      rendition.display(startLocation);
    }).catch(error => {
      console.error('[IndexedDB] Failed to load progress:', error);
      rendition.display();
    });

    book.ready.then(() => {
      return book.locations.generate(1024);
    }).then(() => {
      book.loaded.navigation.then(nav => {
        const tocContent = document.getElementById('tocContent');
        
        function renderTocItems(items) {
          return items.map(item => {
            const li = document.createElement('div');
            li.className = 'toc-item';
            li.textContent = item.label;
            li.addEventListener('click', () => {
              rendition.display(item.href);
              tocPanel.classList.remove('active');
            });
            return li;
          }).forEach(el => tocContent.appendChild(el));
        }
        
        renderTocItems(nav.toc);
      });
    });

    rendition.on('relocated', (location) => {
      currentLocation = location;
      
      const percent = book.locations.percentageFromCfi(location.start.cfi);
      progressFill.style.width = (percent * 100) + '%';
      
      const current = location.start.displayed.page;
      const total = location.start.displayed.total;
      locationInfo.textContent = `Page ${current} of ${total}`;
      
      saveProgress(location);
    });

    prevBtn.addEventListener('click', () => {
      rendition.prev();
    });

    nextBtn.addEventListener('click', () => {
      rendition.next();
    });

    // Touch swipe gestures for mobile - attach to rendition iframe
    let touchStartX = 0;
    let touchEndX = 0;
    let touchStartY = 0;
    
    rendition.on('rendered', () => {
      const iframe = document.querySelector('iframe');
      if (iframe && iframe.contentDocument) {
        const iframeDoc = iframe.contentDocument;
        const iframeBody = iframeDoc.body;
        
        // Disable overscroll and pull-to-refresh on iframe content
        if (iframeBody) {
          iframeBody.style.overscrollBehavior = 'none';
          iframeBody.style.touchAction = 'pan-x';
        }
        
        iframeDoc.addEventListener('touchstart', (e) => {
          touchStartX = e.changedTouches[0].screenX;
          touchStartY = e.changedTouches[0].screenY;
        }, { passive: true });
        
        iframeDoc.addEventListener('touchmove', (e) => {
          // Always prevent default to stop pull-to-refresh and vertical bounce
          e.preventDefault();
          
          const touchMoveX = e.changedTouches[0].screenX;
          const touchMoveY = e.changedTouches[0].screenY;
          const diffX = Math.abs(touchMoveX - touchStartX);
          const diffY = Math.abs(touchMoveY - touchStartY);
        }, { passive: false });
        
        iframeDoc.addEventListener('touchend', (e) => {
          touchEndX = e.changedTouches[0].screenX;
          handleSwipe();
        }, { passive: true });
      }
    });
    
    function handleSwipe() {
      const swipeThreshold = 50;
      const diff = touchStartX - touchEndX;
      
      if (Math.abs(diff) > swipeThreshold) {
        if (diff > 0) {
          // Swiped left - next page
          rendition.next();
        } else {
          // Swiped right - previous page
          rendition.prev();
        }
      }
    }

    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') {
        rendition.prev();
      } else if (e.key === 'ArrowRight') {
        rendition.next();
      }
    });

    syncProgressToServer();

    window.addEventListener('online', () => {
      console.log('[Sync] Connection restored, syncing progress...');
      syncProgressToServer();
    });
  }
})();
