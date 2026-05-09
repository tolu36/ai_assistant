const byId = (id) => document.getElementById(id);

const splitList = (value) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const joinList = (items) => (items || []).join(", ");
let activeProposalId = null;
const tokenStorageKey = "personal_ai_assistant_app_token";

function withAuthHeaders(headers = {}) {
  const token = localStorage.getItem(tokenStorageKey);
  return token ? { ...headers, "X-App-Token": token } : headers;
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: withAuthHeaders(options.headers || {}),
  });
  if (response.status !== 401) {
    return response;
  }

  const token = window.prompt("Enter app access token");
  if (!token) {
    return response;
  }
  localStorage.setItem(tokenStorageKey, token);
  return fetch(url, {
    ...options,
    headers: withAuthHeaders(options.headers || {}),
  });
}

function statusValue(value) {
  if (value === true) {
    return "Configured";
  }
  if (value === false) {
    return "Needs attention";
  }
  return value || "Not set";
}

function renderStatusItem(label, value, good = null) {
  const item = document.createElement("div");
  item.className = "status-item";
  if (good === true) {
    item.classList.add("ok");
  } else if (good === false) {
    item.classList.add("warn");
  }

  const labelNode = document.createElement("span");
  labelNode.textContent = label;
  const valueNode = document.createElement("strong");
  valueNode.textContent = statusValue(value);
  item.appendChild(labelNode);
  item.appendChild(valueNode);
  return item;
}

async function loadSystemStatus() {
  const [statusResponse, llmResponse] = await Promise.all([
    apiFetch("/status"),
    apiFetch("/llm/status"),
  ]);
  const status = await statusResponse.json();
  const llm = await llmResponse.json();
  const container = byId("system-status");
  container.innerHTML = "";
  container.appendChild(renderStatusItem("Storage", status.storage_provider));
  container.appendChild(renderStatusItem("Calendar", status.calendar_provider));
  container.appendChild(renderStatusItem("Model", llm.enabled ? llm.provider : "fallback"));
  container.appendChild(renderStatusItem("News summaries", status.news_summary_provider));
  container.appendChild(renderStatusItem("Email", status.email_configured, status.email_configured));
  container.appendChild(
    renderStatusItem("SSM secrets", status.ssm_secrets_configured, status.ssm_secrets_configured),
  );
  container.appendChild(renderStatusItem("Timezone", status.timezone));
}

async function loadPreferences() {
  const response = await apiFetch("/preferences");
  const data = await response.json();
  byId("sports-interests").value = joinList(data.sports_interests);
  byId("sports-teams").value = joinList(data.sports_teams);
  byId("finance-watchlist").value = joinList(data.finance_watchlist);
}

