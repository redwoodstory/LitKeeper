const metadataModal = new MetadataModal();

function initializeLibraryFilters() {
  const sortBy = document.getElementById('sortBy');
  const categoryFilter = document.getElementById('categoryFilter');
  const sourceFilter = document.getElementById('sourceFilter');
  const sortOrderToggle = document.getElementById('sortOrderToggle');

  const savedSortBy = localStorage.getItem('library_sort_by') || 'date';
  const savedCategory = localStorage.getItem('library_category') || 'all';
  const savedSource = localStorage.getItem('library_source') || 'all';
  const savedSortOrder = localStorage.getItem('library_sort_order') || 'desc';

  if (sortBy) {
    sortBy.value = savedSortBy;
  }
  if (categoryFilter) {
    categoryFilter.value = savedCategory;
  }
  if (sourceFilter) {
    sourceFilter.value = savedSource;
  }
  if (sortOrderToggle) {
    sortOrderToggle.value = savedSortOrder;
    updateSortOrderIcon(sortOrderToggle, savedSortOrder);
  }

  const hasSavedPreferences = localStorage.getItem('library_sort_by') ||
                               localStorage.getItem('library_category') ||
                               localStorage.getItem('library_source') ||
                               localStorage.getItem('library_sort_order');
  
  if (hasSavedPreferences) {
    document.body.addEventListener('htmx:afterSwap', function onSwap(e) {
      if (e.detail.target.id === 'library-content') {
        e.detail.target.style.visibility = '';
        document.body.removeEventListener('htmx:afterSwap', onSwap);
      }
    });
    triggerLibraryFilter();
  }
}

function updateSortOrderIcon(button, order) {
  const svg = button.querySelector('svg path');
  const label = button.querySelector('#sortOrderLabel');
  if (order === 'asc') {
    svg.setAttribute('d', 'M5 15l7-7 7 7');
    button.setAttribute('title', 'Ascending order');
    if (label) label.textContent = 'Ascending';
  } else {
    svg.setAttribute('d', 'M19 9l-7 7-7-7');
    button.setAttribute('title', 'Descending order');
    if (label) label.textContent = 'Descending';
  }
}

function triggerLibraryFilter() {
  const sortBy = document.getElementById('sortBy');
  if (sortBy) {
    htmx.trigger(sortBy, 'change');
  }
}

const sortOrderToggle = document.getElementById('sortOrderToggle');
if (sortOrderToggle) {
  let pendingOrder = null;
  
  sortOrderToggle.addEventListener('click', function(e) {
    const currentOrder = this.value;
    const newOrder = currentOrder === 'desc' ? 'asc' : 'desc';
    pendingOrder = newOrder;
    this.value = newOrder;
    localStorage.setItem('library_sort_order', newOrder);
    updateSortOrderIcon(this, newOrder);
  });
  
  sortOrderToggle.addEventListener('htmx:configRequest', function(e) {
    if (pendingOrder) {
      e.detail.parameters.sort_order = pendingOrder;
      pendingOrder = null;
    }
  });
}

const sortBy = document.getElementById('sortBy');
if (sortBy) {
  sortBy.addEventListener('change', function() {
    localStorage.setItem('library_sort_by', this.value);
  });
}

const categoryFilter = document.getElementById('categoryFilter');
if (categoryFilter) {
  categoryFilter.addEventListener('change', function() {
    localStorage.setItem('library_category', this.value);
  });
}

const sourceFilter = document.getElementById('sourceFilter');
if (sourceFilter) {
  sourceFilter.addEventListener('change', function() {
    localStorage.setItem('library_source', this.value);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initializeLibraryFilters();
});

window.addEventListener('pageshow', (e) => {
  if (e.persisted && sessionStorage.getItem('litkeeper_reload')) {
    sessionStorage.removeItem('litkeeper_reload');
    window.location.reload();
  }
});
