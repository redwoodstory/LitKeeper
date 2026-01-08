const metadataModal = new MetadataModal();

function initializeLibraryFilters() {
  const sortBy = document.getElementById('sortBy');
  const categoryFilter = document.getElementById('categoryFilter');
  const sortOrderToggle = document.getElementById('sortOrderToggle');

  const savedSortBy = localStorage.getItem('library_sort_by') || 'date';
  const savedCategory = localStorage.getItem('library_category') || 'all';
  const savedSortOrder = localStorage.getItem('library_sort_order') || 'desc';

  if (sortBy) {
    sortBy.value = savedSortBy;
  }
  if (categoryFilter) {
    categoryFilter.value = savedCategory;
  }
  if (sortOrderToggle) {
    sortOrderToggle.value = savedSortOrder;
    updateSortOrderIcon(sortOrderToggle, savedSortOrder);
  }

  const hasSavedPreferences = localStorage.getItem('library_sort_by') || 
                               localStorage.getItem('library_category') || 
                               localStorage.getItem('library_sort_order');
  
  if (hasSavedPreferences) {
    triggerLibraryFilter();
  }
}

function updateSortOrderIcon(button, order) {
  const svg = button.querySelector('svg path');
  if (order === 'asc') {
    svg.setAttribute('d', 'M5 15l7-7 7 7');
    button.setAttribute('title', 'Ascending order');
  } else {
    svg.setAttribute('d', 'M19 9l-7 7-7-7');
    button.setAttribute('title', 'Descending order');
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

document.addEventListener('DOMContentLoaded', initializeLibraryFilters);
