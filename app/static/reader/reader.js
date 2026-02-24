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

  // Auto-hide controls on scroll (mobile only)
  let lastScrollTop = 0;
  let scrollTimeout;
  const controlsLeft = document.querySelector('.controls-left');
  const controlsRight = document.querySelector('.controls');

  // Only enable auto-hide on mobile/tablet devices
  const isMobile = window.innerWidth <= 768;

  if (isMobile && controlsLeft && controlsRight) {
    let isHidden = false;

    window.addEventListener('scroll', () => {
      // Clear existing timeout
      clearTimeout(scrollTimeout);

      const currentScrollTop = window.pageYOffset || document.documentElement.scrollTop;

      // Ignore very small scroll movements (less than 5px)
      if (Math.abs(currentScrollTop - lastScrollTop) < 5) {
        return;
      }

      // Scrolling down - hide controls
      if (currentScrollTop > lastScrollTop && currentScrollTop > 50) {
        if (!isHidden) {
          controlsLeft.classList.add('hidden');
          controlsRight.classList.add('hidden');
          settingsPanel.classList.remove('active'); // Close settings if open
          isHidden = true;
        }
      }
      // Scrolling up - show controls
      else if (currentScrollTop < lastScrollTop) {
        if (isHidden) {
          controlsLeft.classList.remove('hidden');
          controlsRight.classList.remove('hidden');
          isHidden = false;
        }
      }

      lastScrollTop = currentScrollTop;

      // Show controls after 2 seconds of no scrolling
      scrollTimeout = setTimeout(() => {
        if (isHidden) {
          controlsLeft.classList.remove('hidden');
          controlsRight.classList.remove('hidden');
          isHidden = false;
        }
      }, 2000);
    }, { passive: true });
  }
})();
