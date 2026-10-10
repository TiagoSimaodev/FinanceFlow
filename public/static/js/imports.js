const importForm = document.querySelector("#import-form");
const importFile = document.querySelector("#csv-file");
const importFeedback = document.querySelector("#import-feedback");
const historyFeedback = document.querySelector("#history-feedback");
const importHistory = document.querySelector("#import-history");
const rejectionPanel = document.querySelector("#rejection-panel");
const rejectionList = document.querySelector("#rejection-list");
const importSubmit = document.querySelector("#import-submit");
const periodType = document.querySelector("#import-period-type");
const monthField = document.querySelector("#import-month-field");
const monthPeriod = document.querySelector("#import-month");
const yearField = document.querySelector("#import-year-field");
const yearPeriod = document.querySelector("#import-year");

function updatePeriodControls() {
  const isMonth = periodType.value === "month";
  monthField.hidden = !isMonth;
  monthPeriod.disabled = !isMonth;
  monthPeriod.required = isMonth;
  yearField.hidden = isMonth;
  yearPeriod.disabled = isMonth;
  yearPeriod.required = !isMonth;
}

function downloadTemplate(templateType) {
  const period = templateType === "month"
    ? monthPeriod.value
    : yearPeriod.value || monthPeriod.value.slice(0, 4);
  if (!period) {
    importFeedback.textContent = "Selecione o período antes de baixar o modelo.";
    importFeedback.className = "form-feedback error";
    return;
  }
  window.location.assign(
    `/api/imports/template?period_type=${templateType}&period=${encodeURIComponent(period)}`,
  );
}

async function requestJson(url, options) {
  const headers = new Headers(options?.headers || {});
  headers.set("X-CSRFToken", document.querySelector('meta[name="csrf-token"]').content);
  const response = await fetch(url, { ...options, headers });
  const payload = await response.json();
  if (!response.ok) {
    const error = new Error(payload.error || "Não foi possível concluir a operação.");
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function formatDateTime(value) {
  if (!value) return "—";
  const normalized = value.endsWith("Z") ? value : `${value}Z`;
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(normalized));
}

function formatStatus(status) {
  const labels = {
    processing: "Processando",
    succeeded: "Concluída",
    partial: "Parcial",
    failed: "Falhou",
  };
  return labels[status] || status;
}

function createCell(text, className = "") {
  const cell = document.createElement("td");
  cell.textContent = text;
  if (className) cell.className = className;
  return cell;
}

function renderImportHistory(batches) {
  importHistory.replaceChildren();
  if (batches.length === 0) {
    const row = document.createElement("tr");
    const empty = createCell("Nenhum arquivo foi importado.", "table-empty");
    empty.colSpan = 7;
    row.append(empty);
    importHistory.append(row);
    return;
  }

  for (const batch of batches) {
    const row = document.createElement("tr");
    const fileCell = document.createElement("td");
    fileCell.className = "file-cell";
    const fileName = document.createElement("strong");
    fileName.textContent = batch.file_name;
    const fileDate = document.createElement("span");
    fileDate.textContent = formatDateTime(batch.started_at);
    fileCell.append(fileName, fileDate);
    row.append(
      fileCell,
      createCell(formatStatus(batch.status), `import-status ${batch.status}`),
      createCell(String(batch.rows_processed)),
      createCell(String(batch.rows_accepted)),
      createCell(String(batch.rows_rejected)),
      createCell(batch.duration_ms === null ? "—" : `${batch.duration_ms} ms`),
    );

    const detailsCell = document.createElement("td");
    if (batch.rows_rejected > 0) {
      const detailsButton = document.createElement("button");
      detailsButton.type = "button";
      detailsButton.className = "text-button";
      detailsButton.textContent = "Ver motivos";
      detailsButton.addEventListener("click", () => showRejections(batch.id));
      detailsCell.append(detailsButton);
    } else if (batch.error_message) {
      detailsCell.textContent = batch.error_message;
      detailsCell.className = "import-error-cell";
    } else {
      detailsCell.textContent = "—";
    }
    row.append(detailsCell);
    importHistory.append(row);
  }
}

async function loadImportHistory() {
  historyFeedback.textContent = "";
  historyFeedback.className = "list-feedback";
  try {
    const batches = await requestJson("/api/imports");
    renderImportHistory(batches);
  } catch (error) {
    historyFeedback.textContent = error.message;
    historyFeedback.className = "list-feedback error";
  }
}

async function showRejections(importId) {
  historyFeedback.textContent = "";
  try {
    const rejections = await requestJson(`/api/imports/${importId}/rejections`);
    rejectionList.replaceChildren();
    if (rejections.length === 0) {
      const empty = document.createElement("li");
      empty.textContent = "Esta importação não tem linhas rejeitadas.";
      rejectionList.append(empty);
    }
    for (const rejection of rejections) {
      const item = document.createElement("li");
      const heading = document.createElement("strong");
      heading.textContent = `Linha ${rejection.row_number}: ${rejection.reason}`;
      const rawData = document.createElement("code");
      rawData.textContent = rejection.raw_data;
      item.append(heading, rawData);
      rejectionList.append(item);
    }
    rejectionPanel.hidden = false;
    rejectionPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) {
    historyFeedback.textContent = error.message;
    historyFeedback.className = "list-feedback error";
  }
}

importForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  importFeedback.textContent = "";
  importFeedback.className = "form-feedback";
  if (!importFile.files.length) {
    importFeedback.textContent = "Selecione um arquivo CSV.";
    importFeedback.className = "form-feedback error";
    return;
  }

  const formData = new FormData();
  formData.append("file", importFile.files[0]);
  formData.append("period_type", periodType.value);
  formData.append(
    "period",
    periodType.value === "month" ? monthPeriod.value : yearPeriod.value,
  );
  importSubmit.disabled = true;
  importSubmit.textContent = "Processando...";
  try {
    const result = await requestJson("/api/imports", {
      method: "POST",
      body: formData,
    });
    importFeedback.textContent =
      `Importação ${formatStatus(result.status).toLowerCase()}: ${result.rows_accepted} aceitas, ` +
      `${result.rows_rejected} rejeitadas de ${result.rows_processed} linhas.`;
    importFeedback.className = result.rows_rejected > 0
      ? "form-feedback warning"
      : "form-feedback success";
    importForm.reset();
    await loadImportHistory();
    if (result.rows_rejected > 0) await showRejections(result.import_id);
  } catch (error) {
    importFeedback.textContent = error.status === 409
      ? `${error.message} Consulte o histórico da importação #${error.payload.import_id}.`
      : error.message;
    importFeedback.className = "form-feedback error";
    await loadImportHistory();
  } finally {
    importSubmit.disabled = false;
    importSubmit.textContent = "Validar e importar";
  }
});

document.querySelector("#refresh-imports").addEventListener("click", loadImportHistory);
periodType.addEventListener("change", updatePeriodControls);
document.querySelector("#download-month-template").addEventListener("click", () => {
  downloadTemplate("month");
});
document.querySelector("#download-year-template").addEventListener("click", () => {
  downloadTemplate("year");
});
document.querySelector("#close-rejections").addEventListener("click", () => {
  rejectionPanel.hidden = true;
});
const currentMonth = new Date().toISOString().slice(0, 7);
monthPeriod.value = currentMonth;
yearPeriod.value = currentMonth.slice(0, 4);
yearPeriod.max = String(new Date().getFullYear());
updatePeriodControls();
loadImportHistory();
