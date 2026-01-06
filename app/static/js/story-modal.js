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
  const hasHtml = story.formats.includes('html') || story.formats.includes('json');
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
                <p class="text-sm text-gray-500 dark:text-gray-400 mb-2">
                  <a href="${escapeHtml(story.source_url)}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 hover:text-blue-600 dark:hover:text-blue-400 transition-colors duration-200">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                    </svg>
                    View on Literotica
                  </a>
                </p>
              ` : ''}
              ${story.series_url ? `
                <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
                  <a href="${escapeHtml(story.series_url)}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 hover:text-blue-600 dark:hover:text-blue-400 transition-colors duration-200">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    View Full Series on Literotica
                  </a>
                </p>
              ` : ''}

              <div class="flex flex-wrap gap-2 mb-4">
                ${hasEpub ? '<span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-200 rounded">EPUB</span>' : ''}
                ${hasHtml ? '<span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-200 rounded">HTML</span>' : ''}
                ${story.category ? `<span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-purple-100 dark:bg-purple-900/50 text-purple-800 dark:text-purple-200 rounded">${escapeHtml(story.category)}</span>` : ''}
                ${story.is_series ? `<span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-indigo-100 dark:bg-indigo-900/50 text-indigo-800 dark:text-indigo-200 rounded">${story.chapter_count} ${story.chapter_count === 1 ? 'Part' : 'Parts'}</span>` : ''}
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
                      <a href="/epub/reader/${story.id}"
                         class="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium bg-slate-900 dark:bg-white text-white dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-100 rounded-lg border border-slate-900 dark:border-white shadow-sm transition-all duration-200">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
                        </svg>
                        <span>Read EPUB</span>
                      </a>
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

                <div class="flex flex-wrap gap-2">
                  ${hasHtml ? `
                    <button onclick="syncStoryFromModal('${story.html_file}', this)"
                            class="px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700/50 rounded-md border border-slate-200/60 dark:border-slate-700 transition-all duration-200 inline-flex items-center gap-1.5"
                            title="Cache for offline reading">
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                      </svg>
                      Sync for Offline
                    </button>
                  ` : ''}
                  ${hasEpub && !hasHtml ? `
                    <button onclick="addHtmlFormat(${story.id}, '${escapeHtml(story.title).replace(/'/g, "\\'")}', '${escapeHtml(story.author).replace(/'/g, "\\'")}', this)"
                            class="px-3 py-1.5 text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-md border border-blue-200/60 dark:border-blue-700 transition-all duration-200 inline-flex items-center gap-1.5"
                            title="Generate HTML format from Literotica">
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                      </svg>
                      Add HTML
                    </button>
                  ` : ''}
                  ${hasHtml && !hasEpub ? `
                    <button onclick="addEpubFormat(${story.id}, this)"
                            class="px-3 py-1.5 text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-md border border-blue-200/60 dark:border-blue-700 transition-all duration-200 inline-flex items-center gap-1.5"
                            title="Generate EPUB format from existing data">
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                      </svg>
                      Add EPUB
                    </button>
                  ` : ''}
                  ${!story.source_url ? `
                    <button onclick="openRefreshModal(${story.id}, '${escapeHtml(story.title).replace(/'/g, "\\'")}', '${escapeHtml(story.author).replace(/'/g, "\\'")}')"
                            class="px-3 py-1.5 text-xs font-medium text-amber-600 dark:text-amber-400 hover:text-amber-700 dark:hover:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/20 rounded-md border border-amber-200/60 dark:border-amber-700 transition-all duration-200 inline-flex items-center gap-1.5"
                            title="Add metadata from Literotica">
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                      </svg>
                      Refresh Metadata
                    </button>
                  ` : ''}
                  ${story.source_url ? `
                    <button onclick="toggleAutoUpdate(${story.id}, ${story.auto_update_enabled}, this)"
                            class="px-3 py-1.5 text-xs font-medium ${story.auto_update_enabled ? 'text-green-600 dark:text-green-400 hover:text-green-700 dark:hover:text-green-300 hover:bg-green-50 dark:hover:bg-green-900/20 border-green-200/60 dark:border-green-700' : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700/50 border-slate-200/60 dark:border-slate-700'} rounded-md border transition-all duration-200 inline-flex items-center gap-1.5"
                            title="${story.auto_update_enabled ? 'Disable automatic updates' : 'Enable automatic updates'}">
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                      </svg>
                      Auto-Update: ${story.auto_update_enabled ? 'ON' : 'OFF'}
                    </button>
                  ` : ''}
                  <button onclick="confirmDeleteStory(${story.id}, '${escapeHtml(story.title).replace(/'/g, "\\'")}')"
                          class="px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md border border-red-200/60 dark:border-red-700 transition-all duration-200 inline-flex items-center gap-1.5"
                          title="Delete this story">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                    </svg>
                    Delete Story
                  </button>
                </div>
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

