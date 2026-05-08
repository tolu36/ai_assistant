const byId = (id) => document.getElementById(id);

const splitList = (value) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const joinList = (items) => (items || []).join(", ");
let activeProposalId = null;

async function loadLlmStatus() {
  const response = await fetch("/llm/status");
  const data = await response.json();
  const status = data.enabled
    ? `LLM: ${data.provider_chain.join(" -> ")}, active: ${data.provider}`
    : "LLM: fallback parser active";
  byId("llm-status").textContent = status;
}

async function loadPreferences() {
  const response = await fetch("/preferences");
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

  await fetch("/preferences", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await loadBrief();
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

      const summary = document.createElement("p");
      summary.textContent = item.summary || "";

      li.appendChild(source);
      li.appendChild(titleText);
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
  const response = await fetch("/brief/morning");
  const data = await response.json();
  const brief = byId("brief");
  brief.innerHTML = "";
  brief.appendChild(renderSection("News", data.news || []));
  brief.appendChild(renderSection("Sports", data.sports || []));
  brief.appendChild(renderSection("Finance", data.finance || []));
}

async function scheduleTask(event) {
  event.preventDefault();
  const response = await fetch("/schedule/task", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task: byId("task").value }),
  });
  const data = await response.json();
  byId("schedule-output").textContent = JSON.stringify(data, null, 2);
}

async function proposeTask() {
  const response = await fetch("/schedule/propose", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task: byId("task").value }),
  });
  const data = await response.json();
  activeProposalId = data.proposal_id || null;
  byId("proposal-actions").classList.toggle("hidden", !activeProposalId);
  byId("schedule-output").textContent = JSON.stringify(data, null, 2);
}

async function reviseProposal() {
  if (!activeProposalId) {
    return;
  }
  const response = await fetch(`/schedule/proposal/${activeProposalId}/revise`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback: byId("proposal-feedback").value }),
  });
  const data = await response.json();
  byId("schedule-output").textContent = JSON.stringify(data, null, 2);
}

async function confirmProposal() {
  if (!activeProposalId) {
    return;
  }
  const response = await fetch(`/schedule/proposal/${activeProposalId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const data = await response.json();
  byId("schedule-output").textContent = JSON.stringify(data, null, 2);
  activeProposalId = null;
  byId("proposal-actions").classList.add("hidden");
}

byId("preferences-form").addEventListener("submit", savePreferences);
byId("schedule-form").addEventListener("submit", scheduleTask);
byId("propose-task").addEventListener("click", proposeTask);
byId("revise-proposal").addEventListener("click", reviseProposal);
byId("confirm-proposal").addEventListener("click", confirmProposal);
byId("refresh-brief").addEventListener("click", loadBrief);

loadPreferences();
loadLlmStatus();
loadBrief();
