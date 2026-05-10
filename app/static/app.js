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

async function fetchJson(url, options = {}) {
  const response = await apiFetch(url, options);
  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    throw new Error(data.detail || `Request failed with ${response.status}`);
  }
  return data;
}

function createNotice(message, type = "info") {
  const notice = document.createElement("div");
  notice.className = `notice ${type}`;
  notice.textContent = message;
  return notice;
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
  const container = byId("system-status");
  container.innerHTML = "";
  container.appendChild(createNotice("Checking system status..."));

  try {
    const [status, llm] = await Promise.all([
      fetchJson("/status"),
      fetchJson("/llm/status"),
    ]);

    container.innerHTML = "";
    container.appendChild(renderStatusItem("Storage", status.storage_provider));
    container.appendChild(renderStatusItem("Calendar", status.calendar_provider));
    container.appendChild(renderStatusItem("Model", llm.enabled ? llm.provider : "fallback"));
    container.appendChild(renderStatusItem("News summaries", status.news_summary_provider));
    container.appendChild(renderStatusItem("Finance intelligence", status.finance_intelligence_provider));
    container.appendChild(
      renderStatusItem(
        "Daily note",
        status.daily_quote_enabled ? status.daily_note_provider : false,
        status.daily_quote_enabled,
      ),
    );
    container.appendChild(renderStatusItem("Email", status.email_configured, status.email_configured));
    container.appendChild(
      renderStatusItem("SSM secrets", status.ssm_secrets_configured, status.ssm_secrets_configured),
    );
    container.appendChild(renderStatusItem("Timezone", status.timezone));
  } catch (error) {
    container.innerHTML = "";
    container.appendChild(createNotice(error.message, "error"));
  }
}

async function loadPreferences() {
  const data = await fetchJson("/preferences");
  byId("sports-interests").value = joinList(data.sports_interests);
  byId("sports-teams").value = joinList(data.sports_teams);
  byId("finance-topics").value = joinList(data.finance_topics);
  byId("finance-watchlist").value = joinList(data.finance_watchlist);
}

async function savePreferences(event) {
  event.preventDefault();
  const button = event.submitter;
  const originalLabel = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "Saving...";
  }

  const payload = {
    sports_interests: splitList(byId("sports-interests").value),
    sports_teams: splitList(byId("sports-teams").value),
    finance_topics: splitList(byId("finance-topics").value),
    finance_watchlist: splitList(byId("finance-watchlist").value),
  };

  try {
    await fetchJson("/preferences", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await loadBrief();
  } catch (error) {
    window.alert(error.message);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }
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

function renderMetaChips(values) {
  const chips = values.filter(Boolean);
  if (!chips.length) {
    return null;
  }

  const row = document.createElement("div");
  row.className = "meta-row";
  chips.forEach((value) => {
    const chip = document.createElement("span");
    chip.textContent = value;
    row.appendChild(chip);
  });
  return row;
}

function renderSlotCard(slot, index, label = "Option", action = null) {
  const card = document.createElement("article");
  card.className = "slot-card";

  const slotLabel = document.createElement("span");
  slotLabel.className = "slot-label";
  slotLabel.textContent = label === "Option" ? `${label} ${index + 1}` : label;

  const start = document.createElement("strong");
  start.textContent = formatDateTime(slot.start);

  const end = document.createElement("span");
  end.textContent = `Ends ${formatDateTime(slot.end)}`;

  card.appendChild(slotLabel);
  card.appendChild(start);
  card.appendChild(end);
  if (action) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = action.label;
    button.addEventListener("click", action.onClick);
    card.appendChild(button);
  }
  return card;
}