window.addEpubFormat = async function(storyId, button) {
  const originalText = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `
    <svg class="w-3.5 h-3.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
    </svg>
    Generating...
  `;

  try {
    const response = await fetch(`/api/format/generate-epub/${storyId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'HX-Request': 'true'
      }
    });

    const result = await response.json();

    if (result.success) {
      showFormatSuccessToast('EPUB format created successfully!');
      if (result.story) {
        updateModalWithNewStory(result.story);
      } else {
        setTimeout(() => window.location.reload(), 1500);
      }
    } else {
      throw new Error(result.message || 'Failed to generate EPUB');
    }
  } catch (error) {
    console.error('EPUB generation error:', error);
    showFormatErrorToast('Failed to generate EPUB format');
    button.innerHTML = originalText;
    button.disabled = false;
  }
};

window.addHtmlFormat = async function(storyId, storyTitle, storyAuthor, button) {
  const originalText = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `
    <svg class="w-3.5 h-3.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
    </svg>
    Checking...
  `;

  try {
    const response = await fetch(`/api/format/generate-html/${storyId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'HX-Request': 'true'
      }
    });

    const result = await response.json();

    if (result.success) {
      showFormatSuccessToast('HTML format created successfully!');
      if (result.story) {
        updateModalWithNewStory(result.story);
      } else {
        setTimeout(() => window.location.reload(), 1500);
      }
    } else if (result.needs_url) {
      button.innerHTML = originalText;
      button.disabled = false;
      
      showInlineHtmlProgress(storyId, storyTitle, storyAuthor);
    } else {
      throw new Error(result.message || 'Failed to generate HTML');
    }
  } catch (error) {
    console.error('HTML generation error:', error);
    showFormatErrorToast('Failed to generate HTML format');
    button.innerHTML = originalText;
    button.disabled = false;
  }
};

function showInlineHtmlProgress(storyId, storyTitle, storyAuthor) {
  const modal = document.getElementById('storyModal');
  if (!modal) return;
  
  const modalContent = modal.querySelector('.p-6.md\\:p-8');
  if (!modalContent) return;
  
  const progressHtml = `
    <div id="htmlProgressSection" class="mt-6 border-t border-slate-200 dark:border-slate-700 pt-6">
      <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
        <div id="htmlProgressContent">
          <div class="flex items-center gap-3 mb-3">
            <svg class="w-5 h-5 animate-spin text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
            <span class="font-medium text-blue-900 dark:text-blue-100">Searching for story on Literotica...</span>
          </div>
          <p class="text-sm text-blue-700 dark:text-blue-300">This will take a moment</p>
        </div>
      </div>
    </div>
  `;
  
  const existingProgress = document.getElementById('htmlProgressSection');
  if (existingProgress) {
    existingProgress.remove();
  }
  
  modalContent.insertAdjacentHTML('beforeend', progressHtml);
  
  searchForStoryInline(storyId, storyTitle, storyAuthor);
}

