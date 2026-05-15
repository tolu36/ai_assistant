const byId = (id) => document.getElementById(id);

const splitList = (value) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const joinList = (items) => (items || []).join(", ");
const tokenStorageKey = "personal_ai_assistant_app_token";
let activeProposalId = null;
let latestBriefData = null;
let currentUtterance = null;
let currentAudio = null;
let currentAudioUrl = null;
let currentAudioController = null;
let currentAudioChunks = [];
let currentAudioIndex = 0;
let currentAudioQueue = [];
let currentAudioQueueIndex = 0;
let currentSpeechText = "";
let ttsAudioEnabled = false;
let latestBriefAudioManifest = null;
let serviceWorkerRegistration = null;

function withAuthHeaders(headers = {}) {
  const token = localStorage.getItem(tokenStorageKey);
  return token ? { ...headers, "X-App-Token": token } : headers;
}

function promptForAppToken(force = false) {
  const existing = localStorage.getItem(tokenStorageKey);
  if (existing && !force) {
    return existing;
  }
  if (force) {
    localStorage.removeItem(tokenStorageKey);
  }
  const token = window.prompt("Enter app access token");
  if (!token) {
    return "";
  }
  localStorage.setItem(tokenStorageKey, token);
  return token;
}

async function apiFetch(url, options = {}) {
  try {
    const tokenBeforeRequest = localStorage.getItem(tokenStorageKey);
    const response = await fetch(url, {
      ...options,
      headers: withAuthHeaders(options.headers || {}),
    });
    if (response.status !== 401) {
      return response;
    }

    const token = promptForAppToken(Boolean(tokenBeforeRequest));
    if (!token) {
      return response;
    }
    return fetch(url, {
      ...options,
      headers: withAuthHeaders(options.headers || {}),
    });
  } catch (error) {
    throw new Error(
      "Could not reach the app server. Refresh the page; if this persists, check the hosted app URL.",
    );
  }
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

function notificationsSupported() {
  return (
    "Notification" in window &&
    "serviceWorker" in navigator &&
    "PushManager" in window
  );
}

function setNotificationStatus(message, type = "info") {
  const status = byId("notification-status");
  status.textContent = message;
  status.className = `notification-status ${type}`;
}

function updateNotificationButtons(state = "idle") {
  const enable = byId("enable-notifications");
  if (!enable) {
    return;
  }
  enable.disabled = state === "loading" || state === "unsupported";
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; i += 1) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

async function getServiceWorkerRegistration() {
  if (!("serviceWorker" in navigator)) {
    throw new Error("Service workers are not supported in this browser.");
  }
  if (serviceWorkerRegistration) {
    return serviceWorkerRegistration;
  }
  serviceWorkerRegistration = await navigator.serviceWorker.register("/service-worker.js");
  return navigator.serviceWorker.ready;
}

async function loadNotificationStatus() {
  if (!notificationsSupported()) {
    setNotificationStatus("Push notifications are not supported in this browser.", "error");
    updateNotificationButtons("unsupported");
    return;
  }

  updateNotificationButtons("loading");
  try {
    const [status, registration] = await Promise.all([
      fetchJson("/notifications/status"),
      getServiceWorkerRegistration(),
    ]);
    const subscription = await registration.pushManager.getSubscription();
    if (!status.enabled) {
      setNotificationStatus("Push notifications need VAPID keys in hosted config.", "error");
      updateNotificationButtons("idle");
      return;
    }
    if (subscription && Notification.permission === "granted") {
      setNotificationStatus("Enabled on this device.", "ok");
    } else if (Notification.permission === "denied") {
      setNotificationStatus("Notifications are blocked for this app.", "error");
    } else {
      setNotificationStatus("Ready to enable on this device.");
    }
    updateNotificationButtons("idle");
  } catch (error) {
    setNotificationStatus(error.message, "error");
    updateNotificationButtons("idle");
  }
}

async function enableNotifications() {
  if (!notificationsSupported()) {
    setNotificationStatus("Push notifications are not supported in this browser.", "error");
    updateNotificationButtons("unsupported");
    return;
  }

  updateNotificationButtons("loading");
  setNotificationStatus("Enabling notifications...");
  try {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setNotificationStatus("Notifications were not allowed.", "error");
      updateNotificationButtons("idle");
      return;
    }

    const registration = await getServiceWorkerRegistration();
    const keyData = await fetchJson("/notifications/vapid-public-key");
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(keyData.public_key),
      });
    }

    await fetchJson("/notifications/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(subscription.toJSON()),
    });
    setNotificationStatus("Enabled on this device.", "ok");
  } catch (error) {
    setNotificationStatus(error.message, "error");
  } finally {
    updateNotificationButtons("idle");
  }
}