function renderScheduleResult(data) {
  const container = byId("schedule-output");
  container.innerHTML = "";

  const title = document.createElement("h3");
  title.textContent = data.status ? data.status[0].toUpperCase() + data.status.slice(1) : "Result";
  container.appendChild(title);

  if (data.detail) {
    container.appendChild(createNotice(data.detail, "error"));
    return;
  }

  if (data.task) {
    const task = document.createElement("p");
    task.className = "result-task";
    task.textContent = data.task;
    container.appendChild(task);
  }

  const meta = renderMetaChips([
    data.duration_minutes ? `${data.duration_minutes} minutes` : "",
    data.frequency_days_per_week ? `${data.frequency_days_per_week} days/week` : "",
  ]);
  if (meta) {
    container.appendChild(meta);
  }

  const slots = data.suggested_slots || [];
  if (slots.length) {
    const grid = document.createElement("div");
    grid.className = "slot-grid";
    slots.forEach((slot, index) => {
      const canConfirmOne = activeProposalId && ["proposal", "revised"].includes(data.status);
      grid.appendChild(
        renderSlotCard(
          slot,
          index,
          "Option",
          canConfirmOne
            ? {
                label: "Confirm This Time",
                onClick: () => confirmProposal([index]),
              }
            : null,
        ),
      );
    });
    container.appendChild(grid);
  }

  if (data.learned_constraint) {
    const constraint = document.createElement("div");
    constraint.className = "schedule-note";
    constraint.textContent = `Learned preference: ${data.learned_constraint.reason}`;
    container.appendChild(constraint);
  }

  if (data.created_events && data.created_events.length) {
    const grid = document.createElement("div");
    grid.className = "slot-grid";
    data.created_events.forEach((event, index) => {
      grid.appendChild(
        renderSlotCard(
          {
            start: event.start,
            end: event.end,
          },
          index,
          event.summary || "Scheduled",
        ),
      );
    });
    container.appendChild(grid);
  }

  if (data.event) {
    const note = document.createElement("div");
    note.className = "schedule-note ok";
    note.textContent = `${data.event.summary || "Scheduled"}: ${formatDateTime(data.event.start)} to ${formatDateTime(data.event.end)}`;
    container.appendChild(note);
  }
}

function tagsForItem(item) {
  return [
    item.category,
    item.matched_ticker ? `Watchlist: ${item.matched_ticker}` : "",
    item.impact_area ? `Impact: ${item.impact_area}` : "",
    item.matched_interest ? `Matched: ${item.matched_interest}` : "",
  ].filter(Boolean);
}

function appendTags(container, tags) {
  if (!tags.length) {
    return;
  }
  const tagRow = document.createElement("div");
  tagRow.className = "news-tags";
  tags.forEach((tag) => {
    const tagNode = document.createElement("span");
    tagNode.className = "news-tag";
    tagNode.textContent = tag;
    tagRow.appendChild(tagNode);
  });
  container.appendChild(tagRow);
}

function appendDetail(container, label, value) {
  if (!value) {
    return;
  }
  const detail = document.createElement("p");
  detail.className = "news-detail";
  const detailLabel = document.createElement("strong");
  detailLabel.textContent = `${label}: `;
  detail.appendChild(detailLabel);
  detail.appendChild(document.createTextNode(value));
  container.appendChild(detail);
}

function renderReadMore(linkValue) {
  if (!linkValue) {
    return null;
  }
  const link = document.createElement("a");
  link.href = linkValue;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.className = "read-more";
  link.textContent = "Read more";
  return link;
}

function renderBriefCard(item, fallbackSource = "News") {
  if (!item || typeof item !== "object") {
    const line = document.createElement("div");
    line.className = "brief-line";
    line.textContent = item || "";
    return line;
  }

  const card = document.createElement("article");
  card.className = "brief-card";

  const source = document.createElement("div");
  source.className = "news-source";
  source.textContent = item.source || fallbackSource;

  const title = document.createElement("h4");
  title.textContent = item.title || "";

  const summary = document.createElement("p");
  summary.textContent = item.summary || "";

  card.appendChild(source);
  card.appendChild(title);
  appendTags(card, tagsForItem(item));
  if (item.summary) {
    card.appendChild(summary);
  }
  appendDetail(card, "Reflection", item.reflection || item.prompt);
  appendDetail(card, "Why it matters", item.why_it_matters);
  appendDetail(card, "Watch for", item.watch_for);

  const readMore = renderReadMore(item.link);
  if (readMore) {
    card.appendChild(readMore);
  }

  return card;
}

function renderDailyNote(items) {
  const item = (items || []).find((entry) => entry && typeof entry === "object");
  if (!item) {
    return null;
  }

  const section = document.createElement("section");
  section.className = "daily-note";

  const label = document.createElement("div");
  label.className = "daily-label";
  label.textContent = "Daily Quote";

  const quote = document.createElement("p");
  quote.className = "daily-quote";
  quote.textContent = item.summary || "";

  const reflection = document.createElement("div");
  reflection.className = "daily-reflection";
  const reflectionLabel = document.createElement("strong");
  reflectionLabel.textContent = "Reflection";
  const reflectionText = document.createElement("span");
  reflectionText.textContent = item.reflection || item.prompt || "";
  reflection.appendChild(reflectionLabel);
  reflection.appendChild(reflectionText);

  section.appendChild(label);
  section.appendChild(quote);
  if (reflectionText.textContent) {
    section.appendChild(reflection);
  }
  return section;
}

