const input = document.getElementById("q");
const tableBody = document.getElementById("searchResults");
const countEl = document.getElementById("resultCount");

const emptyRow = (message) => {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 2;
  cell.className = "empty-row";
  cell.textContent = message;
  row.appendChild(cell);
  return row;
};

const renderResults = (results, query) => {
  tableBody.innerHTML = "";
  if (!results.length) {
    tableBody.appendChild(emptyRow(query ? "No matches found." : "Type to search."));
    return;
  }

  results.forEach((item) => {
    const row = document.createElement("tr");

    const snippetCell = document.createElement("td");
    snippetCell.textContent = item.snippet || "";

    const fileCell = document.createElement("td");
    const link = document.createElement("a");
    link.href = `/markdown/${encodeURIComponent(item.filename)}`;
    link.textContent = item.filename;
    fileCell.appendChild(link);

    row.appendChild(snippetCell);
    row.appendChild(fileCell);
    tableBody.appendChild(row);
  });
};

const updateSearch = async (query) => {
  try {
    const response = await fetch(`/search?q=${encodeURIComponent(query)}`);
    if (!response.ok) {
      throw new Error("Search failed");
    }
    const data = await response.json();
    countEl.textContent = data.count;
    renderResults(data.results || [], query);
  } catch (error) {
    countEl.textContent = "0";
    renderResults([], query);
  }
};

let debounceTimer = null;

const onInput = () => {
  const query = input.value.trim();
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }
  debounceTimer = setTimeout(() => {
    updateSearch(query);
  }, 250);
};

if (input) {
  input.addEventListener("input", onInput);
  if (input.value.trim()) {
    updateSearch(input.value.trim());
  }
}
