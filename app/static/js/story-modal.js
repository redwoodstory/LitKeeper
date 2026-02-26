function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

async function invalidateLibraryCache() {
  if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
    try {
      const messageChannel = new MessageChannel();
      const promise = new Promise((resolve) => {
        messageChannel.port1.onmessage = (event) => {
          resolve(event.data);
        };
      });
      navigator.serviceWorker.controller.postMessage(
        { type: 'INVALIDATE_LIBRARY_CACHE' },
        [messageChannel.port2]
      );
      await promise;
      console.log('[Cache] Library cache invalidated');
    } catch (error) {
      console.error('[Cache] Failed to invalidate cache:', error);
    }
  }
}

function refreshLibrary() {
  const searchInput = document.getElementById('searchInput');
  const categoryFilter = document.getElementById('categoryFilter');
  const sortBy = document.getElementById('sortBy');
  const sortOrderToggle = document.getElementById('sortOrderToggle');
  
  if (searchInput) {
    htmx.trigger(searchInput, 'keyup');
  } else {
    const libraryContent = document.getElementById('library-content');
    if (libraryContent) {
      const params = new URLSearchParams();
      if (categoryFilter) params.append('category', categoryFilter.value);
      if (sortBy) params.append('sort_by', sortBy.value);
      if (sortOrderToggle) params.append('sort_order', sortOrderToggle.value);
      
      fetch(`/library/filter?${params.toString()}`)
        .then(response => response.text())
        .then(html => {
          libraryContent.outerHTML = html;
          const newLibraryContent = document.getElementById('library-content');
          if (newLibraryContent) {
            htmx.process(newLibraryContent);
          }
        })
        .catch(error => {
          console.error('[Library] Failed to refresh:', error);
        });
    }
  }
}

document.addEventListener('click', function(e) {
  const editMetadataBtn = e.target.closest('.edit-metadata-btn');
  if (editMetadataBtn) {
    e.preventDefault();
    e.stopPropagation();
    
    const storyId = parseInt(editMetadataBtn.dataset.storyId);
    const title = editMetadataBtn.dataset.storyTitle;
    const author = editMetadataBtn.dataset.storyAuthor;
    const category = editMetadataBtn.dataset.storyCategory;
    
    let tags = [];
    try {
      const tagsData = editMetadataBtn.dataset.storyTags;
      if (tagsData && tagsData.trim() !== '') {
        tags = JSON.parse(tagsData);
      }
    } catch (e) {
      console.error('Error parsing tags:', e);
      tags = [];
    }
    
    openEditMetadataModal(storyId, title, author, category, tags);
  }
}, true);