function speechSupported() {
  return "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

function audioSupported() {
  return "Audio" in window && "URL" in window && "fetch" in window;
}

function setReadStatus(message, type = "info") {
  const status = byId("read-status");
  status.textContent = message;
  status.className = `read-status ${type}`;
}

function updateReadButtons(state = "idle") {
  const play = byId("read-play");
  const pause = byId("read-pause");
  const stop = byId("read-stop");
  play.disabled = state === "loading" || state === "speaking";
  pause.disabled = state === "idle" || state === "loading";
  stop.disabled = state === "idle";
  pause.textContent = state === "paused" ? "Resume" : "Pause";
}

function readAloudIsIdle() {
  return !currentAudio && !currentUtterance && !currentAudioController;
}

function cleanSpeechText(value) {
  return String(value || "")
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/\bETFs\b/g, "E.T.F.s")
    .replace(/\bETF\b/g, "E.T.F.")
    .replace(/\bLLMs\b/g, "L.L.M.s")
    .replace(/\bLLM\b/g, "L.L.M.")
    .replace(/\bRSS\b/g, "R.S.S.")
    .replace(/\bAI\b/g, "A.I.")
    .replace(/\bGDP\b/g, "G.D.P.")
    .replace(/\bCPI\b/g, "C.P.I.")
    .replace(/\bTSX\b/g, "T.S.X.")
    .replace(/\bS&P\b/g, "S and P")
    .replace(/\bCAD\/USD\b/g, "Canadian dollar to U.S. dollar")
    .replace(/\s+/g, " ")
    .trim();
}

function itemSpeechText(item) {
  if (!item) {
    return "";
  }
  if (typeof item !== "object") {
    return cleanSpeechText(item);
  }

  const parts = [];
  if (item.title && item.title !== "Daily Quote") {
    parts.push(item.title);
  }
  if (item.summary) {
    parts.push(item.summary);
  }
  if (item.reflection || item.prompt) {
    parts.push(`Reflection. ${item.reflection || item.prompt}`);
  }
  if (item.why_it_matters) {
    parts.push(`Why it matters. ${item.why_it_matters}`);
  }
  if (item.watch_for) {
    parts.push(`Watch for. ${item.watch_for}`);
  }
  return parts.map(cleanSpeechText).filter(Boolean).join(". ");
}

function sectionSpeechText(title, items) {
  const lines = (items || []).map(itemSpeechText).filter(Boolean);
  if (!lines.length) {
    return "";
  }
  return `${title}. ${lines.join(" ")}`;
}

function briefAudioManifestUrls(manifest, section) {
  if (!manifest || !manifest.tracks) {
    return [];
  }

  const sectionOrder = ["daily_quote", "news", "sports", "finance"];
  const keys = section && section !== "all" ? [section] : sectionOrder;
  return keys.flatMap((key) => {
    const track = manifest.tracks[key];
    if (!track || !Array.isArray(track.chunks)) {
      return [];
    }
    return track.chunks.map((chunk) => chunk.url).filter(Boolean);
  });
}

function dailyNoteSpeechText(items) {
  const item = (items || []).find((entry) => entry && typeof entry === "object");
  if (!item) {
    return "";
  }

  const parts = [];
  if (item.summary) {
    parts.push(`Daily note. ${item.summary}`);
  }
  if (item.reflection || item.prompt) {
    parts.push(`Reflection. ${item.reflection || item.prompt}`);
  }
  return parts.map(cleanSpeechText).filter(Boolean).join(" ");
}

