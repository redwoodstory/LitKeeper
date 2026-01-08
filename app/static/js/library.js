const metadataModal = new MetadataModal();

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
