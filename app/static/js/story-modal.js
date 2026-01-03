function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatFileSize(bytes) {
  if (!bytes) return '';
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
}

function formatWordCount(count) {
  if (!count) return '';
  if (count < 1000) {
    return `${count} words`;
  }
  return `${(count / 1000).toFixed(1)}k words`;
}

document.addEventListener('click', function(e) {
  const storyCard = e.target.closest('.story-card-cover');
  if (storyCard) {
    try {
      const storyData = storyCard.getAttribute('data-story');
      const story = JSON.parse(storyData);
      showStoryModal(story);
    } catch (error) {
      console.error('Failed to parse story data:', error);
    }
  }
});

window.showStoryModal = function(story) {
  const hasEpub = story.formats.includes('epub');
  const hasHtml = story.formats.includes('html');
  const date = new Date(story.created_at);
  const formattedDate = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  const size = story.size ? formatFileSize(story.size) : '';

  const modalHtml = `
    <div id="storyModal" class="fixed inset-0 z-50 flex items-center md:items-center items-end justify-center bg-black/50 backdrop-blur-sm transition-opacity duration-200" onclick="closeStoryModal(event)">
      <div class="w-full md:w-auto md:max-w-4xl md:mx-4 h-full md:h-auto md:max-h-[90vh] bg-white dark:bg-gray-800 md:rounded-xl rounded-t-2xl shadow-2xl overflow-y-auto transform transition-all relative" onclick="event.stopPropagation()">
        <button onclick="closeStoryModal()"
                class="absolute top-4 right-4 z-20 w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full transition-all duration-200"
                aria-label="Close modal">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
          </svg>
        </button>

        <div class="p-6 md:p-8">
          <div class="flex flex-col md:flex-row gap-6">
            ${story.cover ? `
              <div class="flex-shrink-0 mx-auto md:mx-0">
                <img src="/api/cover/${story.cover}"
                     alt="${escapeHtml(story.title)} cover"
                     class="w-48 h-64 object-cover rounded-lg border-2 border-white/80 dark:border-white/10"
                     style="box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);">
              </div>
            ` : ''}

            <div class="flex-1 min-w-0">
              <h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">${escapeHtml(story.title)}</h2>
              ${story.author ? `
                <p class="text-gray-600 dark:text-gray-400 mb-2">
                  by ${story.author_url ? `<a href="${escapeHtml(story.author_url)}" target="_blank" rel="noopener noreferrer" class="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors duration-200 underline decoration-dotted">${escapeHtml(story.author)}</a>` : escapeHtml(story.author)}
                </p>
              ` : ''}
              ${story.source_url ? `
                <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
                  <a href="${escapeHtml(story.source_url)}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 hover:text-blue-600 dark:hover:text-blue-400 transition-colors duration-200">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                    </svg>
                    View on Literotica
                  </a>
                </p>
              ` : ''}

              <div class="flex flex-wrap gap-2 mb-4">
                ${hasEpub ? '<span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-200 rounded">EPUB</span>' : ''}
                ${hasHtml ? '<span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-200 rounded">HTML</span>' : ''}
                ${story.category ? `<span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-purple-100 dark:bg-purple-900/50 text-purple-800 dark:text-purple-200 rounded">${escapeHtml(story.category)}</span>` : ''}
              </div>

              ${story.tags && story.tags.length > 0 ? `
                <div class="mb-4">
                  <p class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Tags:</p>
                  <div class="flex flex-wrap gap-2">
                    ${story.tags.map(tag => `<span class="inline-flex items-center px-3 py-1.5 text-xs font-medium bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-full">${escapeHtml(tag)}</span>`).join('')}
                  </div>
                </div>
              ` : ''}

              <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
                Added ${formattedDate}
                ${story.page_count ? ` • ${story.page_count} page${story.page_count !== 1 ? 's' : ''}` : ''}
                ${story.word_count ? ` • ${formatWordCount(story.word_count)}` : ''}
                ${size ? ` • ${size}` : ''}
              </p>

              <div class="flex flex-col gap-6 mt-6">
                <div class="flex flex-col gap-3">
                  ${hasHtml ? `
                    <div class="flex gap-2">
                      <a href="/read/${story.html_file}"
                         class="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium bg-slate-900 dark:bg-white text-white dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-100 rounded-lg border border-slate-900 dark:border-white shadow-sm transition-all duration-200">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
                        </svg>
                        <span>Read HTML</span>
                      </a>
                      <a href="/download/html/${story.html_file}"
                         class="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium bg-white dark:bg-slate-800 text-slate-900 dark:text-white hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg border border-slate-200 dark:border-slate-600 shadow-sm transition-all duration-200"
                         download>
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                        </svg>
                        <span>Download HTML</span>
                      </a>
                    </div>
                  ` : ''}
                  ${hasEpub ? `
                    <div class="flex gap-2">
                      <button disabled
                              class="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-500 rounded-lg border border-slate-200 dark:border-slate-700 shadow-sm cursor-not-allowed opacity-50"
                              title="EPUB reader coming soon">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
                        </svg>
                        <span>Read EPUB</span>
                      </button>
                      <a href="/download/epub/${story.epub_file}"
                         class="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium bg-white dark:bg-slate-800 text-slate-900 dark:text-white hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg border border-slate-200 dark:border-slate-600 shadow-sm transition-all duration-200"
                         download>
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                        </svg>
                        <span>Download EPUB</span>
                      </a>
                    </div>
                  ` : ''}
                </div>

                ${hasHtml ? `
                  <button onclick="syncStoryFromModal('${story.html_file}', this)"
                          class="self-start px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700/50 rounded-md border border-slate-200/60 dark:border-slate-700 transition-all duration-200 inline-flex items-center gap-1.5"
                          title="Cache for offline reading">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                    </svg>
                    Sync for Offline
                  </button>
                ` : ''}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);
  document.body.style.overflow = 'hidden';

  const modal = document.getElementById('storyModal');
  const modalContent = modal.querySelector('div > div');

  let startY = 0;
  let currentY = 0;
  let isDragging = false;
  let initialScrollTop = 0;

  const handleTouchStart = (e) => {
    if (window.innerWidth >= 768) return;

    startY = e.touches[0].clientY;
    initialScrollTop = modalContent.scrollTop;
    isDragging = false;
  };

  const handleTouchMove = (e) => {
    if (window.innerWidth >= 768) return;

    currentY = e.touches[0].clientY;
    const deltaY = currentY - startY;

    if (initialScrollTop === 0 && deltaY > 0) {
      isDragging = true;
      e.preventDefault();
      modalContent.style.transform = `translateY(${deltaY}px)`;
      modalContent.style.transition = 'none';
    }
  };

  const handleTouchEnd = () => {
    if (window.innerWidth >= 768) return;

    const deltaY = currentY - startY;

    if (isDragging) {
      if (deltaY > 100) {
        closeStoryModal();
      } else {
        modalContent.style.transition = 'transform 0.2s ease-out';
        modalContent.style.transform = 'translateY(0)';
      }
      isDragging = false;
    }
  };

  modalContent.addEventListener('touchstart', handleTouchStart, { passive: false });
  modalContent.addEventListener('touchmove', handleTouchMove, { passive: false });
  modalContent.addEventListener('touchend', handleTouchEnd);

  setTimeout(() => {
    modal.classList.add('active');
  }, 10);

  document.addEventListener('keydown', handleModalEscape);
};

function handleModalEscape(e) {
  if (e.key === 'Escape') {
    closeStoryModal();
  }
}

window.closeStoryModal = function(event) {
  if (event && event.target !== event.currentTarget) {
    return;
  }

  const modal = document.getElementById('storyModal');
  if (modal) {
    modal.classList.add('opacity-0');
    setTimeout(() => {
      modal.remove();
      document.body.style.overflow = '';
    }, 200);
  }

  document.removeEventListener('keydown', handleModalEscape);
};

window.syncStoryFromModal = async function(filename, button) {
  const originalText = button.innerHTML;
  button.disabled = true;
  button.innerHTML = '⏳ Syncing...';

  try {
    const response = await fetch(`/read/${filename}`);
    if (response.ok) {
      button.innerHTML = '✅ Synced!';
      setTimeout(() => {
        button.innerHTML = originalText;
        button.disabled = false;
      }, 2000);
    } else {
      throw new Error('Failed to fetch story');
    }
  } catch (error) {
    console.error('Sync error:', error);
    button.innerHTML = '❌ Failed';
    setTimeout(() => {
      button.innerHTML = originalText;
      button.disabled = false;
    }, 2000);
  }
};