function financeSpeechText(items) {
  const groups = financeGroups(items || []);
  const parts = [];
  const context = sectionSpeechText("Finance context", groups.context);
  const financialNews = sectionSpeechText(
    "Financial news and macro trends",
    groups.financialNews,
  );
  const marketWatch = sectionSpeechText(
    "Companies, stocks, and ETFs to watch",
    groups.marketWatch,
  );

  if (context) {
    parts.push(context);
  }
  if (financialNews) {
    parts.push(financialNews);
  }
  if (marketWatch) {
    parts.push(marketWatch);
  }
  return parts.length ? `Finance. ${parts.join(" ")}` : "";
}

function buildBriefSpeechText(data, section) {
  if (!data) {
    return "";
  }

  const builders = {
    daily_quote: () => dailyNoteSpeechText(data.daily_quote || []),
    news: () => sectionSpeechText("News", data.news || []),
    sports: () => sectionSpeechText("Sports", data.sports || []),
    finance: () => financeSpeechText(data.finance || []),
  };

  if (section && section !== "all" && builders[section]) {
    return builders[section]();
  }

  return ["daily_quote", "news", "sports", "finance"]
    .map((key) => builders[key]())
    .filter(Boolean)
    .join(" ");
}

function updateReadRateLabel() {
  const rate = Number.parseFloat(byId("read-rate").value || "1");
  byId("read-rate-value").textContent = `${rate.toFixed(2)}x`;
  if (currentAudio) {
    currentAudio.playbackRate = rate;
  }
}

function splitSpeechText(text, maxChars = 1100) {
  const clean = cleanSpeechText(text);
  const sentences = clean.match(/[^.!?]+[.!?]*/g) || [clean];
  const chunks = [];
  let current = "";

  sentences.forEach((sentence) => {
    const trimmed = sentence.trim();
    if (!trimmed) {
      return;
    }

    if (trimmed.length > maxChars) {
      const words = trimmed.split(/\s+/);
      let wordChunk = "";
      words.forEach((word) => {
        const candidate = wordChunk ? `${wordChunk} ${word}` : word;
        if (candidate.length > maxChars && wordChunk) {
          chunks.push(wordChunk);
          wordChunk = word;
        } else {
          wordChunk = candidate;
        }
      });
      if (wordChunk) {
        chunks.push(wordChunk);
      }
      return;
    }

    const candidate = current ? `${current} ${trimmed}` : trimmed;
    if (candidate.length > maxChars && current) {
      chunks.push(current);
      current = trimmed;
    } else {
      current = candidate;
    }
  });

  if (current) {
    chunks.push(current);
  }
  return chunks;
}

function clearCurrentAudio() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.removeAttribute("src");
    currentAudio.load();
    currentAudio = null;
  }
  if (currentAudioUrl) {
    URL.revokeObjectURL(currentAudioUrl);
    currentAudioUrl = null;
  }
}

function stopSpeech(showStatus = true) {
  if (speechSupported()) {
    window.speechSynthesis.cancel();
  }
  if (currentAudioController) {
    currentAudioController.abort();
    currentAudioController = null;
  }
  clearCurrentAudio();
  currentUtterance = null;
  currentAudioChunks = [];
  currentAudioIndex = 0;
  currentAudioQueue = [];
  currentAudioQueueIndex = 0;
  updateReadButtons("idle");
  if (showStatus) {
    setReadStatus("Stopped.");
  }
}

function toggleSpeechPause() {
  if (currentAudio) {
    if (currentAudio.paused) {
      currentAudio.play();
      updateReadButtons("speaking");
      setReadStatus("Playing high-quality audio.");
    } else {
      currentAudio.pause();
      updateReadButtons("paused");
      setReadStatus("Paused.");
    }
    return;
  }

  if (!speechSupported() || !currentUtterance) {
    return;
  }

  if (window.speechSynthesis.paused) {
    window.speechSynthesis.resume();
    updateReadButtons("speaking");
    setReadStatus("Reading.");
  } else if (window.speechSynthesis.speaking) {
    window.speechSynthesis.pause();
    updateReadButtons("paused");
    setReadStatus("Paused.");
  }
}

