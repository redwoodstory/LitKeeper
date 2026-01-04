const themeToggle = document.getElementById('themeToggle');
const html = document.documentElement;

function getInitialTheme() {
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme) return savedTheme;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function setTheme(theme) {
  if (theme === 'dark') {
    html.classList.add('dark');
  } else {
    html.classList.remove('dark');
  }
  localStorage.setItem('theme', theme);
}

themeToggle.addEventListener('click', () => {
  const currentTheme = html.classList.contains('dark') ? 'dark' : 'light';
  setTheme(currentTheme === 'dark' ? 'light' : 'dark');
});

function showHiddenWarnings() {
  sessionStorage.removeItem('mountWarningDismissed');
  sessionStorage.removeItem('secretKeyWarningDismissed');
  sessionStorage.removeItem('missingMetadataBannerDismissed');
  sessionStorage.removeItem('syncBannerDismissed');

  const mountWarning = document.getElementById('mountWarning');
  if (mountWarning) {
    mountWarning.classList.remove('hidden');
  }

  const secretKeyWarning = document.getElementById('secretKeyWarning');
  if (secretKeyWarning) {
    secretKeyWarning.classList.remove('hidden');
  }

  if (typeof loadMissingMetadata === 'function') {
    loadMissingMetadata();
  }

  const syncBanner = document.getElementById('syncBanner');
  if (syncBanner) {
    syncBanner.classList.remove('hidden');
  }
}

setTheme(getInitialTheme());

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
  if (!localStorage.getItem('theme')) {
    setTheme(e.matches ? 'dark' : 'light');
  }
});
