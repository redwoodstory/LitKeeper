const form = document.getElementById('downloadForm');
const submitBtn = form.querySelector('button[type="submit"]');
const loading = document.getElementById('loading');
const result = document.getElementById('result');
const formatError = document.getElementById('formatError');

const metadataModal = new MetadataModal();

let activeQueuePolling = new Set();

async function checkActiveQueue() {
  try {
    const response = await fetch('/api/queue');
    const data = await response.json();
    
    if (data.success && data.queue && data.queue.length > 0) {
      data.queue.forEach(item => {
        if (!activeQueuePolling.has(item.id)) {
          pollQueueStatus(item.id);
        }
      });
    }
  } catch (error) {
    console.error('Error checking active queue:', error);
  }
}

document.addEventListener('visibilitychange', function() {
  if (!document.hidden) {
    checkActiveQueue();
    
    if (activeQueuePolling.size > 0) {
      activeQueuePolling.forEach(queueId => {
        pollQueueStatus(queueId);
      });
    }
  }
});

checkActiveQueue();

function pollQueueStatus(queueId) {
  activeQueuePolling.add(queueId);
  
  const checkStatus = async () => {
    if (document.hidden) {
      return;
    }
    
    try {
      const response = await fetch(`/api/queue/${queueId}`);
      const data = await response.json();

      if (!data.success) {
        activeQueuePolling.delete(queueId);
        return;
      }

      const queueItem = data.queue_item;
      const result = document.getElementById('result');

      if (queueItem.status === 'processing') {
        const progressMsg = queueItem.progress_message || 'Downloading...';
        const storyInfo = queueItem.title && queueItem.author 
          ? `<p class="text-sm mt-1">${queueItem.title} by ${queueItem.author}</p>`
          : '';
        result.innerHTML = `
          <div class="flex items-start gap-3">
            <svg class="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
            <div class="flex-1">
              <p class="font-medium">${progressMsg}</p>
              ${storyInfo}
            </div>
          </div>
        `;
        setTimeout(checkStatus, 2000);
      } else if (queueItem.status === 'completed') {
        activeQueuePolling.delete(queueId);
        
        result.className = 'mt-4 p-4 rounded-lg bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 border border-green-200 dark:border-green-800';
        result.innerHTML = `
          <div class="flex items-start gap-3">
            <svg class="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
            </svg>
            <div class="flex-1">
              <p class="font-medium">Download complete!</p>
              <p class="text-sm mt-1">"${queueItem.title || 'Story'}" has been added to your library.</p>
            </div>
            <button onclick="this.closest('.p-4').classList.add('hidden')" class="text-green-600 dark:text-green-400 hover:text-green-800 dark:hover:text-green-200">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>
        `;
        
        setTimeout(() => {
          refreshLibrary();
        }, 1000);
        
        setTimeout(() => {
          result.classList.add('hidden');
        }, 5000);
      } else if (queueItem.status === 'failed') {
        activeQueuePolling.delete(queueId);
        
        result.className = 'mt-4 p-4 rounded-lg bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800';
        result.innerHTML = `
          <div class="flex items-start gap-3">
            <svg class="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
            <div class="flex-1">
              <p class="font-medium">Download failed</p>
              <p class="text-sm mt-1">${queueItem.error_message || 'An error occurred'}</p>
            </div>
            <button onclick="this.closest('.p-4').classList.add('hidden')" class="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-200">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>
        `;
      } else if (queueItem.status === 'pending') {
        setTimeout(checkStatus, 2000);
      }
    } catch (error) {
      console.error('Error polling queue status:', error);
      activeQueuePolling.delete(queueId);
    }
  };

  checkStatus();
}

function showDownloadCompleteToast(storyTitle) {
  const existingToast = document.getElementById('downloadCompleteToast');
  if (existingToast) {
    existingToast.remove();
  }

  const toast = document.createElement('div');
  toast.id = 'downloadCompleteToast';
  toast.className = 'fixed bottom-4 right-4 bg-green-500 text-white px-6 py-4 rounded-lg shadow-lg z-[70] transition-all duration-300 max-w-md';
  toast.innerHTML = `
    <div class="flex items-start gap-3">
      <svg class="w-6 h-6 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
      </svg>
      <div class="flex-1">
        <p class="font-semibold">Story Downloaded!</p>
        <p class="text-sm mt-1 opacity-90">"${storyTitle}" is now in your library</p>
      </div>
      <button onclick="this.closest('#downloadCompleteToast').remove()" class="text-white hover:text-green-100 transition-colors">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
      </button>
    </div>
  `;

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 5000);
}

const sortOrderToggle = document.getElementById('sortOrderToggle');
if (sortOrderToggle) {
  sortOrderToggle.addEventListener('click', function() {
    const currentOrder = this.value;
    const newOrder = currentOrder === 'desc' ? 'asc' : 'desc';
    this.value = newOrder;

    const svg = this.querySelector('svg path');
    if (newOrder === 'asc') {
      svg.setAttribute('d', 'M5 15l7-7 7 7');
      this.setAttribute('title', 'Ascending order');
    } else {
      svg.setAttribute('d', 'M19 9l-7 7-7-7');
      this.setAttribute('title', 'Descending order');
    }
  });
}

