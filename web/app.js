const scenarios = {
  daily: {
    recordType: "daily",
    files: ["дневник_наблюдений.xlsx", "отчёт_о_занятии.pdf", "обратная_связь_родителя.docx"],
  },
  weekly: {
    recordType: "weekly",
    files: ["дневник_наблюдений.xlsx", "отчёт_о_занятии.pdf", "обратная_связь_родителя.docx", "заключение_специалиста.png"],
  },
  incomplete: {
    recordType: "daily",
    files: ["дневник_наблюдений.xlsx", "отчёт_о_занятии.pdf"],
  },
  unknown: {
    recordType: "daily",
    files: ["дневник_наблюдений.xlsx", "отчёт_о_занятии.pdf", "обратная_связь_родителя.docx", "scan_0041.jpg"],
  },
};

const form = document.querySelector("#check-form");
const fileInput = document.querySelector("#files");
const selectedFiles = document.querySelector("#selected-files");
const result = document.querySelector("#result");
const history = document.querySelector("#history");
const requestMeta = document.querySelector("#request-meta");
const jsonResponse = document.querySelector("#json-response");
const actionButtons = [...document.querySelectorAll("#submit-button, .scenario-run")];
const manualFiles = [];

document.querySelectorAll(".mode-button").forEach((button) => {
  button.addEventListener("click", () => {
    const activeMode = button.dataset.mode;
    document.querySelectorAll(".mode-button").forEach((modeButton) => {
      modeButton.setAttribute("aria-pressed", String(modeButton === button));
    });
    document.querySelector("#manual-panel").hidden = activeMode !== "manual";
    document.querySelector("#scenarios-panel").hidden = activeMode !== "scenarios";
  });
});

document.querySelectorAll("[data-files-for]").forEach((list) => {
  const scenario = scenarios[list.dataset.filesFor];
  scenario.files.forEach((name) => {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = `/demo-files/${encodeURIComponent(name)}`;
    link.download = name;
    link.textContent = name;
    item.append(link);
    list.append(item);
  });
});

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

function setBusy(busy) {
  actionButtons.forEach((button) => { button.disabled = busy; });
}

function showRequest(method, path, recordType, names, code, data) {
  const values = [`${method} ${path}`, recordType || "—", names.length ? names.join(", ") : "—", code ?? "—"];
  requestMeta.querySelectorAll("dd").forEach((node, index) => { node.textContent = values[index]; });
  jsonResponse.textContent = data === null ? "Нет ответа от сервера" : JSON.stringify(data, null, 2);
}

async function apiRequest(method, path, { body, recordType = "", names = [], trace = true } = {}) {
  try {
    const response = await fetch(path, { method, body });
    const data = await response.json();
    if (trace) showRequest(method, path, recordType, names, response.status, data);
    if (!response.ok) throw new Error(data.detail ? JSON.stringify(data.detail) : `HTTP ${response.status}`);
    return data;
  } catch (error) {
    if (trace && error instanceof TypeError) showRequest(method, path, recordType, names, "сеть", { error: error.message });
    throw error;
  }
}

function showError(message) {
  result.replaceChildren(element("p", "issue-error", message));
}

function showResult(data) {
  const banner = element("div", `result-banner ${data.status}`);
  banner.append(element("strong", "", data.status_label || data.status));
  banner.append(element("span", "", data.reason || (data.status === "complete" ? "Все обязательные материалы на месте." : "Проверка выполняется.")));
  result.replaceChildren(banner);

  const issueGroup = element("div", "result-group");
  issueGroup.append(element("h3", "", `Замечания · ${data.issues.length}`));
  const issueList = element("ul");
  data.issues.forEach((issue) => issueList.append(element("li", `issue-${issue.level}`, issue.message)));
  if (!data.issues.length) issueList.append(element("li", "", "Замечаний нет"));
  issueGroup.append(issueList);
  result.append(issueGroup);

  const documentGroup = element("div", "result-group");
  documentGroup.append(element("h3", "", `Файлы · ${data.documents.length}`));
  const documentList = element("ul");
  data.documents.forEach((document) => {
    const row = element("li", "", document.name);
    row.append(element("small", "", `${document.detected_type || "Тип не определён"} · ${document.size_kb} КБ`));
    documentList.append(row);
  });
  documentGroup.append(documentList);
  result.append(documentGroup);
}

async function refreshHistory(trace = true) {
  try {
    const rows = await apiRequest("GET", "/api/checks", { trace });
    history.replaceChildren();
    if (!rows.length) {
      history.textContent = "Проверок пока нет.";
      return;
    }
    rows.forEach((item) => {
      const row = element("button", "history-item");
      row.type = "button";
      const description = element("span");
      description.append(element("strong", "", item.record_type === "daily" ? "Дневная запись" : "Недельная запись"));
      description.append(element("small", "", `${new Date(item.created_at).toLocaleString("ru-RU")} · ${item.materials_count} файл(ов)`));
      row.append(description, element("span", `status-chip ${item.status}`, item.status === "complete" ? "Полная" : item.status === "incomplete" ? "Неполная" : "В работе"));
      row.addEventListener("click", () => openDetails(item.id));
      history.append(row);
    });
  } catch (error) {
    history.textContent = `Не удалось загрузить историю: ${error.message}`;
  }
}

async function openDetails(id) {
  try {
    showResult(await apiRequest("GET", `/api/checks/${id}`));
  } catch (error) {
    showError(`Не удалось открыть проверку: ${error.message}`);
  }
}

async function submitCheck(recordType, files) {
  if (!files.length) {
    showError("Добавьте хотя бы один файл.");
    return;
  }
  const body = new FormData();
  body.append("record_type", recordType);
  files.forEach((file) => body.append("files", file));
  setBusy(true);
  try {
    const data = await apiRequest("POST", "/api/checks", { body, recordType, names: files.map((file) => file.name) });
    showResult(data);
    await refreshHistory(false);
  } catch (error) {
    showError(`Не удалось выполнить проверку: ${error.message}`);
  } finally {
    setBusy(false);
  }
}

function renderSelectedFiles() {
  selectedFiles.replaceChildren();
  manualFiles.forEach((file, index) => {
    const item = element("li", "selected-file");
    item.append(element("span", "", file.name));
    const remove = element("button", "remove-file", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", `Убрать файл ${file.name}`);
    remove.addEventListener("click", () => {
      manualFiles.splice(index, 1);
      renderSelectedFiles();
    });
    item.append(remove);
    selectedFiles.append(item);
  });
}

fileInput.addEventListener("change", () => {
  manualFiles.push(...fileInput.files);
  fileInput.value = "";
  renderSelectedFiles();
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  submitCheck(form.elements.record_type.value, [...manualFiles]);
});

document.querySelectorAll("[data-scenario]").forEach((button) => {
  button.addEventListener("click", async () => {
    const scenario = scenarios[button.dataset.scenario];
    setBusy(true);
    try {
      const files = await Promise.all(scenario.files.map(async (name) => {
        const response = await fetch(`/demo-files/${encodeURIComponent(name)}`);
        if (!response.ok) throw new Error(`Файл «${name}» недоступен (HTTP ${response.status})`);
        return new File([await response.blob()], name);
      }));
      await submitCheck(scenario.recordType, files);
    } catch (error) {
      showError(`Не удалось подготовить сценарий: ${error.message}`);
    } finally {
      setBusy(false);
    }
  });
});

document.querySelector("#refresh-history").addEventListener("click", () => refreshHistory());
refreshHistory();
