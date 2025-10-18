const DEFAULT_API_BASE = "http://localhost:8000";
const POLL_INTERVAL_MS = 2000;

const apiBaseInput = document.getElementById("apiBase");
const saveApiBaseButton = document.getElementById("saveApiBase");
const apiBaseStatus = document.getElementById("apiBaseStatus");
const analyzeForm = document.getElementById("analyzeForm");
const urlInput = document.getElementById("urlInput");
const useCurrentTabButton = document.getElementById("useCurrentTab");
const analyzeButton = document.getElementById("analyzeButton");
const resultSection = document.getElementById("result");
const resultSummary = document.getElementById("resultSummary");
const resultDetails = document.getElementById("resultDetails");
const toggleDetailsButton = document.getElementById("toggleDetails");
const historyList = document.getElementById("historyList");
const historyCardTemplate = document.getElementById("historyCard");
const refreshHistoryButton = document.getElementById("refreshHistory");

const extensionApi =
  typeof chrome !== "undefined" ? chrome : typeof browser !== "undefined" ? browser : null;

let apiBase = DEFAULT_API_BASE;
let activePoll = null;

document.addEventListener("DOMContentLoaded", async () => {
  apiBase = await loadApiBase();
  apiBaseInput.value = apiBase;

  const tabUrl = await getActiveTabUrl();
  if (tabUrl) {
    urlInput.value = tabUrl;
  }

  await loadHistory();
});

saveApiBaseButton.addEventListener("click", async () => {
  const value = apiBaseInput.value.trim();
  if (!value) {
    showApiBaseStatus("Base URL is required.", true);
    return;
  }
  if (!/^https?:\/\//i.test(value)) {
    showApiBaseStatus("Use http:// or https://", true);
    return;
  }

  await saveApiBase(value);
  apiBase = value;
  showApiBaseStatus("Saved.", false);
});

useCurrentTabButton.addEventListener("click", async () => {
  const tabUrl = await getActiveTabUrl();
  if (tabUrl) {
    urlInput.value = tabUrl;
  }
});

analyzeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = urlInput.value.trim();
  if (!url) {
    setResultError("Enter a URL to analyze.");
    return;
  }

  analyzeButton.disabled = true;
  setResultInfo("Submitting request...");

  try {
    const response = await fetch(`${apiBase}/api/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url }),
    });

    if (!response.ok) {
      const text = await safeReadText(response);
      setResultError(`Backend error: ${text}`);
      analyzeButton.disabled = false;
      return;
    }

    const data = await response.json();
    const taskId = data.task_id;
    const status = data.status || "QUEUED";
    setResultInfo(`Task queued (${status}). Waiting for result...`);
    startPolling(taskId);
  } catch (err) {
    setResultError(`Request failed: ${err}`);
    analyzeButton.disabled = false;
  }
});

toggleDetailsButton.addEventListener("click", () => {
  const hidden = resultDetails.classList.toggle("hidden");
  toggleDetailsButton.textContent = hidden ? "Show details" : "Hide details";
});

refreshHistoryButton.addEventListener("click", () => {
  loadHistory();
});

async function loadApiBase() {
  if (!extensionApi || !extensionApi.storage || !extensionApi.storage.sync) {
    return DEFAULT_API_BASE;
  }
  return new Promise((resolve) => {
    extensionApi.storage.sync.get({ apiBase: DEFAULT_API_BASE }, (items) => {
      resolve(items.apiBase || DEFAULT_API_BASE);
    });
  });
}

async function saveApiBase(value) {
  if (!extensionApi || !extensionApi.storage || !extensionApi.storage.sync) {
    apiBase = value;
    return;
  }
  return new Promise((resolve) => {
    extensionApi.storage.sync.set({ apiBase: value }, () => resolve());
  });
}

async function getActiveTabUrl() {
  if (!extensionApi || !extensionApi.tabs || !extensionApi.tabs.query) {
    return "";
  }
  return new Promise((resolve) => {
    extensionApi.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (Array.isArray(tabs) && tabs.length > 0) {
        resolve(tabs[0].url || "");
      } else {
        resolve("");
      }
    });
  });
}

async function startPolling(taskId) {
  if (activePoll) {
    clearTimeout(activePoll);
  }

  const poll = async () => {
    try {
      const response = await fetch(`${apiBase}/api/result/${taskId}`);
      if (response.status === 404) {
        setResultError("Task not found.");
        analyzeButton.disabled = false;
        return;
      }
      if (!response.ok) {
        const text = await safeReadText(response);
        setResultError(`Backend error: ${text}`);
        analyzeButton.disabled = false;
        return;
      }

      const payload = await response.json();
      const status = (payload.status || "").toUpperCase();

      if (status === "FAILED") {
        showResult(payload, true);
        analyzeButton.disabled = false;
        return;
      }

      if (status === "COMPLETED") {
        showResult(payload, false);
        analyzeButton.disabled = false;
        loadHistory();
        return;
      }

      setResultInfo(`Task status: ${status || "PENDING"}...`);
      activePoll = setTimeout(poll, POLL_INTERVAL_MS);
    } catch (err) {
      setResultError(`Polling failed: ${err}`);
      analyzeButton.disabled = false;
    }
  };

  poll();
}

function showResult(payload, failed) {
  resultSection.classList.remove("hidden");
  resultDetails.textContent = JSON.stringify(payload.details || {}, null, 2);
  resultDetails.classList.add("hidden");
  toggleDetailsButton.textContent = "Show details";

  const verdict = (payload.verdict || (failed ? "FAILED" : "UNKNOWN")).toUpperCase();
  const score =
    typeof payload.risk_score === "number" ? payload.risk_score.toString() : "n/a";
  const cssClass = verdictToClass(verdict);
  const status = payload.status || (failed ? "FAILED" : "UNKNOWN");

  resultSummary.innerHTML = `
    <div class="summary-line ${cssClass}">
      <span>${verdictLabel(verdict)}</span>
      <span>Score: ${score}</span>
    </div>
    <div class="summary-details">Status: ${status}</div>
  `;
}

function setResultInfo(message) {
  resultSection.classList.remove("hidden");
  resultSummary.innerHTML = `<div class="summary-line unknown">${sanitize(message)}</div>`;
  resultDetails.textContent = "";
  resultDetails.classList.add("hidden");
  toggleDetailsButton.textContent = "Show details";
}

function setResultError(message) {
  resultSection.classList.remove("hidden");
  resultSummary.innerHTML = `<div class="summary-line failed">${sanitize(message)}</div>`;
  resultDetails.textContent = "";
  resultDetails.classList.add("hidden");
  toggleDetailsButton.textContent = "Show details";
}

async function loadHistory() {
  try {
    const response = await fetch(`${apiBase}/api/history?limit=10`);
    if (!response.ok) {
      const text = await safeReadText(response);
      renderHistoryError(`Backend error: ${text}`);
      return;
    }

    const payload = await response.json();
    renderHistory(payload.items || []);
  } catch (err) {
    renderHistoryError(`Failed to load history: ${err}`);
  }
}

function renderHistory(items) {
  historyList.innerHTML = "";
  if (!items.length) {
    renderHistoryMessage("No history yet.");
    return;
  }

  for (const item of items) {
    const fragment = historyCardTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".history-card");
    const verdictHost = card.querySelector(".history-card__verdict");
    verdictHost.appendChild(renderVerdictPill(item.verdict));
    const score = typeof item.risk_score === "number" ? item.risk_score : "n/a";
    card.querySelector(".history-card__score").textContent = `Score: ${score}`;
    card.querySelector(".history-card__url").textContent = item.url || "";
    card.querySelector(".history-card__status").textContent = (item.status || "").toLowerCase();
    card.querySelector(".history-card__created").textContent = formatDate(item.created_at);
    historyList.appendChild(fragment);
  }
}

function renderVerdictPill(verdictValue) {
  const verdict = (verdictValue || "UNKNOWN").toUpperCase();
  const span = document.createElement("span");
  span.classList.add("verdict-pill", verdictToClass(verdict));
  span.textContent = verdictLabel(verdict);
  return span;
}

function renderHistoryError(message) {
  renderHistoryMessage(message, true);
}

function renderHistoryMessage(message, isError = false) {
  historyList.innerHTML = "";
  const box = document.createElement("div");
  box.className = isError ? "history-error" : "history-empty";
  box.textContent = message;
  historyList.appendChild(box);
}

function verdictToClass(verdict) {
  switch (verdict) {
    case "SAFE":
      return "safe";
    case "WARNING":
      return "warning";
    case "PHISHING":
      return "phishing";
    case "FAILED":
      return "failed";
    default:
      return "unknown";
  }
}

function verdictLabel(verdict) {
  switch (verdict) {
    case "SAFE":
      return "Safe";
    case "WARNING":
      return "Warning";
    case "PHISHING":
      return "Phishing";
    case "FAILED":
      return "Failed";
    default:
      return "Unknown";
  }
}

function showApiBaseStatus(message, isError) {
  apiBaseStatus.textContent = message;
  apiBaseStatus.style.color = isError ? "#b91c1c" : "#1d4ed8";
  setTimeout(() => {
    apiBaseStatus.textContent = "";
  }, 3000);
}

function sanitize(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

async function safeReadText(response) {
  try {
    return await response.text();
  } catch (err) {
    return `Unable to read response: ${err}`;
  }
}

function formatDate(value) {
  if (!value) {
    return "--";
  }
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString();
  } catch (err) {
    return value;
  }
}