function renderSection(title, items, fallbackSource = title) {
  const section = document.createElement("section");
  section.className = "brief-section";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const grid = document.createElement("div");
  grid.className = "brief-card-grid";

  if (!items || !items.length) {
    grid.appendChild(createNotice(`${title} is not available right now.`));
  } else {
    items.forEach((item) => grid.appendChild(renderBriefCard(item, fallbackSource)));
  }

  section.appendChild(heading);
  section.appendChild(grid);
  return section;
}

function financeGroups(items) {
  const groups = {
    context: [],
    financialNews: [],
    marketWatch: [],
  };

  (items || []).forEach((item) => {
    if (!item || typeof item !== "object") {
      groups.context.push(item);
    } else if (item.section === "financial_news") {
      groups.financialNews.push(item);
    } else if (item.section === "market_watch") {
      groups.marketWatch.push(item);
    } else if (item.category === "Financial news" || item.impact_area) {
      groups.financialNews.push(item);
    } else {
      groups.marketWatch.push(item);
    }
  });

  return groups;
}

function appendFinanceGroup(section, title, items) {
  if (!items.length) {
    return;
  }
  const group = document.createElement("div");
  group.className = "finance-group";
  const heading = document.createElement("h4");
  heading.textContent = title;
  const grid = document.createElement("div");
  grid.className = "brief-card-grid";
  items.forEach((item) => grid.appendChild(renderBriefCard(item, "Finance")));
  group.appendChild(heading);
  group.appendChild(grid);
  section.appendChild(group);
}

function renderFinanceSection(items) {
  const section = document.createElement("section");
  section.className = "brief-section finance-section";
  const heading = document.createElement("h3");
  heading.textContent = "Finance";
  section.appendChild(heading);

  const groups = financeGroups(items);
  if (groups.context.length) {
    const stack = document.createElement("div");
    stack.className = "finance-context";
    groups.context.forEach((line) => {
      const item = document.createElement("div");
      item.textContent = line;
      stack.appendChild(item);
    });
    section.appendChild(stack);
  }

  appendFinanceGroup(
    section,
    "Financial News and Macro Trends",
    groups.financialNews,
  );
  appendFinanceGroup(
    section,
    "Companies, Stocks, and ETFs to Watch",
    groups.marketWatch,
  );

  if (!items || !items.length) {
    section.appendChild(createNotice("Finance is not available right now."));
  }
  return section;
}

function renderBriefNotices(notices) {
  const cleanNotices = (notices || []).filter((notice) => notice && notice.title);
  if (!cleanNotices.length) {
    return null;
  }

  const section = document.createElement("section");
  section.className = "brief-notices";
  const heading = document.createElement("h3");
  heading.textContent = "Source Health";
  section.appendChild(heading);

  const grid = document.createElement("div");
  grid.className = "notice-grid";
  cleanNotices.slice(0, 6).forEach((notice) => {
    const item = document.createElement("div");
    item.className = `notice ${notice.severity || "info"}`;
    const title = document.createElement("strong");
    title.textContent = notice.title;
    item.appendChild(title);
    if (notice.detail) {
      const detail = document.createElement("span");
      detail.textContent = notice.detail;
      item.appendChild(detail);
    }
    grid.appendChild(item);
  });
  section.appendChild(grid);
  return section;
}

function renderBriefData(data) {
  const brief = byId("brief");
  brief.innerHTML = "";
  const dailyNote = renderDailyNote(data.daily_quote || []);
  if (dailyNote) {
    brief.appendChild(dailyNote);
  }
  const notices = renderBriefNotices(data.notices || []);
  if (notices) {
    brief.appendChild(notices);
  }
  brief.appendChild(renderSection("News", data.news || [], "News"));
  brief.appendChild(renderSection("Sports", data.sports || [], "Sports"));
  brief.appendChild(renderFinanceSection(data.finance || []));
}