async function savePreferences(event) {
  event.preventDefault();
  const payload = {
    sports_interests: splitList(byId("sports-interests").value),
    sports_teams: splitList(byId("sports-teams").value),
    finance_watchlist: splitList(byId("finance-watchlist").value),
  };

  await apiFetch("/preferences", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await loadBrief();
}

function formatDateTime(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function renderScheduleResult(data) {
  const container = byId("schedule-output");
  container.innerHTML = "";

  const title = document.createElement("h3");
  title.textContent = data.status ? data.status[0].toUpperCase() + data.status.slice(1) : "Result";
  container.appendChild(title);

  if (data.task) {
    const task = document.createElement("p");
    task.textContent = data.task;
    container.appendChild(task);
  }

  const meta = [
    data.duration_minutes ? `${data.duration_minutes} minutes` : "",
    data.frequency_days_per_week ? `${data.frequency_days_per_week} days/week` : "",
  ].filter(Boolean);
  if (meta.length) {
    const metaNode = document.createElement("div");
    metaNode.className = "schedule-meta";
    metaNode.textContent = meta.join(" | ");
    container.appendChild(metaNode);
  }

  const slots = data.suggested_slots || [];
  if (slots.length) {
    const list = document.createElement("ol");
    list.className = "slot-list";
    slots.forEach((slot) => {
      const item = document.createElement("li");
      item.textContent = `${formatDateTime(slot.start)} to ${formatDateTime(slot.end)}`;
      list.appendChild(item);
    });
    container.appendChild(list);
  }

  if (data.learned_constraint) {
    const constraint = document.createElement("div");
    constraint.className = "schedule-note";
    constraint.textContent = `Learned: ${data.learned_constraint.reason}`;
    container.appendChild(constraint);
  }

  if (data.created_events && data.created_events.length) {
    const list = document.createElement("ul");
    list.className = "slot-list";
    data.created_events.forEach((event) => {
      const item = document.createElement("li");
      item.textContent = `${event.summary || "Scheduled"}: ${formatDateTime(event.start)} to ${formatDateTime(event.end)}`;
      list.appendChild(item);
    });
    container.appendChild(list);
  }

  if (data.event) {
    const item = document.createElement("div");
    item.className = "schedule-note";
    item.textContent = `${data.event.summary || "Scheduled"}: ${formatDateTime(data.event.start)} to ${formatDateTime(data.event.end)}`;
    container.appendChild(item);
  }

  if (data.detail) {
    const error = document.createElement("div");
    error.className = "schedule-note error";
    error.textContent = data.detail;
    container.appendChild(error);
  }
}

function renderSection(title, items) {
  const section = document.createElement("section");
  section.className = "brief-section";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const list = document.createElement("ul");

  items.forEach((item) => {
    const li = document.createElement("li");
    if (item && typeof item === "object") {
      li.className = "news-item";
      const source = document.createElement("div");
      source.className = "news-source";
      source.textContent = item.source || "News";

      const titleText = document.createElement("strong");
      titleText.textContent = item.title || "";

      const tags = [
        item.category,
        item.matched_ticker ? `Watchlist: ${item.matched_ticker}` : "",
        item.impact_area ? `Impact: ${item.impact_area}` : "",
        item.matched_interest ? `Matched: ${item.matched_interest}` : "",
      ].filter(Boolean);

      const summary = document.createElement("p");
      summary.textContent = item.summary || "";

      li.appendChild(source);
      li.appendChild(titleText);
      if (tags.length) {
        const tagRow = document.createElement("div");
        tagRow.className = "news-tags";
        tags.forEach((tag) => {
          const tagNode = document.createElement("span");
          tagNode.className = "news-tag";
          tagNode.textContent = tag;
          tagRow.appendChild(tagNode);
        });
        li.appendChild(tagRow);
      }
      li.appendChild(summary);

      if (item.link) {
        const link = document.createElement("a");
        link.href = item.link;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Read more";
        li.appendChild(link);
      }
    } else {
      li.textContent = item;
    }
    list.appendChild(li);
  });

  section.appendChild(heading);
  section.appendChild(list);
  return section;
}

async function loadBrief() {
  const response = await apiFetch("/brief/morning");
  const data = await response.json();
  const brief = byId("brief");
  brief.innerHTML = "";
  brief.appendChild(renderSection("News", data.news || []));
  brief.appendChild(renderSection("Sports", data.sports || []));
  brief.appendChild(renderSection("Finance", data.finance || []));
}

async function scheduleTask(event) {
  event.preventDefault();
  const response = await apiFetch("/schedule/task", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task: byId("task").value }),
  });
  const data = await response.json();
  renderScheduleResult(data);
}

async function proposeTask() {
  const response = await apiFetch("/schedule/propose", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task: byId("task").value }),
  });
  const data = await response.json();
  activeProposalId = data.proposal_id || null;
  byId("proposal-actions").classList.toggle("hidden", !activeProposalId);
  renderScheduleResult(data);
}

async function reviseProposal() {
  if (!activeProposalId) {
    return;
  }
  const response = await apiFetch(`/schedule/proposal/${activeProposalId}/revise`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback: byId("proposal-feedback").value }),
  });
  const data = await response.json();
  renderScheduleResult(data);
}

async function confirmProposal() {
  if (!activeProposalId) {
    return;
  }
  const response = await apiFetch(`/schedule/proposal/${activeProposalId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const data = await response.json();
  renderScheduleResult(data);
  activeProposalId = null;
  byId("proposal-actions").classList.add("hidden");
}

byId("preferences-form").addEventListener("submit", savePreferences);
byId("schedule-form").addEventListener("submit", scheduleTask);
byId("propose-task").addEventListener("click", proposeTask);
byId("revise-proposal").addEventListener("click", reviseProposal);
byId("confirm-proposal").addEventListener("click", confirmProposal);
byId("refresh-brief").addEventListener("click", loadBrief);
byId("refresh-status").addEventListener("click", loadSystemStatus);

async function init() {
  await loadPreferences();
  await loadSystemStatus();
  await loadBrief();
}

init();
