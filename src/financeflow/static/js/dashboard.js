const monthInput = document.querySelector("#dashboard-month");
const typeSelect = document.querySelector("#dashboard-type");
const categorySelect = document.querySelector("#dashboard-category");
const feedback = document.querySelector("#dashboard-feedback");
const categoryEmpty = document.querySelector("#category-empty");
const categoryCanvas = document.querySelector("#category-chart");
let monthlyChart;
let categoryChart;
let currentDashboard;

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
const percentageFormatter = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 2,
});
const monthNames = [
  "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
  "Jul", "Ago", "Set", "Out", "Nov", "Dez",
];
const chartColors = ["#287b56", "#e8995b", "#6c91bd", "#9a7ac0", "#d27672", "#82a96c"];

function formatMoney(cents) {
  return currencyFormatter.format(cents / 100);
}

function formatMonth(month) {
  const [year, number] = month.split("-");
  return `${monthNames[Number(number) - 1]}/${year.slice(-2)}`;
}

async function requestDashboard(month) {
  const parameters = new URLSearchParams({ month });
  if (typeSelect.value) parameters.set("type", typeSelect.value);
  if (categorySelect.value) parameters.set("category_id", categorySelect.value);
  const response = await fetch(`/api/dashboard?${parameters.toString()}`);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Não foi possível carregar o dashboard.");
  }
  return payload;
}