function playBrowserSpeech(text, statusMessage = "Using browser voice fallback.") {
  if (!speechSupported()) {
    setReadStatus("Read aloud is not supported in this browser.", "error");
    updateReadButtons("idle");
    return;
  }

  clearCurrentAudio();
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = Number.parseFloat(byId("read-rate").value || "1");
  utterance.pitch = 1;
  utterance.onstart = () => {
    updateReadButtons("speaking");
    setReadStatus(statusMessage);
  };
  utterance.onend = () => {
    currentUtterance = null;
    updateReadButtons("idle");
    setReadStatus("Finished.");
  };
  utterance.onerror = () => {
    currentUtterance = null;
    updateReadButtons("idle");
    setReadStatus("Could not read aloud.", "error");
  };

  currentUtterance = utterance;
  window.speechSynthesis.speak(utterance);
}

async function fetchSpeechAudio(text) {
  currentAudioController = new AbortController();
  try {
    const response = await apiFetch("/tts/speech", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal: currentAudioController.signal,
    });
    if (!response.ok) {
      let detail = `Request failed with ${response.status}`;
      try {
        const data = await response.json();
        detail = data.detail || detail;
      } catch {
        detail = response.statusText || detail;
      }
      throw new Error(detail);
    }
    return response.blob();
  } finally {
    currentAudioController = null;
  }
}

async function fetchSavedSpeechAudio(url) {
  currentAudioController = new AbortController();
  try {
    const response = await apiFetch(url, {
      signal: currentAudioController.signal,
    });
    if (!response.ok) {
      let detail = `Request failed with ${response.status}`;
      try {
        const data = await response.json();
        detail = data.detail || detail;
      } catch {
        detail = response.statusText || detail;
      }
      throw new Error(detail);
    }
    return response.blob();
  } finally {
    currentAudioController = null;
  }
}

async function playMistralAudioChunk() {
  if (currentAudioIndex >= currentAudioChunks.length) {
    updateReadButtons("idle");
    setReadStatus("Finished.");
    return;
  }

  const chunkNumber = currentAudioIndex + 1;
  setReadStatus(`Generating high-quality audio ${chunkNumber}/${currentAudioChunks.length}...`);
  updateReadButtons("loading");
  const blob = await fetchSpeechAudio(currentAudioChunks[currentAudioIndex]);
  clearCurrentAudio();

  currentAudioUrl = URL.createObjectURL(blob);
  currentAudio = new Audio(currentAudioUrl);
  currentAudio.playbackRate = Number.parseFloat(byId("read-rate").value || "1");
  currentAudio.onplay = () => {
    updateReadButtons("speaking");
    setReadStatus(`Playing high-quality audio ${chunkNumber}/${currentAudioChunks.length}.`);
  };
  currentAudio.onended = () => {
    clearCurrentAudio();
    currentAudioIndex += 1;
    playMistralAudioChunk().catch((error) => {
      if (error.name === "AbortError") {
        return;
      }
      setReadStatus("High-quality audio failed; using browser voice fallback.", "error");
      playBrowserSpeech(currentSpeechText);
    });
  };
  currentAudio.onerror = () => {
    clearCurrentAudio();
    setReadStatus("High-quality audio failed; using browser voice fallback.", "error");
    playBrowserSpeech(currentSpeechText);
  };

  await currentAudio.play();
}

async function playSavedAudioQueueChunk() {
  if (currentAudioQueueIndex >= currentAudioQueue.length) {
    updateReadButtons("idle");
    setReadStatus("Finished.");
    return;
  }

  const chunkNumber = currentAudioQueueIndex + 1;
  setReadStatus(`Loading saved Mistral audio ${chunkNumber}/${currentAudioQueue.length}...`);
  updateReadButtons("loading");
  const blob = await fetchSavedSpeechAudio(currentAudioQueue[currentAudioQueueIndex]);
  clearCurrentAudio();
  currentAudioUrl = URL.createObjectURL(blob);
  currentAudio = new Audio(currentAudioUrl);
  currentAudio.playbackRate = Number.parseFloat(byId("read-rate").value || "1");
  currentAudio.onplay = () => {
    updateReadButtons("speaking");
    setReadStatus(`Playing saved Mistral audio ${chunkNumber}/${currentAudioQueue.length}.`);
  };
  currentAudio.onended = () => {
    clearCurrentAudio();
    currentAudioQueueIndex += 1;
    playSavedAudioQueueChunk().catch((error) => {
      if (error.name === "AbortError") {
        return;
      }
      setReadStatus("Saved audio failed; generating audio now.", "error");
      playMistralAudioChunk().catch(() => playBrowserSpeech(currentSpeechText));
    });
  };
  currentAudio.onerror = () => {
    clearCurrentAudio();
    setReadStatus("Saved audio failed; generating audio now.", "error");
    playMistralAudioChunk().catch(() => playBrowserSpeech(currentSpeechText));
  };

  await currentAudio.play();
}

