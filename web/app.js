const form = document.getElementById("forecast-form");
const targetInput = document.getElementById("target-month");
const monthsInput = document.getElementById("months-ahead");
const statusEl = document.getElementById("form-status");
const summaryEl = document.getElementById("summary");
const tableBody = document.querySelector("#results-table tbody");
const filterContainer = document.querySelector(".controls");
const monthFilter = document.getElementById("month-filter");

let cachedResults = [];

async function fetchForecast(params = "") {
  const url = params ? `/api/forecast?${params}` : "/api/forecast";
  const response = await fetch(url);
  if (!response.ok) {
    let message = "Request failed";
    try {
      const data = await response.json();
      message = data.detail || JSON.stringify(data);
    } catch (error) {
      message = await response.text();
    }
    throw new Error(message);
  }
  return response.json();
}

function updateSummary(data) {
  const targetText = data.target_date ? `Target month: ${data.target_date}` : "Target month: (next available)";
  summaryEl.innerHTML = `
    <h2>Results</h2>
    <p>Latest observed month: <strong>${data.latest_observation}</strong></p>
    <p>${targetText}</p>
    <p>Generated ${data.result_count} regional forecasts over ${data.months_generated} month(s).</p>
  `;
}

function renderTable(rows) {
  if (!rows.length) {
    tableBody.innerHTML = `<tr><td colspan="6">No rows to display.</td></tr>`;
    return;
  }
  tableBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${row.region}</td>
          <td>${row.current_date}</td>
          <td>${row.forecast_date}</td>
          <td>${row.current_price.toFixed(2)}</td>
          <td>${row.forecast_price.toFixed(2)}</td>
          <td>${(row.pct_change * 100).toFixed(2)}%</td>
        </tr>
      `
    )
    .join("");
}

function updateFilterOptions(rows) {
  const months = Array.from(new Set(rows.map((row) => row.forecast_date)));
  if (!months.length) {
    filterContainer.hidden = true;
    monthFilter.innerHTML = "";
    return;
  }
  filterContainer.hidden = false;
  monthFilter.innerHTML = months
    .map((value, index) => `<option value="${value}" ${index === 0 ? "selected" : ""}>${value}</option>`)
    .join("");
}

function applyFilter() {
  const selectedDate = monthFilter.value;
  const filtered = selectedDate ? cachedResults.filter((row) => row.forecast_date === selectedDate) : cachedResults;
  renderTable(filtered);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    statusEl.textContent = "Loading...";
    const monthsAhead = Math.max(1, Math.min(24, parseInt(monthsInput.value, 10) || 1));
    const params = new URLSearchParams({ months: monthsAhead });
    if (targetInput.value) {
      const [year, month] = targetInput.value.split("-");
      params.set("target_year", year);
      params.set("target_month", month);
    }
    const data = await fetchForecast(params.toString());
    cachedResults = data.results;
    updateSummary(data);
    updateFilterOptions(cachedResults);
    applyFilter();
    statusEl.textContent = "Forecast updated.";
  } catch (error) {
    console.error(error);
    statusEl.textContent = `Error: ${error.message}`;
    tableBody.innerHTML = "";
  }
});

monthFilter.addEventListener("change", applyFilter);

(async function init() {
  try {
    statusEl.textContent = "Loading initial forecast...";
    const data = await fetchForecast("months=1");
    cachedResults = data.results;
    updateSummary(data);
    updateFilterOptions(cachedResults);
    applyFilter();
    statusEl.textContent = "";
  } catch (error) {
    statusEl.textContent = `Unable to load initial forecast: ${error.message}`;
  }
})();