async function loadBrief() {
  const brief = byId("brief");
  brief.innerHTML = "";
  brief.appendChild(createNotice("Fetching morning brief..."));

  try {
    const data = await fetchJson("/brief/morning");
    renderBriefData(data);
  } catch (error) {
    brief.innerHTML = "";
    brief.appendChild(createNotice(error.message, "error"));
  }
}

async function loadBriefHistory() {
  const container = byId("brief-history");
  container.innerHTML = "";
  container.appendChild(createNotice("Loading saved briefs..."));

  try {
    const history = await fetchJson("/brief/history?limit=10");
    container.innerHTML = "";
    if (!history.length) {
      container.appendChild(createNotice("No saved briefs yet."));
      return;
    }

    history.forEach((entry) => {
      const row = document.createElement("article");
      row.className = "history-item";

      const text = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = entry.brief_date || "Saved brief";
      const meta = document.createElement("span");
      meta.textContent = entry.created_at || "";
      text.appendChild(title);
      text.appendChild(meta);

      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Open";
      button.addEventListener("click", async () => {
        button.disabled = true;
        button.textContent = "Opening...";
        try {
          const saved = await fetchJson(`/brief/history/${entry.id}`);
          renderBriefData(saved.brief || {});
          window.scrollTo({ top: 0, behavior: "smooth" });
        } catch (error) {
          window.alert(error.message);
        } finally {
          button.disabled = false;
          button.textContent = "Open";
        }
      });

      row.appendChild(text);
      row.appendChild(button);
      container.appendChild(row);
    });
  } catch (error) {
    container.innerHTML = "";
    container.appendChild(createNotice(error.message, "error"));
  }
}

async function scheduleTask(event) {
  event.preventDefault();
  const container = byId("schedule-output");
  container.innerHTML = "";
  container.appendChild(createNotice("Scheduling task..."));

  try {
    const data = await fetchJson("/schedule/task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: byId("task").value }),
    });
    renderScheduleResult(data);
  } catch (error) {
    container.innerHTML = "";
    container.appendChild(createNotice(error.message, "error"));
  }
}

async function proposeTask() {
  const container = byId("schedule-output");
  container.innerHTML = "";
  container.appendChild(createNotice("Finding available times..."));

  try {
    const data = await fetchJson("/schedule/propose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: byId("task").value }),
    });
    activeProposalId = data.proposal_id || null;
    byId("proposal-actions").classList.toggle("hidden", !activeProposalId);
    renderScheduleResult(data);
  } catch (error) {
    activeProposalId = null;
    byId("proposal-actions").classList.add("hidden");
    container.innerHTML = "";
    container.appendChild(createNotice(error.message, "error"));
  }
}

async function reviseProposal() {
  if (!activeProposalId) {
    return;
  }
  const container = byId("schedule-output");
  container.innerHTML = "";
  container.appendChild(createNotice("Revising proposal..."));

  try {
    const data = await fetchJson(`/schedule/proposal/${activeProposalId}/revise`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feedback: byId("proposal-feedback").value }),
    });
    renderScheduleResult(data);
  } catch (error) {
    container.innerHTML = "";
    container.appendChild(createNotice(error.message, "error"));
  }
}

async function confirmProposal(slotIndexes = null) {
  if (!activeProposalId) {
    return;
  }
  const container = byId("schedule-output");
  container.innerHTML = "";
  container.appendChild(createNotice("Confirming schedule..."));

  try {
    const data = await fetchJson(`/schedule/proposal/${activeProposalId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(slotIndexes ? { slot_indexes: slotIndexes } : {}),
    });
    renderScheduleResult(data);
    activeProposalId = null;
    byId("proposal-actions").classList.add("hidden");
  } catch (error) {
    container.innerHTML = "";
    container.appendChild(createNotice(error.message, "error"));
  }
}

byId("preferences-form").addEventListener("submit", savePreferences);
byId("schedule-form").addEventListener("submit", scheduleTask);
byId("propose-task").addEventListener("click", proposeTask);
byId("revise-proposal").addEventListener("click", reviseProposal);
byId("confirm-proposal").addEventListener("click", () => confirmProposal());
byId("refresh-brief").addEventListener("click", loadBrief);
byId("refresh-status").addEventListener("click", loadSystemStatus);
byId("load-history").addEventListener("click", loadBriefHistory);

async function init() {
  await Promise.allSettled([loadPreferences(), loadSystemStatus(), loadBrief()]);
}

init();
