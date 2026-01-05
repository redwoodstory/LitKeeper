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
  const bookmarksToggle = document.getElementById('bookmarksToggle');
  const bookmarksPanel = document.getElementById('bookmarksPanel');
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
    bookmarksPanel.classList.remove('active');
  });

  tocToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    tocPanel.classList.toggle('active');
    settingsPanel.classList.remove('active');
    bookmarksPanel.classList.remove('active');
  });

  bookmarksToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    bookmarksPanel.classList.toggle('active');
    settingsPanel.classList.remove('active');
    tocPanel.classList.remove('active');
  });

  document.querySelectorAll('.close-panel').forEach(btn => {
    btn.addEventListener('click', () => {
      tocPanel.classList.remove('active');
      bookmarksPanel.classList.remove('active');
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

  async function saveProgress(location) {
    try {
      const response = await fetch(`/epub/api/progress/${storyId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          current_chapter: location.start.index,
          scroll_position: 0
        })
      });
      
      if (!response.ok) {
        console.error('Failed to save progress');
      }
    } catch (error) {
      console.error('Error saving progress:', error);
    }
  }

  async function loadBookmarks() {
    try {
      const response = await fetch(`/epub/api/bookmarks/${storyId}`);
      const bookmarks = await response.json();
      
      const container = document.getElementById('bookmarksContent');
      if (bookmarks.length === 0) {
        container.innerHTML = '<p style="color: var(--secondary-text); text-align: center; padding: 2rem;">No bookmarks yet</p>';
        return;
      }
      
      container.innerHTML = bookmarks.map(b => `
        <div class="bookmark-item" data-chapter="${b.chapter_number}">
          <div style="font-weight: 500;">Chapter ${b.chapter_number}</div>
          ${b.note ? `<div class="bookmark-note">${b.note}</div>` : ''}
          <button onclick="deleteBookmark(${b.id})" style="margin-top: 0.5rem; padding: 0.25rem 0.5rem; font-size: 0.75rem; background: var(--bg-color); border: 1px solid var(--border-color); border-radius: 4px; cursor: pointer;">Delete</button>
        </div>
      `).join('');
      
      container.querySelectorAll('.bookmark-item').forEach(item => {
        item.addEventListener('click', (e) => {
          if (e.target.tagName !== 'BUTTON') {
            const chapter = parseInt(item.dataset.chapter);
            if (rendition && book.spine.get(chapter)) {
              rendition.display(book.spine.get(chapter).href);
              bookmarksPanel.classList.remove('active');
            }
          }
        });
      });
    } catch (error) {
      console.error('Error loading bookmarks:', error);
    }
  }

  window.deleteBookmark = async function(bookmarkId) {
    try {
      const response = await fetch(`/epub/api/bookmarks/${bookmarkId}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        loadBookmarks();
      }
    } catch (error) {
      console.error('Error deleting bookmark:', error);
    }
  };

  async function addBookmark() {
    if (!currentLocation) return;
    
    const note = prompt('Add a note (optional):');
    
    try {
      const response = await fetch(`/epub/api/bookmarks/${storyId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          chapter_number: currentLocation.start.index,
          note: note || null
        })
      });
      
      if (response.ok) {
        loadBookmarks();
        alert('Bookmark added!');
      }
    } catch (error) {
      console.error('Error adding bookmark:', error);
    }
  }

  // Check if ePub is available (try both ePub and window.ePub)
  const ePubConstructor = window.ePub || window.Epub || ePub;
  
  if (typeof ePubConstructor === 'undefined') {
    console.error('EPUB.js library not loaded');
    console.log('Available globals:', Object.keys(window).filter(k => k.toLowerCase().includes('epub')));
    document.getElementById('viewer').innerHTML = '<div style="padding: 2rem; text-align: center;"><p>Error: EPUB.js library failed to load. Please refresh the page.</p></div>';
    return;
  }

  console.log('Initializing EPUB with URL:', epubUrl);

  // Load EPUB as ArrayBuffer to avoid path resolution issues
  fetch(epubUrl.replace(/\/$/, ''))
    .then(response => {
      if (!response.ok) {
        throw new Error('Failed to fetch EPUB file');
      }
      return response.arrayBuffer();
    })
    .then(arrayBuffer => {
      console.log('EPUB file loaded, size:', arrayBuffer.byteLength);
      
      // Initialize EPUB book with ArrayBuffer
      book = ePubConstructor(arrayBuffer);
      
      console.log('Book object created:', book);
      
      rendition = book.renderTo('viewer', {
        width: '100%',
        height: '100%',
        spread: 'none',
        allowScriptedContent: true
      });
      
      console.log('Rendition created:', rendition);
      
      initializeReader();
    })
    .catch(error => {
      console.error('Error loading EPUB:', error);
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

    const initialProgress = window.INITIAL_PROGRESS;
    const startLocation = initialProgress && initialProgress.current_chapter 
      ? book.spine.get(initialProgress.current_chapter)?.href 
      : undefined;

    rendition.display(startLocation);

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
      } else if (e.key === 'b' && e.ctrlKey) {
        e.preventDefault();
        addBookmark();
      }
    });

    rendition.on('selected', (cfiRange, contents) => {
      const selection = contents.window.getSelection();
      const text = selection.toString();
      
      if (text.length > 0) {
        const shouldBookmark = confirm('Add bookmark at this location?');
        if (shouldBookmark) {
          addBookmark();
        }
      }
    });

    loadBookmarks();
  }
})();