function renderMonthlyChart(monthly) {
  if (monthlyChart) monthlyChart.destroy();
  if (typeof Chart === "undefined") {
    feedback.textContent = "Os indicadores foram carregados, mas os gráficos precisam de conexão para carregar o Chart.js.";
    feedback.className = "dashboard-feedback error";
    return;
  }
  const isDark = document.documentElement.dataset.theme === "dark";
  const chartText = isDark ? "#c3cec6" : "#68756c";

  monthlyChart = new Chart(document.querySelector("#monthly-chart"), {
    type: "bar",
    data: {
      labels: monthly.map((item) => formatMonth(item.month)),
      datasets: [
        {
          label: "Receitas",
          data: monthly.map((item) => item.income_cents / 100),
          backgroundColor: "#65a87a",
          borderRadius: 5,
          maxBarThickness: 24,
        },
        {
          label: "Despesas",
          data: monthly.map((item) => item.expenses_cents / 100),
          backgroundColor: "#e9a06b",
          borderRadius: 5,
          maxBarThickness: 24,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        color: chartText,
        legend: {
          position: "bottom",
          labels: { color: chartText, usePointStyle: true, pointStyle: "circle", boxWidth: 7, padding: 18 },
        },
        tooltip: {
          callbacks: {
            label: (context) => `${context.dataset.label}: ${currencyFormatter.format(context.parsed.y)}`,
          },
        },
      },
      scales: {
        x: { grid: { display: false }, border: { display: false }, ticks: { color: chartText } },
        y: {
          beginAtZero: true,
          border: { display: false },
          grid: { color: isDark ? "#35443b" : "#edf1ed" },
          ticks: { color: chartText,
            callback: (value) => new Intl.NumberFormat("pt-BR", {
              notation: "compact",
              style: "currency",
              currency: "BRL",
              maximumFractionDigits: 1,
            }).format(value),
          },
        },
      },
    },
  });
}

function renderCategoryChart(categories) {
  if (categoryChart) {
    categoryChart.destroy();
    categoryChart = undefined;
  }

  const hasExpenses = categories.some((category) => category.amount_cents > 0);
  categoryCanvas.hidden = !hasExpenses;
  categoryEmpty.hidden = hasExpenses;
  if (!hasExpenses || typeof Chart === "undefined") return;
  const chartText = document.documentElement.dataset.theme === "dark" ? "#c3cec6" : "#68756c";

  categoryChart = new Chart(categoryCanvas, {
    type: "doughnut",
    data: {
      labels: categories.map((item) => item.category_name),
      datasets: [{
        data: categories.map((item) => item.amount_cents / 100),
        backgroundColor: categories.map((_, index) => chartColors[index % chartColors.length]),
        borderWidth: 0,
        hoverOffset: 5,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      plugins: {
        color: chartText,
        legend: {
          position: "bottom",
          labels: { color: chartText, usePointStyle: true, pointStyle: "circle", boxWidth: 7, padding: 15 },
        },
        tooltip: {
          callbacks: {
            label: (context) => `${context.label}: ${currencyFormatter.format(context.parsed)}`,
          },
        },
      },
    },
  });
}

function renderDashboard(data) {
  currentDashboard = data;
  const totals = data.totals;
  document.querySelector("#total-income").textContent = formatMoney(totals.income_cents);
  document.querySelector("#total-expenses").textContent = formatMoney(totals.expenses_cents);
  document.querySelector("#total-balance").textContent = formatMoney(totals.balance_cents);
  document.querySelector("#savings-rate").textContent = totals.savings_rate_pct === null
    ? "—"
    : `${percentageFormatter.format(totals.savings_rate_pct)}%`;

  const variation = document.querySelector("#expense-variation");
  if (totals.expense_variation_pct === null) {
    variation.textContent = "Sem base";
    variation.className = "variation-value neutral";
  } else {
    const percentage = Math.abs(totals.expense_variation_pct);
    const direction = totals.expense_variation_pct > 0
      ? "aumento"
      : totals.expense_variation_pct < 0 ? "redução" : "sem alteração";
    variation.textContent = `${percentageFormatter.format(percentage)}%`;
    variation.className = `variation-value ${
      totals.expense_variation_pct > 0 ? "increase" : "decrease"
    }`;
    document.querySelector("#expense-comparison-caption").textContent =
      `${direction} vs. ${formatMonth(data.period.previous_month)}`;
  }

  renderMonthlyChart(data.monthly);
  renderCategoryChart(data.categories);
  document.querySelector("#category-chart-title").textContent =
    data.period.type === "receita" ? "Entradas por categoria" : "Despesas por categoria";
  updateExportUrls();
}

function currentDashboardParameters() {
  const parameters = new URLSearchParams({ month: monthInput.value });
  if (typeSelect.value) parameters.set("type", typeSelect.value);
  if (categorySelect.value) parameters.set("category_id", categorySelect.value);
  return parameters;
}

function updateExportUrls() {
  if (!currentDashboard) return;
  for (const button of document.querySelectorAll("[data-export-format]")) {
    const parameters = currentDashboardParameters();
    parameters.set("format", button.dataset.exportFormat);
    button.dataset.exportUrl = `/api/dashboard/export?${parameters.toString()}`;
    button.disabled = false;
  }
}

function downloadChart(chart, name) {
  if (!chart) {
    feedback.textContent = "Este gráfico ainda não está disponível para download.";
    feedback.className = "dashboard-feedback error";
    return;
  }
  const link = document.createElement("a");
  link.href = chart.toBase64Image("image/png", 1);
  link.download = `financeflow-${name}-${currentDashboard.period.month}.png`;
  link.click();
}

async function downloadData(format) {
  const button = document.querySelector(`[data-export-format="${format}"]`);
  if (!button?.dataset.exportUrl) {
    feedback.textContent = "Aguarde o carregamento do período antes de exportar.";
    feedback.className = "dashboard-feedback error";
    return;
  }
  button.disabled = true;
  feedback.textContent = "";
  feedback.className = "dashboard-feedback";
  try {
    const response = await fetch(button.dataset.exportUrl);
    if (!response.ok) {
      const payload = await response.json();
      throw new Error(payload.error || "Não foi possível baixar o arquivo.");
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1]
      || `financeflow-movimentacoes.${format}`;
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  } catch (error) {
    feedback.textContent = error.message;
    feedback.className = "dashboard-feedback error";
  } finally {
    button.disabled = false;
  }
}

async function loadCategories() {
  const selectedCategoryId = categorySelect.value;
  const parameters = new URLSearchParams();
  if (typeSelect.value) parameters.set("type", typeSelect.value);
  try {
    const categories = await requestDashboardCategories(parameters);
    categorySelect.replaceChildren(new Option("Todas as categorias", ""));
    for (const category of categories) {
      const option = new Option(category.name, category.id);
      option.dataset.type = category.type;
      categorySelect.add(option);
    }
    if (categories.some((category) => String(category.id) === selectedCategoryId)) {
      categorySelect.value = selectedCategoryId;
    }
  } catch (error) {
    feedback.textContent = error.message;
    feedback.className = "dashboard-feedback error";
  }
}

async function requestDashboardCategories(parameters) {
  const response = await fetch(`/api/categories?${parameters.toString()}`);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Não foi possível carregar as categorias.");
  }
  return payload;
}

async function loadDashboard() {
  feedback.textContent = "";
  feedback.className = "dashboard-feedback";
  for (const button of document.querySelectorAll("[data-export-format]")) {
    button.disabled = true;
  }
  try {
    const data = await requestDashboard(monthInput.value);
    renderDashboard(data);
  } catch (error) {
    feedback.textContent = error.message;
    feedback.className = "dashboard-feedback error";
  }
}

window.addEventListener("financeflow-theme-change", () => {
  if (currentDashboard) renderDashboard(currentDashboard);
});
typeSelect.addEventListener("change", async () => {
  categorySelect.value = "";
  await loadCategories();
  await loadDashboard();
});
categorySelect.addEventListener("change", async () => {
  const selectedOption = categorySelect.selectedOptions[0];
  if (selectedOption.dataset.type) typeSelect.value = selectedOption.dataset.type;
  await loadDashboard();
});

for (const button of document.querySelectorAll("[data-export-format]")) {
  button.addEventListener("click", () => downloadData(button.dataset.exportFormat));
}

for (const button of document.querySelectorAll("[data-export-chart]")) {
  button.addEventListener("click", () => {
    const name = button.dataset.exportChart;
    downloadChart(name === "monthly" ? monthlyChart : categoryChart, name);
  });
}

const now = new Date();
monthInput.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
monthInput.addEventListener("change", loadDashboard);
loadCategories();
loadDashboard();