async function loadBriefAudioManifest(options = {}) {
  const quiet = Boolean(options.quiet);
  if (!latestBriefData || !latestBriefData.history_id || !ttsAudioEnabled) {
    latestBriefAudioManifest = null;
    return null;
  }

  try {
    const manifest = await fetchJson(`/tts/brief/${encodeURIComponent(latestBriefData.history_id)}`);
    latestBriefAudioManifest = manifest;
    if (!quiet && readAloudIsIdle()) {
      setReadStatus("Ready. Saved Mistral audio available.");
    }
    return manifest;
  } catch {
    latestBriefAudioManifest = null;
    if (!quiet && readAloudIsIdle()) {
      setReadStatus("Saved audio is still being generated; live Mistral audio is available.");
    }
    return null;
  }
}

async function playSavedBriefAudioIfAvailable(section) {
  const manifest = latestBriefAudioManifest || (await loadBriefAudioManifest({ quiet: true }));
  const urls = briefAudioManifestUrls(manifest, section);
  if (!urls.length) {
    return false;
  }

  currentAudioQueue = urls;
  currentAudioQueueIndex = 0;
  await playSavedAudioQueueChunk();
  return true;
}

async function playSpeech() {
  const selectedSection = byId("read-section").value;
  const text = buildBriefSpeechText(latestBriefData, selectedSection);
  if (!text) {
    setReadStatus("Load a brief before using read aloud.", "error");
    return;
  }

  stopSpeech(false);
  currentSpeechText = text;
  currentAudioChunks = splitSpeechText(text);
  currentAudioIndex = 0;

  if (!audioSupported()) {
    playBrowserSpeech(text, "Reading with browser voice.");
    return;
  }

  if (!ttsAudioEnabled) {
    await loadTtsStatus({ quiet: true });
  }

  if (!ttsAudioEnabled) {
    playBrowserSpeech(text, "Mistral API key not detected; using browser voice fallback.");
    return;
  }

  if (await playSavedBriefAudioIfAvailable(selectedSection)) {
    return;
  }

  try {
    await playMistralAudioChunk();
  } catch (error) {
    if (error.name === "AbortError") {
      return;
    }
    if (speechSupported()) {
      setReadStatus("High-quality audio unavailable; using browser voice fallback.", "error");
      playBrowserSpeech(text);
      return;
    }
    updateReadButtons("idle");
    setReadStatus(error.message || "Could not generate high-quality audio.", "error");
  }
}

function initReadAloud() {
  updateReadRateLabel();
  if (audioSupported()) {
    setReadStatus("Checking Mistral audio...");
  } else if (speechSupported()) {
    setReadStatus("Ready. Browser voice fallback only.");
  } else {
    setReadStatus("Read aloud is not supported in this browser.", "error");
  }
  updateReadButtons("idle");
}

