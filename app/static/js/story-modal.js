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
      <div class="${isMobile ? 'w-full' : 'max-w-2xl w-full mx-4'} bg-white dark:bg-gray-800 rounded-${isMobile ? 't' : ''}-xl shadow-2xl p-6 transform transition-all" onclick="event.stopPropagation()">
        ${isMobile ? '<div class="w-12 h-1.5 bg-gray-300 dark:bg-gray-600 rounded-full mx-auto mb-4"></div>' : ''}

        <div class="flex flex-col md:flex-row gap-6">
          ${story.cover ? `
            <div class="flex-shrink-0 mx-auto md:mx-0">
              <img src="/api/cover/${story.cover}"
                   alt="${escapeHtml(story.title)} cover"
                   class="w-48 h-64 object-cover rounded-lg shadow-md">
            </div>
          ` : ''}

          <div class="flex-1 min-w-0">
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">${escapeHtml(story.title)}</h2>
            ${story.author ? `<p class="text-gray-600 dark:text-gray-400 mb-4">by ${escapeHtml(story.author)}</p>` : ''}

            <div class="flex flex-wrap gap-2 mb-4">
              ${hasEpub ? '<span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-200 rounded">EPUB</span>' : ''}
              ${hasHtml ? '<span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-200 rounded">HTML</span>' : ''}
              ${story.category ? `<span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-purple-100 dark:bg-purple-900/50 text-purple-800 dark:text-purple-200 rounded">${escapeHtml(story.category)}</span>` : ''}
            </div>

            ${story.tags && story.tags.length > 0 ? `
              <div class="mb-4">
                <p class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Tags:</p>
                <div class="flex flex-wrap gap-2">
                  ${story.tags.map(tag => `<span class="text-xs px-2 py-1 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded">${escapeHtml(tag)}</span>`).join('')}
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
              <button onclick="closeStoryModal()"
                      class="px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 text-sm font-medium rounded-lg transition-all duration-200">
                Close
              </button>
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
