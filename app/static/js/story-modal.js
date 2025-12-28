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
  const isMobile = window.innerWidth < 768;

  const hasEpub = story.formats.includes('epub');
  const hasHtml = story.formats.includes('html');
  const date = new Date(story.created_at);
  const formattedDate = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  const size = story.size ? formatFileSize(story.size) : '';

  const modalHtml = `
    <div id="storyModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm ${isMobile ? 'items-end' : ''}" onclick="closeStoryModal(event)">
      <div class="${isMobile ? 'w-full' : 'max-w-4xl mx-4'} bg-white dark:bg-gray-800 rounded-${isMobile ? 't' : ''}-xl shadow-2xl p-6 md:p-8 transform transition-all relative" onclick="event.stopPropagation()">
        <button onclick="closeStoryModal()"
                class="absolute top-4 right-4 w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full transition-all duration-200"
                aria-label="Close modal">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
          </svg>
        </button>
        ${isMobile ? '<div class="w-12 h-1.5 bg-gray-300 dark:bg-gray-600 rounded-full mx-auto mb-4"></div>' : ''}

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
              ${size ? ` • ${size}` : ''}
            </p>

            <div class="flex flex-wrap gap-3 mt-6">
              ${hasHtml ? `
                <button onclick="syncStoryFromModal('${story.html_file}', this)"
                   class="px-4 py-2 bg-purple-500 hover:bg-purple-600 text-white text-sm font-medium rounded-lg transition-all duration-200 whitespace-nowrap"
                   title="Cache for offline reading">
                  📥 Sync Offline
                </button>
                <a href="/read/${story.html_file}"
                   class="px-4 py-2 bg-green-500 hover:bg-green-600 text-white text-sm font-medium rounded-lg transition-all duration-200 whitespace-nowrap">
                  📖 Read
                </a>
              ` : ''}
              ${hasEpub ? `
                <a href="/download/${story.epub_file}"
                   class="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium rounded-lg transition-all duration-200 whitespace-nowrap">
                  ⬇️ Download EPUB
                </a>
              ` : ''}
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);

  setTimeout(() => {
    document.getElementById('storyModal').classList.add('active');
  }, 10);

  if (isMobile) {
    let startY = 0;
    let currentY = 0;
    const modal = document.getElementById('storyModal');
    const modalContent = modal.querySelector('div > div');

    modalContent.addEventListener('touchstart', (e) => {
      startY = e.touches[0].clientY;
    });

    modalContent.addEventListener('touchmove', (e) => {
      currentY = e.touches[0].clientY;
      const deltaY = currentY - startY;

      if (deltaY > 0) {
        modalContent.style.transform = `translateY(${deltaY}px)`;
      }
    });

    modalContent.addEventListener('touchend', () => {
      const deltaY = currentY - startY;
      if (deltaY > 100) {
        closeStoryModal();
      } else {
        modalContent.style.transform = 'translateY(0)';
      }
    });
  }

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
    setTimeout(() => modal.remove(), 200);
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