window.syncStory = async function(filename, button) {
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
        <div class="mb-4 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg">
          <div class="flex items-start gap-3">
            <svg class="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p class="text-sm font-medium text-amber-900 dark:text-amber-200">No matches found</p>
              <p class="text-xs text-amber-700 dark:text-amber-300 mt-1">${data.message}. Enter a Literotica URL below to continue.</p>
            </div>
          </div>
        </div>
        ${renderInlineManualUrlInput(storyId)}
      `;
      return;
    }
    
    contentDiv.innerHTML = `
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
    <div class="mb-4">
      <p class="text-base font-medium text-slate-900 dark:text-white mb-2">Select the matching story</p>
      <p class="text-sm text-slate-600 dark:text-slate-400 mb-4">Choose the best match to generate HTML format or enter a URL manually below</p>
    </div>
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

window.closeStoryModal = function() {
  const modal = document.getElementById('storyModal');
  if (modal) {
    modal.remove();
    document.body.style.overflow = '';
  }
};

async function updateModalWithNewStory(story) {
  closeStoryModal();
  await invalidateLibraryCache();
  setTimeout(() => {
    refreshLibrary();
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
      
      const storyCards = document.querySelectorAll('[hx-get*="/api/story/' + storyId + '/modal"]');
      storyCards.forEach(card => {
        card.style.transition = 'opacity 200ms, transform 200ms';
        card.style.opacity = '0';
        card.style.transform = 'scale(0.95)';
        setTimeout(() => card.remove(), 200);
      });
      
      document.dispatchEvent(new CustomEvent('storyDeleted', { 
        detail: { storyId: storyId } 
      }));
      
      await invalidateLibraryCache();
      
      setTimeout(() => {
        refreshLibrary();
      }, 300);
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



window.openEditMetadataModal = function(storyId, currentTitle, currentAuthor, currentCategory, currentTags) {
  const tagsArray = Array.isArray(currentTags) ? currentTags : [];
  const tagsString = tagsArray.join(', ');

  const editModalHtml = `
    <div id="editMetadataModal" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm transition-opacity duration-200" onclick="closeEditMetadataModal(event)">
      <div class="w-full max-w-2xl mx-4 bg-white dark:bg-gray-800 rounded-xl shadow-2xl transform transition-all" onclick="event.stopPropagation()">
        <div class="p-6">
          <div class="flex items-center justify-between mb-6">
            <h3 class="text-xl font-semibold text-gray-900 dark:text-white">Edit Story Metadata</h3>
            <button onclick="closeEditMetadataModal()" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>

          <form id="editMetadataForm" class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Title</label>
              <input type="text" id="editTitle" value="${escapeHtml(currentTitle)}"
                     class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-slate-900 dark:focus:ring-white focus:border-transparent">
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Author</label>
              <input type="text" id="editAuthor" value="${escapeHtml(currentAuthor)}"
                     class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-slate-900 dark:focus:ring-white focus:border-transparent">
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Category</label>
              <input type="text" id="editCategory" value="${escapeHtml(currentCategory)}"
                     class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-slate-900 dark:focus:ring-white focus:border-transparent">
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Tags (comma-separated)</label>
              <input type="text" id="editTags" value="${escapeHtml(tagsString)}"
                     class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-slate-900 dark:focus:ring-white focus:border-transparent"
                     placeholder="tag1, tag2, tag3">
            </div>

            <div class="flex gap-3 pt-4">
              <button type="button" onclick="closeEditMetadataModal()"
                      class="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 border border-gray-300 dark:border-gray-600 rounded-lg transition-all duration-200">
                Cancel
              </button>
              <button type="submit"
                      class="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-slate-900 dark:bg-white dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-100 rounded-lg transition-all duration-200">
                Save Changes
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', editModalHtml);

  document.getElementById('editMetadataForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    await saveMetadataChanges(storyId);
  });
};

window.closeEditMetadataModal = function(event) {
  if (event && event.target !== event.currentTarget) {
    return;
  }

  const modal = document.getElementById('editMetadataModal');
  if (modal) {
    modal.remove();
  }
};

async function saveMetadataChanges(storyId) {
  const title = document.getElementById('editTitle').value.trim();
  const author = document.getElementById('editAuthor').value.trim();
  const category = document.getElementById('editCategory').value.trim();
  const tagsInput = document.getElementById('editTags').value.trim();
  const tags = tagsInput ? tagsInput.split(',').map(t => t.trim()).filter(t => t) : [];

  try {
    const response = await fetch(`/api/story/${storyId}/metadata`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'HX-Request': 'true'
      },
      body: JSON.stringify({ title, author, category, tags })
    });

    const result = await response.json();

    if (result.success) {
      closeEditMetadataModal();
      
      if (result.cover_regenerated) {
        const timestamp = new Date().getTime();
        const modal = document.getElementById('storyModal');
        if (modal) {
          try {
            const modalResponse = await fetch(`/api/story/${storyId}/modal?t=${timestamp}`);
            if (modalResponse.ok) {
              const modalHtml = await modalResponse.text();
              modal.outerHTML = modalHtml;
              
              const newModal = document.getElementById('storyModal');
              if (newModal && result.cover_filename) {
                const coverImg = newModal.querySelector('img[alt*="cover"]');
                if (coverImg) {
                  const coverSrc = coverImg.src.split('?')[0];
                  coverImg.src = `${coverSrc}?t=${timestamp}`;
                }
              }
            }
          } catch (modalError) {
            console.error('Error refreshing modal:', modalError);
          }
        }
        
        if (result.cover_filename) {
          htmx.trigger(document.body, 'coverRegenerated', { 
            storyId: storyId, 
            coverFilename: result.cover_filename 
          });
        }
        
        showToast('Metadata updated successfully', 'success');
      } else {
        showToast('Metadata updated successfully', 'success');
        closeStoryModal();
        
        const storyCards = document.querySelectorAll('[hx-get*="/api/story/' + storyId + '/modal"]');
        storyCards.forEach(card => {
          card.style.transition = 'opacity 200ms';
          card.style.opacity = '0.5';
        });
        
        setTimeout(async () => {
          try {
            const response = await fetch(`/api/story/${storyId}/card`);
            if (response.ok) {
              const newCardHtml = await response.text();
              storyCards.forEach(card => {
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = newCardHtml;
                const newCard = tempDiv.firstElementChild;
                
                newCard.style.opacity = '0';
                card.parentNode.replaceChild(newCard, card);
                
                setTimeout(() => {
                  newCard.style.transition = 'opacity 300ms';
                  newCard.style.opacity = '1';
                }, 10);
              });
            }
          } catch (error) {
            console.error('Failed to update story card:', error);
          }
          
          if (typeof refreshLibrary === 'function') {
            refreshLibrary();
          } else {
            window.location.reload();
          }
        }, 200);
      }
    } else {
      showToast(result.message || 'Failed to update metadata', 'error');
    }
  } catch (error) {
    console.error('Error updating metadata:', error);
    showToast('An error occurred while updating metadata', 'error');
  }
}

document.body.addEventListener('coverRegenerated', function(evt) {
  const { storyId, coverFilename } = evt.detail;
  const timestamp = new Date().getTime();
  
  const libraryCovers = document.querySelectorAll(`img[src*="${coverFilename}"]`);
  libraryCovers.forEach(img => {
    if (!img.closest('#storyModal')) {
      const currentSrc = img.src.split('?')[0];
      img.src = `${currentSrc}?t=${timestamp}`;
    }
  });
});