async function searchForStoryInline(storyId, title, author) {
  const contentDiv = document.getElementById('htmlProgressContent');
  if (!contentDiv) return;
  
  try {
    const response = await fetch(`/api/metadata/search/${storyId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    const data = await response.json();
    
    if (!data.success) {
      contentDiv.innerHTML = `
        <div class="text-center py-4">
          <svg class="w-12 h-12 mx-auto text-slate-400 dark:text-slate-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
          <p class="text-slate-900 dark:text-white font-medium mb-2">${data.message}</p>
          <p class="text-sm text-slate-600 dark:text-slate-400 mb-4">Enter a Literotica URL below to continue</p>
          ${renderInlineManualUrlInput(storyId)}
        </div>
      `;
      return;
    }
    
    contentDiv.innerHTML = `
      <div class="mb-4">
        <p class="text-base font-medium text-slate-900 dark:text-white mb-3">Select the matching story:</p>
        <p class="text-sm text-slate-600 dark:text-slate-400 mb-4">Choose the best match to generate HTML format</p>
      </div>
      ${renderInlineSearchResults(storyId, data.results, data.auto_match ? data.best_match.url : null)}
      ${renderInlineManualUrlInput(storyId)}
    `;
  } catch (error) {
    contentDiv.innerHTML = `
      <div class="text-center py-4">
        <svg class="w-12 h-12 mx-auto text-red-400 dark:text-red-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        <p class="text-slate-900 dark:text-white font-medium mb-2">Error searching for metadata</p>
        <p class="text-sm text-slate-600 dark:text-slate-400">Please try again or enter a URL manually</p>
      </div>
    `;
  }
}

function renderInlineSearchResults(storyId, results, autoMatchUrl = null) {
  if (!results || results.length === 0) return '';
  
  return `
    <div class="space-y-2 mb-4">
      ${results.map(result => `
        <div class="border border-slate-200 dark:border-slate-700 rounded-lg p-3 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-all duration-200 ${result.url === autoMatchUrl ? 'ring-2 ring-green-500 dark:ring-green-600' : ''}">
          <div class="flex items-start justify-between gap-3">
            <div class="flex-1 min-w-0">
              <h4 class="font-medium text-slate-900 dark:text-white text-sm truncate">${escapeHtml(result.title)}</h4>
              <p class="text-xs text-slate-600 dark:text-slate-400 mt-1">by ${escapeHtml(result.author)}</p>
              ${result.category ? `<span class="inline-block mt-1.5 px-2 py-0.5 text-xs font-medium bg-purple-100 dark:bg-purple-900/50 text-purple-800 dark:text-purple-200 rounded">${escapeHtml(result.category)}</span>` : ''}
              <p class="text-xs text-slate-500 dark:text-slate-500 mt-1">Match: ${(result.confidence * 100).toFixed(0)}%</p>
            </div>
            <button onclick="generateHtmlWithUrl(${storyId}, '${escapeHtml(result.url)}', '${result.url === autoMatchUrl ? 'auto' : 'manual'}', this)"
                    class="px-3 py-1.5 text-xs font-medium bg-slate-900 dark:bg-white text-white dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-100 rounded-lg transition-all duration-200 whitespace-nowrap">
              Use This
            </button>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function renderInlineManualUrlInput(storyId) {
  return `
    <div class="border-t border-slate-200 dark:border-slate-700 pt-4 mt-4">
      <label class="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-2">Or enter URL manually:</label>
      <div class="flex gap-2">
        <input type="url" 
               id="inlineManualUrlInput" 
               placeholder="https://www.literotica.com/s/story-title"
               class="flex-1 px-3 py-1.5 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-900 dark:focus:ring-white">
        <button onclick="generateHtmlWithManualUrl(${storyId}, this)"
                class="px-3 py-1.5 text-xs font-medium bg-slate-900 dark:bg-white text-white dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-100 rounded-lg transition-all duration-200">
          Generate
        </button>
      </div>
    </div>
  `;
}

window.generateHtmlWithUrl = async function(storyId, url, method, button) {
  const originalText = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `
    <svg class="w-3 h-3 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
    </svg>
  `;
  
  const contentDiv = document.getElementById('htmlProgressContent');
  if (contentDiv) {
    contentDiv.innerHTML = `
      <div class="flex items-center gap-3 mb-3">
        <svg class="w-5 h-5 animate-spin text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
        </svg>
        <span class="font-medium text-blue-900 dark:text-blue-100">Generating HTML format...</span>
      </div>
      <p class="text-sm text-blue-700 dark:text-blue-300">Downloading story content and updating metadata</p>
    `;
  }
  
  try {
    const response = await fetch(`/api/format/generate-html-with-metadata/${storyId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'HX-Request': 'true'
      },
      body: JSON.stringify({ url, method })
    });
    
    const result = await response.json();
    
    if (result.success) {
      if (contentDiv) {
        contentDiv.innerHTML = `
          <div class="flex items-center gap-3 mb-3">
            <svg class="w-5 h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
            </svg>
            <span class="font-medium text-green-900 dark:text-green-100">HTML format created successfully!</span>
          </div>
          <p class="text-sm text-green-700 dark:text-green-300">Updating modal...</p>
        `;
      }
      
      setTimeout(() => {
        if (result.story) {
          updateModalContentInPlace(result.story);
        } else {
          window.location.reload();
        }
      }, 800);
    } else {
      throw new Error(result.message || 'Failed to generate HTML');
    }
  } catch (error) {
    console.error('HTML generation error:', error);
    if (contentDiv) {
      contentDiv.innerHTML = `
        <div class="flex items-center gap-3 mb-3">
          <svg class="w-5 h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
          </svg>
          <span class="font-medium text-red-900 dark:text-red-100">Failed to generate HTML format</span>
        </div>
        <p class="text-sm text-red-700 dark:text-red-300">${error.message}</p>
      `;
    }
    button.innerHTML = originalText;
    button.disabled = false;
  }
};

window.generateHtmlWithManualUrl = function(storyId, button) {
  const input = document.getElementById('inlineManualUrlInput');
  const url = input.value.trim();
  
  if (!url) {
    alert('Please enter a URL');
    return;
  }
  
  if (!url.includes('literotica.com')) {
    alert('Please enter a valid Literotica URL');
    return;
  }
  
  generateHtmlWithUrl(storyId, url, 'manual', button);
};

function updateModalContentInPlace(story) {
  const progressSection = document.getElementById('htmlProgressSection');
  if (progressSection) {
    progressSection.style.opacity = '0';
    progressSection.style.transition = 'opacity 0.3s ease-out';
    setTimeout(() => progressSection.remove(), 300);
  }
  
  const hasHtml = story.formats.includes('html') || story.formats.includes('json');
  const hasEpub = story.formats.includes('epub');
  
  const modal = document.getElementById('storyModal');
  if (!modal) {
    console.error('Modal not found');
    return;
  }
  
  const formatBadgesContainer = modal.querySelector('.flex.flex-wrap.gap-2.mb-4');
  if (formatBadgesContainer && hasHtml) {
    const badges = Array.from(formatBadgesContainer.querySelectorAll('span'));
    const htmlBadgeExists = badges.some(badge => badge.textContent.includes('HTML'));
    
    if (!htmlBadgeExists) {
      const epubBadge = badges.find(badge => badge.textContent.includes('EPUB'));
      if (epubBadge) {
        epubBadge.insertAdjacentHTML('afterend', '<span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-200 rounded">HTML</span>');
      } else {
        formatBadgesContainer.insertAdjacentHTML('afterbegin', '<span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-200 rounded">HTML</span>');
      }
    }
  }
  
  const actionsContainer = modal.querySelector('.flex.flex-col.gap-6.mt-6');
  if (!actionsContainer) {
    console.error('Actions container not found');
    return;
  }
  
  const buttonsContainer = actionsContainer.querySelector('.flex.flex-col.gap-3');
  if (buttonsContainer && hasHtml) {
    const existingHtmlButtons = Array.from(buttonsContainer.querySelectorAll('a')).some(a => 
      a.href && a.href.includes('/read/')
    );
    
    if (!existingHtmlButtons) {
      const htmlButtons = `
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
      `;
      
      buttonsContainer.insertAdjacentHTML('afterbegin', htmlButtons);
    }
  }
  
  const secondaryActionsContainer = actionsContainer.querySelector('.flex.flex-wrap.gap-2');
  if (secondaryActionsContainer && hasHtml) {
    const buttons = Array.from(secondaryActionsContainer.querySelectorAll('button'));
    const addHtmlButton = buttons.find(btn => btn.textContent.includes('Add HTML'));
    
    if (addHtmlButton) {
      addHtmlButton.remove();
    }
    
    const syncButtonExists = buttons.some(btn => btn.textContent.includes('Sync for Offline'));
    
    if (!syncButtonExists) {
      const syncButton = `
        <button onclick="syncStoryFromModal('${story.html_file}', this)"
                class="px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700/50 rounded-md border border-slate-200/60 dark:border-slate-700 transition-all duration-200 inline-flex items-center gap-1.5"
                title="Cache for offline reading">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
          </svg>
          Sync for Offline
        </button>
      `;
      
      secondaryActionsContainer.insertAdjacentHTML('afterbegin', syncButton);
    }
  }
  
  showFormatSuccessToast('HTML format created successfully!');
}

function updateModalWithNewStory(story) {
  closeStoryModal();
  setTimeout(() => {
    showStoryModal(story);
  }, 100);
}

function showFormatSuccessToast(message) {
  showToast(message, 'success');
}

function showFormatErrorToast(message) {
  showToast(message, 'error');
}

function showToast(message, type = 'info') {
  const existingToast = document.getElementById('formatToast');
  if (existingToast) {
    existingToast.remove();
  }

  const colors = {
    info: 'bg-blue-500',
    success: 'bg-green-500',
    error: 'bg-red-500'
  };

  const toast = document.createElement('div');
  toast.id = 'formatToast';
  toast.className = `fixed bottom-4 right-4 ${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg z-[70] transition-opacity duration-300`;
  toast.textContent = message;

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

window.confirmDeleteStory = function(storyId, storyTitle) {
  const confirmationHtml = `
    <div id="deleteConfirmationModal" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm transition-opacity duration-200" onclick="closeDeleteConfirmation(event)">
      <div class="w-full max-w-md mx-4 bg-white dark:bg-gray-800 rounded-xl shadow-2xl transform transition-all" onclick="event.stopPropagation()">
        <div class="p-6">
          <div class="flex items-center gap-3 mb-4">
            <div class="flex-shrink-0 w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
              <svg class="w-6 h-6 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
              </svg>
            </div>
            <div class="flex-1">
              <h3 class="text-lg font-semibold text-gray-900 dark:text-white">Delete Story</h3>
              <p class="text-sm text-gray-500 dark:text-gray-400">This action cannot be undone</p>
            </div>
          </div>
          
          <p class="text-sm text-gray-700 dark:text-gray-300 mb-6">
            Are you sure you want to delete <strong class="font-semibold">"${escapeHtml(storyTitle)}"</strong>? This will permanently remove the story and all its files from your library.
          </p>
          
          <div class="flex gap-3">
            <button onclick="closeDeleteConfirmation()"
                    class="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 border border-gray-300 dark:border-gray-600 rounded-lg transition-all duration-200">
              Cancel
            </button>
            <button onclick="deleteStory(${storyId}, '${escapeHtml(storyTitle).replace(/'/g, "\\'")}')"
                    class="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-red-600 hover:bg-red-700 dark:bg-red-600 dark:hover:bg-red-700 rounded-lg transition-all duration-200">
              Delete Story
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', confirmationHtml);
  
  setTimeout(() => {
    const modal = document.getElementById('deleteConfirmationModal');
    if (modal) {
      modal.classList.add('active');
    }
  }, 10);
};

window.closeDeleteConfirmation = function(event) {
  if (event && event.target !== event.currentTarget) {
    return;
  }
  
  const modal = document.getElementById('deleteConfirmationModal');
  if (modal) {
    modal.classList.add('opacity-0');
    setTimeout(() => {
      modal.remove();
    }, 200);
  }
};

window.deleteStory = async function(storyId, storyTitle) {
  closeDeleteConfirmation();
  
  const modal = document.getElementById('storyModal');
  if (modal) {
    const modalContent = modal.querySelector('.p-6.md\\:p-8');
    if (modalContent) {
      const loadingOverlay = document.createElement('div');
      loadingOverlay.id = 'deleteLoadingOverlay';
      loadingOverlay.className = 'absolute inset-0 bg-white/90 dark:bg-gray-800/90 flex items-center justify-center z-10 rounded-xl';
      loadingOverlay.innerHTML = `
        <div class="text-center">
          <svg class="w-12 h-12 mx-auto mb-3 text-red-600 dark:text-red-400 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
          </svg>
          <p class="text-gray-900 dark:text-white font-medium">Deleting story...</p>
        </div>
      `;
      modal.querySelector('div > div').appendChild(loadingOverlay);
    }
  }
  
  try {
    const response = await fetch(`/api/story/delete/${storyId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    const result = await response.json();
    
    if (result.success) {
      showToast(`"${storyTitle}" deleted successfully`, 'success');
      closeStoryModal();
      
      removeStoryFromDOM(storyId);
      
      checkIfLibraryEmpty();
    } else {
      throw new Error(result.message || 'Failed to delete story');
    }
  } catch (error) {
    console.error('Delete error:', error);
    showToast('Failed to delete story', 'error');
    
    const loadingOverlay = document.getElementById('deleteLoadingOverlay');
    if (loadingOverlay) {
      loadingOverlay.remove();
    }
  }
};

function removeStoryFromDOM(storyId) {
  const storyCards = document.querySelectorAll('.story-card-cover');
  
  storyCards.forEach(card => {
    try {
      const storyData = card.getAttribute('data-story');
      const story = JSON.parse(storyData);
      
      if (story.id === storyId) {
        card.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
        card.style.opacity = '0';
        card.style.transform = 'scale(0.95)';
        
        setTimeout(() => {
          card.remove();
        }, 300);
      }
    } catch (error) {
      console.error('Error parsing story data:', error);
    }
  });
}

function checkIfLibraryEmpty() {
  setTimeout(() => {
    const remainingCards = document.querySelectorAll('.story-card-cover');

    if (remainingCards.length === 0) {
      const libraryContainer = document.querySelector('#library-grid, .grid');

      if (libraryContainer) {
        libraryContainer.innerHTML = `
          <div class="col-span-full text-center text-gray-500 dark:text-gray-400 py-12">
            <svg class="w-20 h-20 mx-auto mb-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
            </svg>
            <p class="text-lg font-medium">No stories in your library</p>
            <p class="text-sm mt-1">Download a story to get started</p>
          </div>
        `;
      }
    }
  }, 400);
}

window.toggleAutoUpdate = async function(storyId, _currentState, button) {
  const originalText = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `
    <svg class="w-3.5 h-3.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
    </svg>
    Updating...
  `;

  try {
    const response = await fetch(`/api/story/toggle-auto-update/${storyId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    const result = await response.json();

    if (result.success) {
      const newState = result.auto_update_enabled;
      const newClass = newState
        ? 'px-3 py-1.5 text-xs font-medium text-green-600 dark:text-green-400 hover:text-green-700 dark:hover:text-green-300 hover:bg-green-50 dark:hover:bg-green-900/20 border-green-200/60 dark:border-green-700 rounded-md border transition-all duration-200 inline-flex items-center gap-1.5'
        : 'px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700/50 border-slate-200/60 dark:border-slate-700 rounded-md border transition-all duration-200 inline-flex items-center gap-1.5';

      button.className = newClass;
      button.title = newState ? 'Disable automatic updates' : 'Enable automatic updates';
      button.setAttribute('onclick', `toggleAutoUpdate(${storyId}, ${newState}, this)`);
      button.innerHTML = `
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
        </svg>
        Auto-Update: ${newState ? 'ON' : 'OFF'}
      `;
      button.disabled = false;

      showToast(result.message, 'success');
    } else {
      throw new Error(result.message || 'Failed to toggle auto-update');
    }
  } catch (error) {
    console.error('Auto-update toggle error:', error);
    showToast('Failed to toggle auto-update', 'error');
    button.innerHTML = originalText;
    button.disabled = false;
  }
};
