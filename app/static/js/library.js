const form = document.getElementById('downloadForm');
const submitBtn = form.querySelector('button[type="submit"]');
const loading = document.getElementById('loading');
const result = document.getElementById('result');
const formatError = document.getElementById('formatError');

const metadataModal = new MetadataModal();

function refreshLibrary() {
  const libraryElement = document.getElementById('library');
  const categoryFilter = document.getElementById('categoryFilter');
  const searchInput = document.querySelector('input[name="search"]');

  if (libraryElement && window.htmx) {
    const category = categoryFilter ? categoryFilter.value : 'all';
    const search = searchInput ? searchInput.value : '';

    htmx.ajax('GET', `/library/filter?category=${category}&search=${encodeURIComponent(search)}`, {
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

  result.style.display = 'none';
  result.className = 'hidden mt-4 p-4 rounded-lg';
  loading.classList.remove('hidden');
  submitBtn.disabled = true;

  try {
    const formData = new FormData(form);
    const url = formData.get('url');
    const formats = Array.from(formatCheckboxes).map(cb => cb.value);

    const response = await fetch('/api/preview', {
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
      loading.classList.add('hidden');
      submitBtn.disabled = false;

      metadataModal.show(data.metadata, saveStoryWithMetadata);
    } else {
      result.classList.remove('hidden');
      result.classList.add('bg-red-100', 'dark:bg-red-900', 'text-red-800', 'dark:text-red-200', 'border', 'border-red-200', 'dark:border-red-800');
      result.textContent = data.message;
      loading.classList.add('hidden');
      submitBtn.disabled = false;
    }
  } catch (error) {
    result.classList.remove('hidden');
    result.classList.add('bg-red-100', 'dark:bg-red-900', 'text-red-800', 'dark:text-red-200', 'border', 'border-red-200', 'dark:border-red-800');
    result.textContent = 'An error occurred while processing your request.';
    loading.classList.add('hidden');
    submitBtn.disabled = false;
  }
});