async function loadTtsStatus(options = {}) {
  const quiet = Boolean(options.quiet);

  if (!audioSupported()) {
    ttsAudioEnabled = false;
    return;
  }

  try {
    const status = await fetchJson("/tts/status");
    ttsAudioEnabled = Boolean(status.enabled);
    if (!quiet && readAloudIsIdle()) {
      if (ttsAudioEnabled) {
        setReadStatus("Ready. Mistral audio enabled.");
      } else {
        setReadStatus("Mistral API key not detected; browser fallback available.", "error");
      }
    }
    if (ttsAudioEnabled && latestBriefData && latestBriefData.history_id && !latestBriefAudioManifest) {
      loadBriefAudioManifest({ quiet });
    }
  } catch (error) {
    ttsAudioEnabled = false;
    if (!quiet && readAloudIsIdle()) {
      setReadStatus("Could not verify Mistral audio; browser fallback available.", "error");
    }
  }
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
    container.appendChild(
      renderStatusItem(
        "Read aloud",
        status.tts_configured ? "Mistral audio" : "Browser fallback",
        status.tts_configured,
      ),
    );
    container.appendChild(
      renderStatusItem(
        "Push",
        status.push_configured ? "Configured" : "Needs VAPID",
        status.push_configured,
      ),
    );
    container.appendChild(renderStatusItem("News summaries", status.news_summary_provider));
    container.appendChild(renderStatusItem("Finance intelligence", status.finance_intelligence_provider));
    container.appendChild(
      renderStatusItem(
        "Daily note",
        status.daily_quote_enabled ? status.daily_note_provider : false,
        status.daily_quote_enabled,
      ),
    );
    container.appendChild(
      renderStatusItem("Email account", status.email_configured, status.email_configured),
    );
    container.appendChild(
      renderStatusItem("SSM secrets", status.ssm_secrets_configured, status.ssm_secrets_configured),
    );
    container.appendChild(renderStatusItem("Timezone", status.timezone));
    container.appendChild(
      renderStatusItem(
        "Email schedule",
        status.email_enabled ? "Enabled" : "Disabled",
        !status.email_enabled,
      ),
    );
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

function localDateString(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatBriefHistoryDate(briefDate, createdAt) {
  const localCreatedDate = localDateString(createdAt);
  if (!briefDate) {
    return localCreatedDate || "Saved brief";
  }
  if (!localCreatedDate || !/^\d{4}-\d{2}-\d{2}$/.test(briefDate)) {
    return briefDate;
  }

  const briefTime = new Date(`${briefDate}T00:00:00`).getTime();
  const localCreatedTime = new Date(`${localCreatedDate}T00:00:00`).getTime();
  const dayDiff = Math.round((briefTime - localCreatedTime) / 86400000);
  if (Math.abs(dayDiff) === 1) {
    return localCreatedDate;
  }
  return briefDate;
}

function hasBriefContent(data) {
  return ["daily_quote", "news", "sports", "finance"].some(
    (section) => Array.isArray(data[section]) && data[section].length > 0,
  );
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
  latestBriefData = data;
  latestBriefAudioManifest = null;
  const brief = byId("brief");
  brief.innerHTML = "";

  if (!hasBriefContent(data)) {
    brief.appendChild(
      createNotice(
        "This saved brief does not contain any brief content. Refresh the brief to generate a new saved copy.",
        "error",
      ),
    );
    return;
  }

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

  if (data.history_id && ttsAudioEnabled) {
    loadBriefAudioManifest({ quiet: false });
  }
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

async function loadInitialBrief() {
  const params = new URLSearchParams(window.location.search);
  const briefId = params.get("brief_id");
  if (!briefId) {
    await loadBrief();
    return;
  }

  const brief = byId("brief");
  brief.innerHTML = "";
  brief.appendChild(createNotice("Opening saved morning brief..."));

  try {
    const saved = await fetchJson(`/brief/history/${encodeURIComponent(briefId)}`);
    renderBriefData(saved.brief || {});
    window.history.replaceState({}, "", "/");
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
      title.textContent = formatBriefHistoryDate(entry.brief_date, entry.created_at);
      const meta = document.createElement("span");
      meta.textContent = formatDateTime(entry.created_at);
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
byId("read-play").addEventListener("click", playSpeech);
byId("read-pause").addEventListener("click", toggleSpeechPause);
byId("read-stop").addEventListener("click", () => stopSpeech());
byId("read-rate").addEventListener("input", updateReadRateLabel);
byId("enable-notifications").addEventListener("click", enableNotifications);
window.addEventListener("beforeunload", () => stopSpeech(false));

function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    return Promise.resolve(null);
  }

  return navigator.serviceWorker
    .register("/service-worker.js")
    .then((registration) => {
      serviceWorkerRegistration = registration;
      return registration;
    })
    .catch(() => null);
}

async function init() {
  initReadAloud();
  registerServiceWorker();
  await Promise.allSettled([
    loadPreferences(),
    loadSystemStatus(),
    loadTtsStatus(),
    loadInitialBrief(),
    loadNotificationStatus(),
  ]);
}

init();
