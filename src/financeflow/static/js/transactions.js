const form = document.querySelector("#transaction-form");
const filtersForm = document.querySelector("#filters-form");
const typeInputs = document.querySelectorAll('input[name="type"]');
const categorySelect = document.querySelector("#category");
const filterCategorySelect = document.querySelector("#filter-category");
const formFeedback = document.querySelector("#form-feedback");
const listFeedback = document.querySelector("#list-feedback");
const transactionList = document.querySelector("#transaction-list");
const recordCount = document.querySelector("#record-count");

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
const dateFormatter = new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" });

function formatDate(isoDate) {
  return dateFormatter.format(new Date(`${isoDate}T00:00:00Z`));
}

async function requestJson(url, options) {
  const headers = new Headers(options?.headers || {});
  headers.set("X-CSRFToken", document.querySelector('meta[name="csrf-token"]').content);
  const response = await fetch(url, { ...options, headers });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Não foi possível concluir a operação.");
  }
  return payload;
}

function selectedType() {
  return document.querySelector('input[name="type"]:checked').value;
}

async function loadCategories(type) {
  categorySelect.replaceChildren(new Option("Carregando...", ""));
  try {
    const categories = await requestJson(`/api/categories?type=${encodeURIComponent(type)}`);
    categorySelect.replaceChildren(new Option("Selecione", ""));
    for (const category of categories) {
      categorySelect.add(new Option(category.name, category.id));
    }
    categorySelect.disabled = false;
    if (categories.length === 0) {
      categorySelect.replaceChildren(new Option("Nenhuma categoria disponível", ""));
    }
  } catch (error) {
    categorySelect.replaceChildren(new Option("Erro ao carregar categorias", ""));
    categorySelect.disabled = true;
    formFeedback.textContent = error.message;
    formFeedback.className = "form-feedback error";
  }
}

async function loadFilterCategories() {
  try {
    const categories = await requestJson("/api/categories");
    filterCategorySelect.replaceChildren(new Option("Todas", ""));
    for (const category of categories) {
      const option = new Option(category.name, category.id);
      option.dataset.type = category.type;
      filterCategorySelect.add(option);
    }
  } catch (error) {
    listFeedback.textContent = error.message;
    listFeedback.className = "list-feedback error";
  }
}

function renderTransactions(transactions) {
  transactionList.replaceChildren();
  recordCount.textContent = `${transactions.length} ${
    transactions.length === 1 ? "registro" : "registros"
  }`;

  if (transactions.length === 0) {
    const emptyMessage = document.createElement("li");
    emptyMessage.className = "empty-state";
    emptyMessage.textContent = "Nenhuma movimentação encontrada para este filtro.";
    transactionList.append(emptyMessage);
    return;
  }

  for (const transaction of transactions) {
    const item = document.createElement("li");
    item.className = "transaction-item";

    const info = document.createElement("div");
    info.className = "transaction-info";
    const symbol = document.createElement("span");
    symbol.className = `transaction-symbol ${transaction.type}`;
    symbol.setAttribute("aria-hidden", "true");
    symbol.textContent = transaction.type === "receita" ? "↗" : "↘";

    const copy = document.createElement("div");
    copy.className = "transaction-copy";
    const title = document.createElement("strong");
    title.textContent = transaction.description || transaction.category_name;
    const detail = document.createElement("span");
    detail.textContent = `${transaction.category_name} · ${formatDate(transaction.date)}`;
    copy.append(title, detail);
    info.append(symbol, copy);

    const amount = document.createElement("span");
    amount.className = `transaction-amount ${transaction.type}`;
    const formattedAmount = currencyFormatter.format(transaction.amount_cents / 100);
    amount.textContent = transaction.type === "receita"
      ? `+ ${formattedAmount}`
      : `− ${formattedAmount}`;
    item.append(info, amount);
    transactionList.append(item);
  }
}

async function loadTransactions() {
  listFeedback.textContent = "";
  listFeedback.className = "list-feedback";
  const parameters = new URLSearchParams();
  for (const [key, value] of new FormData(filtersForm).entries()) {
    if (value) parameters.set(key, value);
  }

  try {
    const transactions = await requestJson(`/api/transactions?${parameters.toString()}`);
    renderTransactions(transactions);
  } catch (error) {
    listFeedback.textContent = error.message;
    listFeedback.className = "list-feedback error";
  }
}

for (const input of typeInputs) {
  input.addEventListener("change", () => {
    formFeedback.textContent = "";
    formFeedback.className = "form-feedback";
    loadCategories(selectedType());
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formFeedback.textContent = "";
  formFeedback.className = "form-feedback";
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  payload.amount = payload.amount.replace(",", ".");
  payload.category_id = Number(payload.category_id);

  try {
    await requestJson("/api/transactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    form.reset();
    document.querySelector('input[name="type"][value="despesa"]').checked = true;
    document.querySelector("#date").value = new Date().toISOString().slice(0, 10);
    await loadCategories(selectedType());
    formFeedback.textContent = "Movimentação salva com sucesso.";
    formFeedback.className = "form-feedback success";
    await loadTransactions();
  } catch (error) {
    formFeedback.textContent = error.message;
    formFeedback.className = "form-feedback error";
  }
});

filtersForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadTransactions();
});

document.querySelector("#filter-type").addEventListener("change", (event) => {
  if (event.target.value && filterCategorySelect.value) {
    const selectedCategory = filterCategorySelect.selectedOptions[0];
    const selectedCategoryType = selectedCategory.dataset.type;
    if (selectedCategoryType && selectedCategoryType !== event.target.value) {
      filterCategorySelect.value = "";
    }
  }
  loadTransactions();
});

filterCategorySelect.addEventListener("change", loadTransactions);

loadCategories(selectedType());
loadFilterCategories();
document.querySelector("#date").value = new Date().toISOString().slice(0, 10);
loadTransactions();