function refreshLibrary() {
  const libraryElement = document.getElementById('library');
  const categoryFilter = document.getElementById('categoryFilter');
  const searchInput = document.querySelector('input[name="search"]');
  const sortBySelect = document.getElementById('sortBy');
  const sortOrderToggle = document.getElementById('sortOrderToggle');

  if (libraryElement && window.htmx) {
    const category = categoryFilter ? categoryFilter.value : 'all';
    const search = searchInput ? searchInput.value : '';
    const sortBy = sortBySelect ? sortBySelect.value : 'date';
    const sortOrder = sortOrderToggle ? sortOrderToggle.value : 'desc';

    htmx.ajax('GET', `/library/filter?category=${category}&search=${encodeURIComponent(search)}&sort_by=${sortBy}&sort_order=${sortOrder}`, {
      target: '#library',
      swap: 'innerHTML'
    }).then(() => {
      fetch('/api/library')
        .then(r => r.json())
        .then(data => {
          const count = data.stories.length;
          const countElement = document.getElementById('libraryCount');
          if (countElement) {
            countElement.textContent = count === 0 ? 'No stories yet' :
              count === 1 ? '1 story' : `${count} stories`;
          }

          const categories = new Set();
          data.stories.forEach(story => {
            if (story.category) {
              categories.add(story.category);
            }
          });

          if (categoryFilter && categories.size > 0) {
            const currentValue = categoryFilter.value;
            const sortedCategories = Array.from(categories).sort();

            const existingCategories = Array.from(categoryFilter.querySelectorAll('option'))
              .filter(opt => opt.value !== 'all' && opt.value !== 'uncategorized')
              .map(opt => opt.value);

            const needsUpdate = sortedCategories.length !== existingCategories.length ||
              !sortedCategories.every((cat, i) => cat === existingCategories[i]);

            if (needsUpdate) {
              const optionsToKeep = categoryFilter.querySelectorAll('option[value="all"], option[value="uncategorized"]');
              categoryFilter.innerHTML = '';
              optionsToKeep.forEach(opt => categoryFilter.appendChild(opt));

              sortedCategories.forEach(cat => {
                const option = document.createElement('option');
                option.value = cat;
                option.textContent = cat;
                categoryFilter.appendChild(option);
              });

              categoryFilter.value = currentValue;
            }
          }
        });
    });
  } else {
    window.location.reload(true);
  }
}

async function saveStoryWithMetadata(metadata) {
  const response = await fetch('/api/save', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(metadata)
  });

  const data = await response.json();

  result.classList.remove('hidden');
  if (data.success === "true") {
    result.classList.add('bg-green-100', 'dark:bg-green-900', 'text-green-800', 'dark:text-green-200', 'border', 'border-green-200', 'dark:border-green-800');
    result.textContent = data.message;

    form.reset();
    form.querySelectorAll('input[name="format"]').forEach(cb => cb.checked = true);

    setTimeout(() => {
      refreshLibrary();
    }, 1000);
  } else {
    result.classList.add('bg-red-100', 'dark:bg-red-900', 'text-red-800', 'dark:text-red-200', 'border', 'border-red-200', 'dark:border-red-800');
    result.textContent = data.message;
  }

  loading.classList.add('hidden');
  submitBtn.disabled = false;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const formatCheckboxes = form.querySelectorAll('input[name="format"]:checked');
  if (formatCheckboxes.length === 0) {
    formatError.classList.remove('hidden');
    return;
  }
  formatError.classList.add('hidden');

  result.classList.add('hidden');
  result.className = 'hidden mt-4 p-4 rounded-lg';
  loading.classList.remove('hidden');
  submitBtn.disabled = true;

  try {
    const formData = new FormData(form);
    const url = formData.get('url');
    const formats = Array.from(formatCheckboxes).map(cb => cb.value);

    const response = await fetch('/api/queue', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        url: url,
        format: formats
      })
    });

    const data = await response.json();

    if (data.success) {
      result.classList.remove('hidden');
      result.classList.add('bg-green-100', 'dark:bg-green-900', 'text-green-800', 'dark:text-green-200', 'border', 'border-green-200', 'dark:border-green-800');

      const queueInfo = data.queue_item;
      result.innerHTML = `
        <div class="flex items-start gap-3">
          <svg class="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
          </svg>
          <div class="flex-1">
            <p class="font-medium">Download queued successfully!</p>
            <p class="text-sm mt-1">Your story is downloading in the background. You'll see it appear in your library when it's ready.</p>
            ${queueInfo.queue_position > 1 ? `<p class="text-xs mt-2 opacity-75">Position in queue: ${queueInfo.queue_position}</p>` : ''}
          </div>
          <button onclick="this.closest('.p-4').classList.add('hidden')" class="text-green-600 dark:text-green-400 hover:text-green-800 dark:hover:text-green-200">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>
      `;

      form.reset();
      form.querySelectorAll('input[name="format"]').forEach(cb => cb.checked = true);

      pollQueueStatus(queueInfo.id);
    } else {
      result.classList.remove('hidden');
      result.classList.add('bg-red-100', 'dark:bg-red-900', 'text-red-800', 'dark:text-red-200', 'border', 'border-red-200', 'dark:border-red-800');
      result.textContent = data.message;
    }

    loading.classList.add('hidden');
    submitBtn.disabled = false;

  } catch (error) {
    result.classList.remove('hidden');
    result.classList.add('bg-red-100', 'dark:bg-red-900', 'text-red-800', 'dark:text-red-200', 'border', 'border-red-200', 'dark:border-red-800');
    result.textContent = 'An error occurred while processing your request.';
    loading.classList.add('hidden');
    submitBtn.disabled = false;
  }
});
