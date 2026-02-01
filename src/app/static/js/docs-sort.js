// Sortable "Your Docs" table functionality
// Three-state sorting: original -> ascending -> descending -> original

const SORT_STATES = {
  ORIGINAL: 'original',
  ASCENDING: 'ascending',
  DESCENDING: 'descending'
};

const SORT_ICONS = {
  [SORT_STATES.ORIGINAL]: '⇅',
  [SORT_STATES.ASCENDING]: '↑',
  [SORT_STATES.DESCENDING]: '↓'
};

class DocsSorter {
  constructor() {
    this.sortBtn = document.getElementById('sortDocsBtn');
    this.tableBody = document.getElementById('docsTableBody');

    if (!this.sortBtn || !this.tableBody) {
      return;
    }

    this.currentState = SORT_STATES.ORIGINAL;
    this.originalOrder = [];

    this.init();
  }

  init() {
    // Store the original order of rows
    this.storeOriginalOrder();

    // Add click event listener
    this.sortBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation(); // Prevent details toggle
      this.toggleSort();
    });
  }

  storeOriginalOrder() {
    // Store references to all rows in their original order
    const rows = Array.from(this.tableBody.querySelectorAll('tr[data-filename]'));
    this.originalOrder = rows.map(row => row.cloneNode(true));
  }

  toggleSort() {
    // Cycle through sort states
    if (this.currentState === SORT_STATES.ORIGINAL) {
      this.currentState = SORT_STATES.ASCENDING;
      this.sortAscending();
    } else if (this.currentState === SORT_STATES.ASCENDING) {
      this.currentState = SORT_STATES.DESCENDING;
      this.sortDescending();
    } else {
      this.currentState = SORT_STATES.ORIGINAL;
      this.restoreOriginal();
    }

    // Update button icon
    this.updateIcon();
  }

  sortAscending() {
    const rows = Array.from(this.tableBody.querySelectorAll('tr[data-filename]'));

    rows.sort((a, b) => {
      const filenameA = a.dataset.filename.toLowerCase();
      const filenameB = b.dataset.filename.toLowerCase();
      return filenameA.localeCompare(filenameB);
    });

    this.renderRows(rows);
  }

  sortDescending() {
    const rows = Array.from(this.tableBody.querySelectorAll('tr[data-filename]'));

    rows.sort((a, b) => {
      const filenameA = a.dataset.filename.toLowerCase();
      const filenameB = b.dataset.filename.toLowerCase();
      return filenameB.localeCompare(filenameA);
    });

    this.renderRows(rows);
  }

  restoreOriginal() {
    // Restore the original order using cloned nodes
    this.renderRows(this.originalOrder.map(row => row.cloneNode(true)));
  }

  renderRows(rows) {
    // Clear existing data rows (keep empty state row if present)
    const emptyRow = this.tableBody.querySelector('tr:not([data-filename])');
    this.tableBody.innerHTML = '';

    // Re-append rows in new order
    rows.forEach(row => this.tableBody.appendChild(row));

    // Re-append empty row if it existed
    if (emptyRow && rows.length === 0) {
      this.tableBody.appendChild(emptyRow);
    }
  }

  updateIcon() {
    this.sortBtn.textContent = SORT_ICONS[this.currentState];
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => new DocsSorter());
} else {
  new DocsSorter();
}
