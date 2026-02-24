(function() {
  const html = document.documentElement;
  const root = document.documentElement;
  const themeToggle = document.getElementById('themeToggle');
  const settingsToggle = document.getElementById('settingsToggle');
  const settingsPanel = document.getElementById('settingsPanel');
  const fontSelect = document.getElementById('fontSelect');
  const fontSizeRange = document.getElementById('fontSizeRange');
  const fontSizeValue = document.getElementById('fontSizeValue');
  const lineHeightRange = document.getElementById('lineHeightRange');
  const lineHeightValue = document.getElementById('lineHeightValue');
  const widthRange = document.getElementById('widthRange');
  const widthValue = document.getElementById('widthValue');

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
    if (theme === 'dark') {
      html.setAttribute('data-theme', 'dark');
    } else {
      html.setAttribute('data-theme', 'light');
    }
    const sunIcon = themeToggle.querySelector('.sun-icon');
    const moonIcon = themeToggle.querySelector('.moon-icon');
    if (theme === 'dark') {
      sunIcon.style.display = 'block';
      moonIcon.style.display = 'none';
    } else {
      sunIcon.style.display = 'none';
      moonIcon.style.display = 'block';
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

  // Settings panel toggle
  settingsToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    settingsPanel.classList.toggle('active');
  });

  // Close settings when clicking outside
  document.addEventListener('click', (e) => {
    if (!settingsPanel.contains(e.target) && !settingsToggle.contains(e.target)) {
      settingsPanel.classList.remove('active');
    }
  });

  // Font family selection
  const savedFont = localStorage.getItem('fontFamily') || "ProximaNovaMedium, system-ui, -apple-system, 'Segoe UI', Roboto, Ubuntu, Cantarell, 'Noto Sans', Helvetica, Arial, sans-serif";
  fontSelect.value = savedFont;
  root.style.setProperty('--font-family', savedFont);

  fontSelect.addEventListener('change', (e) => {
    const font = e.target.value;
    root.style.setProperty('--font-family', font);
    localStorage.setItem('fontFamily', font);
  });

  // Font size adjustment
  const savedFontSize = localStorage.getItem('fontSize') || '16';
  fontSizeRange.value = savedFontSize;
  fontSizeValue.textContent = savedFontSize + 'px';
  root.style.setProperty('--font-size', savedFontSize + 'px');

  fontSizeRange.addEventListener('input', (e) => {
    const size = e.target.value;
    fontSizeValue.textContent = size + 'px';
    root.style.setProperty('--font-size', size + 'px');
    localStorage.setItem('fontSize', size);
  });

  // Line height adjustment
  const savedLineHeight = localStorage.getItem('lineHeight') || '1.58';
  lineHeightRange.value = savedLineHeight;
  lineHeightValue.textContent = savedLineHeight;
  root.style.setProperty('--line-height', savedLineHeight);

  lineHeightRange.addEventListener('input', (e) => {
    const height = e.target.value;
    lineHeightValue.textContent = height;
    root.style.setProperty('--line-height', height);
    localStorage.setItem('lineHeight', height);
  });

  // Width adjustment
  const savedWidth = localStorage.getItem('readingWidth') || '800';
  widthRange.value = savedWidth;
  widthValue.textContent = savedWidth + 'px';
  root.style.setProperty('--max-width', savedWidth + 'px');

  widthRange.addEventListener('input', (e) => {
    const width = e.target.value;
    widthValue.textContent = width + 'px';
    root.style.setProperty('--max-width', width + 'px');
    localStorage.setItem('readingWidth', width);
  });

  // Mobile margin adjustment
  const marginRange = document.getElementById('marginRange');
  const marginValue = document.getElementById('marginValue');
  const savedMargin = localStorage.getItem('mobileMargin') || '16';
  marginRange.value = savedMargin;
  marginValue.textContent = savedMargin + 'px';
  root.style.setProperty('--mobile-margin', savedMargin + 'px');

  marginRange.addEventListener('input', (e) => {
    const margin = e.target.value;
    marginValue.textContent = margin + 'px';
    root.style.setProperty('--mobile-margin', margin + 'px');
    localStorage.setItem('mobileMargin', margin);
  });

  function applyMobileVisibility() {
    const mobile = window.innerWidth <= 768;
    document.querySelectorAll('.desktop-only-setting').forEach(el => {
      el.style.display = mobile ? 'none' : '';
    });
    document.querySelectorAll('.mobile-only-setting').forEach(el => {
      el.style.display = mobile ? '' : 'none';
    });
  }
  applyMobileVisibility();
  window.addEventListener('resize', applyMobileVisibility);

  // Auto-hide header on mobile: hides on scroll, reveals on tap
  const readerHeader = document.querySelector('.reader-header');
  const isMobile = window.innerWidth <= 768;

  if (isMobile && readerHeader) {
    let isHidden = false;
    let hideTimeout;

    function showHeader() {
      readerHeader.classList.remove('hidden');
      isHidden = false;
      clearTimeout(hideTimeout);
      hideTimeout = setTimeout(() => {
        if (!settingsPanel.classList.contains('active')) {
          readerHeader.classList.add('hidden');
          isHidden = true;
        }
      }, 3000);
    }

    let lastScrollTop = 0;
    window.addEventListener('scroll', () => {
      const currentScrollTop = window.pageYOffset || document.documentElement.scrollTop;
      if (Math.abs(currentScrollTop - lastScrollTop) < 5) return;

      if (currentScrollTop > lastScrollTop && currentScrollTop > 50 && !isHidden) {
        readerHeader.classList.add('hidden');
        settingsPanel.classList.remove('active');
        isHidden = true;
        clearTimeout(hideTimeout);
      }

      lastScrollTop = currentScrollTop;
    }, { passive: true });

    document.addEventListener('click', () => {
      if (isHidden) showHeader();
    });
  }

  if (window.STORY_ID) {
    const storyId = window.STORY_ID;
    const initialProgress = window.INITIAL_PROGRESS;

    // Lightweight IndexedDB wrapper — mirrors epub_reader.js ProgressDB,
    // uses the same db/store so both readers share local cache.
    const progressDB = {
      dbName: 'LitKeeperProgress',
      storeName: 'reading_progress',
      _db: null,

      async open() {
        if (this._db) return this._db;
        return new Promise((resolve, reject) => {
          const req = indexedDB.open(this.dbName, 1);
          req.onupgradeneeded = (e) => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains(this.storeName)) {
              db.createObjectStore(this.storeName, { keyPath: 'story_id' });
            }
          };
          req.onsuccess = (e) => { this._db = e.target.result; resolve(this._db); };
          req.onerror = () => reject(req.error);
        });
      },

      async save(data) {
        try {
          const db = await this.open();
          return new Promise((resolve, reject) => {
            const tx = db.transaction(this.storeName, 'readwrite');
            tx.objectStore(this.storeName).put(data);
            tx.oncomplete = resolve;
            tx.onerror = () => reject(tx.error);
          });
        } catch (_) {}
      }
    };

    let pendingSync = false;

    async function saveProgress(chapter, para, scrollPos, pct) {
      const payload = {
        current_chapter: chapter,
        current_paragraph: para,
        scroll_position: scrollPos,
        percentage: pct
      };

      // Save locally first (offline resilience)
      await progressDB.save({
        story_id: storyId,
        ...payload,
        timestamp: new Date().toISOString(),
        synced: false
      });

      try {
        const res = await fetch(`/epub/api/progress/${storyId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          pendingSync = false;
        } else {
          pendingSync = true;
        }
      } catch (_) {
        pendingSync = true;
      }
    }

    async function syncPending() {
      if (!pendingSync) return;
      const db = await progressDB.open().catch(() => null);
      if (!db) return;
      const record = await new Promise((resolve) => {
        const tx = db.transaction(progressDB.storeName, 'readonly');
        const req = tx.objectStore(progressDB.storeName).get(storyId);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => resolve(null);
      });
      if (!record) return;
      try {
        await fetch(`/epub/api/progress/${storyId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            current_chapter: record.current_chapter,
            current_paragraph: record.current_paragraph,
            scroll_position: record.scroll_position,
            percentage: record.percentage
          })
        });
        pendingSync = false;
      } catch (_) {}
    }

    window.addEventListener('online', syncPending);

    // --- Scroll tracking ---
    function getTopVisibleParagraph() {
      const paras = document.querySelectorAll('p[data-chapter]');
      for (const p of paras) {
        const rect = p.getBoundingClientRect();
        if (rect.top >= -10) return p;
      }
      return paras[paras.length - 1] || null;
    }

    let scrollTimer = null;
    window.addEventListener('scroll', () => {
      clearTimeout(scrollTimer);
      scrollTimer = setTimeout(() => {
        const scrollable = document.documentElement.scrollHeight - window.innerHeight;
        const pct = scrollable > 0 ? Math.min(1, window.scrollY / scrollable) : 0;
        const p = getTopVisibleParagraph();
        const chapter = p ? parseInt(p.dataset.chapter, 10) : 1;
        const para = p ? parseInt(p.dataset.para, 10) : 0;
        saveProgress(chapter, para, Math.round(window.scrollY), pct);
      }, 1500);
    }, { passive: true });

    // --- Restore position on load ---
    function restorePosition() {
      if (!initialProgress) return;

      const { current_chapter: chapter, current_paragraph: para, percentage: pct } = initialProgress;

      // If we have valid chapter-level data (HTML reader saved it), jump to that paragraph.
      // chapter === 0 means the progress came from the EPUB reader which always writes 0.
      if (chapter && chapter > 0) {
        const target = document.querySelector(`[data-chapter="${chapter}"][data-para="${para}"]`);
        if (target) {
          target.scrollIntoView({ behavior: 'instant', block: 'start' });
          return;
        }
      }

      // Fallback: use percentage (works cross-format)
      if (pct && pct > 0) {
        const scrollable = document.documentElement.scrollHeight - window.innerHeight;
        if (scrollable > 0) {
          window.scrollTo({ top: scrollable * pct, behavior: 'instant' });
        }
      }
    }

    // Wait for layout to settle before restoring
    requestAnimationFrame(() => requestAnimationFrame(restorePosition));
  }

})();
