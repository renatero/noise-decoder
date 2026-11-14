const params = new URLSearchParams(location.search);
const input = document.querySelector("#investigation");
const note = document.querySelector("#input-note");
const status = document.querySelector("#status");
const report = document.querySelector("#report");

input.value = params.get("investigate") || "";
const inputType = params.get("input_type");
if (input.value && inputType) {
  note.textContent = `Prefilled from extension: ${inputType}. This reference has not been collected or analysed.`;
}

document.querySelector("#investigation-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  status.textContent = "Preparing investigation…";
  report.hidden = true;
  status.textContent = "Investigation prepared. No page content was collected and no analysis request was sent. Choose a dataset or public-data source when that dashboard workflow is available.";
});
