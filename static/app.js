const authBtn = document.getElementById("authBtn");
const logoutBtn = document.getElementById("logoutBtn");
const scheduleBtn = document.getElementById("scheduleBtn");
const listBtn = document.getElementById("listBtn");
const cancelBtn = document.getElementById("cancelBtn");
const rescheduleBtn = document.getElementById("rescheduleBtn");
const parseBtn = document.getElementById("parseBtn");
const voiceBtn = document.getElementById("voiceBtn");
const clearOutputBtn = document.getElementById("clearOutputBtn");
const output = document.getElementById("output");
const authStatus = document.getElementById("authStatus");
const toastRegion = document.getElementById("toastRegion");

const state = {
  email: localStorage.getItem("meet_assistant_email") || "",
};

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

const setBusy = (button, busy, label) => {
  if (!button) return;
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = label || "Working...";
    button.disabled = true;
    return;
  }
  button.textContent = button.dataset.label || button.textContent;
  button.disabled = false;
};

const showToast = ({ title, message, type = "info", url }) => {
  const toast = document.createElement("div");
  toast.className = `toast is-${type}`;
  toast.innerHTML = `
    <strong>${escapeHtml(title)}</strong>
    <p>${escapeHtml(message)}</p>
    ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">Open setup page</a>` : ""}
  `;
  toastRegion.appendChild(toast);
  setTimeout(() => toast.remove(), type === "error" ? 9000 : 5200);
};

const setAuthState = (email) => {
  state.email = email || "";
  if (state.email) {
    localStorage.setItem("meet_assistant_email", state.email);
    authStatus.textContent = `Connected: ${state.email}`;
    authStatus.classList.add("is-connected");
    logoutBtn.hidden = false;
  } else {
    localStorage.removeItem("meet_assistant_email");
    authStatus.textContent = "Not connected";
    authStatus.classList.remove("is-connected");
    logoutBtn.hidden = true;
  }
};

const getEmail = () => {
  const email = state.email.trim();
  if (!email) {
    throw new Error("Connect Google before using the assistant.");
  }
  return email;
};

const meetingIdentifierPayload = (value) => {
  const cleaned = value
    .trim()
    .replace(/^event\s*id\s*:\s*/i, "")
    .trim();
  if (!cleaned) {
    return { event_id: undefined, query: undefined };
  }
  const looksLikeGoogleEventId = /^[a-z0-9_@.-]{10,}$/i.test(cleaned);
  if (!/\s/.test(cleaned) && looksLikeGoogleEventId) {
    return { event_id: cleaned, query: undefined };
  }
  return { event_id: undefined, query: cleaned };
};

const friendlyError = (status, body) => {
  let parsed = null;
  try {
    parsed = JSON.parse(body);
  } catch {
    return { message: body || `Request failed with status ${status}.` };
  }

  const detail = parsed.detail;
  if (typeof detail === "string") {
    return { message: detail };
  }
  if (detail && typeof detail === "object") {
    return {
      message: detail.message || `Request failed with status ${status}.`,
      action: detail.action,
      url: detail.url,
      raw: detail.raw,
    };
  }
  return { message: parsed.message || `Request failed with status ${status}.` };
};

const fetchJson = async (url, options = {}) => {
  const response = await fetch(url, options);
  const text = await response.text();
  if (!response.ok) {
    const error = friendlyError(response.status, text);
    error.status = response.status;
    throw error;
  }
  return text ? JSON.parse(text) : {};
};

const formatDateTime = (value) => {
  if (!value) return "Time not set";
  const date = new Date(value.dateTime || value.date);
  if (Number.isNaN(date.getTime())) return value.dateTime || value.date || "Time not set";
  return date.toLocaleString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};

const renderOutput = (data) => {
  if (data && data.error) {
    output.innerHTML = `
      <div class="result-item result-error">
        <strong>${escapeHtml(data.error)}</strong>
        ${data.action ? `<span>${escapeHtml(data.action)}</span>` : ""}
        ${data.status ? `<span>Status: ${escapeHtml(data.status)}</span>` : ""}
        ${data.setup_url ? `<a href="${escapeHtml(data.setup_url)}" target="_blank" rel="noreferrer">Open setup page</a>` : ""}
      </div>
    `;
    return;
  }

  if (Array.isArray(data)) {
    if (!data.length) {
      output.textContent = "No upcoming meetings found.";
      return;
    }
    output.innerHTML = `<div class="result-list">${data.map((event) => `
      <article class="result-item">
        <strong>${escapeHtml(event.summary || "Untitled meeting")}</strong>
        <span>${escapeHtml(formatDateTime(event.start))} to ${escapeHtml(formatDateTime(event.end))}</span>
        <span>Event ID: ${escapeHtml(event.id || "Not available")}</span>
      </article>
    `).join("")}</div>`;
    return;
  }

  if (data && data.message && data.email) {
    output.innerHTML = `
      <div class="result-item">
        <strong>${escapeHtml(data.message)}</strong>
        <span>Account: ${escapeHtml(data.email)}</span>
      </div>
    `;
    return;
  }

  if (data && data.hangout_link) {
    output.innerHTML = `
      <div class="result-item">
        <strong>${escapeHtml(data.message || "Meeting scheduled.")}</strong>
        ${data.meeting ? `<span>Starts: ${escapeHtml(formatDateTime(data.meeting.start))}</span>` : ""}
        ${data.meeting ? `<span>Ends: ${escapeHtml(formatDateTime(data.meeting.end))}</span>` : ""}
        <span>Event ID: ${escapeHtml(data.event_id || data.meeting?.id || "Not available")}</span>
        <a href="${escapeHtml(data.hangout_link)}" target="_blank" rel="noreferrer">${escapeHtml(data.hangout_link)}</a>
      </div>
    `;
    return;
  }

  if (data && data.meeting) {
    const meeting = data.meeting;
    output.innerHTML = `
      <div class="result-item">
        <strong>${escapeHtml(data.message || "Meeting updated.")}</strong>
        <span>${escapeHtml(meeting.title || "Untitled meeting")}</span>
        <span>Starts: ${escapeHtml(formatDateTime(meeting.start))}</span>
        <span>Ends: ${escapeHtml(formatDateTime(meeting.end))}</span>
        <span>Event ID: ${escapeHtml(data.event_id || meeting.id || "Not available")}</span>
        ${meeting.meet_link ? `<a href="${escapeHtml(meeting.meet_link)}" target="_blank" rel="noreferrer">${escapeHtml(meeting.meet_link)}</a>` : ""}
      </div>
    `;
    return;
  }

  if (data && data.message && data.event_id) {
    output.innerHTML = `
      <div class="result-item">
        <strong>${escapeHtml(data.message)}</strong>
        <span>Event ID: ${escapeHtml(data.event_id)}</span>
      </div>
    `;
    return;
  }

  if (data && data.message) {
    output.innerHTML = `
      <div class="result-item">
        <strong>${escapeHtml(data.message)}</strong>
      </div>
    `;
    return;
  }

  output.textContent = JSON.stringify(data, null, 2);
};

const handleError = (error) => {
  const message = error.action ? `${error.message} ${error.action}` : error.message;
  const notFoundHint = error.status === 404
    ? "I could not find a matching meeting. Try the exact Event ID, or mention the title/person and date."
    : error.action;
  renderOutput({
    error: error.status === 404 ? "Meeting not found" : error.message || "Something went wrong.",
    action: notFoundHint,
    setup_url: error.url,
    status: error.status,
  });
  showToast({
    title: error.status === 403 ? "Permission or setup issue" : "Request failed",
    message,
    type: "error",
    url: error.url,
  });
};

const runScheduleFromParsed = async (parsed) => {
  const email = getEmail();
  if (!parsed.title || !parsed.date || !parsed.time) {
    document.getElementById("summary").value = parsed.title || "";
    document.getElementById("date").value = parsed.date || "";
    document.getElementById("time").value = parsed.time || "";
    document.getElementById("duration").value = parsed.duration || 30;
    document.querySelector('[data-panel="schedulePanel"]').click();
    throw new Error("I need a title, date, and time before I can schedule this meeting.");
  }
  const start = new Date(`${parsed.date}T${parsed.time}:00`);
  const end = new Date(start.getTime() + Number(parsed.duration || 30) * 60000);
  return fetchJson(`/events/schedule?email=${encodeURIComponent(email)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      summary: parsed.title,
      description: parsed.query || undefined,
      start_datetime: start.toISOString(),
      end_datetime: end.toISOString(),
      attendees: Array.isArray(parsed.attendees) ? parsed.attendees.map((emailAddress) => ({ email: emailAddress })) : [],
    }),
  });
};

const runCancelFromParsed = async (parsed) => {
  const email = getEmail();
  const identifier = parsed.event_id || parsed.query;
  if (!identifier) {
    throw new Error("Tell me which meeting to cancel, for example: Cancel my meeting with Ram tomorrow.");
  }
  return fetchJson(`/events/cancel?email=${encodeURIComponent(email)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...meetingIdentifierPayload(identifier), date: parsed.date || undefined }),
  });
};

const runRescheduleFromParsed = async (parsed) => {
  const email = getEmail();
  const identifier = parsed.event_id || parsed.query;
  if (!identifier || !parsed.date || !parsed.time) {
    document.getElementById("rescheduleQuery").value = identifier || "";
    document.getElementById("newDate").value = parsed.date || "";
    document.getElementById("newTime").value = parsed.time || "";
    document.getElementById("newDuration").value = parsed.duration || 30;
    document.querySelector('[data-panel="managePanel"]').click();
    throw new Error("I need the meeting name or ID, plus the new date and time, before I can reschedule.");
  }
  const start = new Date(`${parsed.date}T${parsed.time}:00`);
  const end = new Date(start.getTime() + Number(parsed.duration || 30) * 60000);
  return fetchJson(`/events/reschedule?email=${encodeURIComponent(email)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...meetingIdentifierPayload(identifier),
      date: parsed.date || undefined,
      new_start: start.toISOString(),
      new_end: end.toISOString(),
    }),
  });
};

document.querySelectorAll(".tool-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tool-tab").forEach((item) => item.classList.remove("is-active"));
    document.querySelectorAll(".tool-panel").forEach((panel) => panel.classList.remove("is-active"));
    tab.classList.add("is-active");
    document.getElementById(tab.dataset.panel).classList.add("is-active");
  });
});

authBtn.addEventListener("click", async () => {
  setBusy(authBtn, true, "Opening...");
  try {
    const data = await fetchJson("/auth/url");
    window.location.href = data.auth_url;
  } catch (error) {
    handleError(error);
    setBusy(authBtn, false);
  }
});

logoutBtn.addEventListener("click", async () => {
  setBusy(logoutBtn, true, "Logging out...");
  try {
    const email = state.email;
    await fetchJson(`/auth/logout${email ? `?email=${encodeURIComponent(email)}` : ""}`, {
      method: "POST",
    });
    setAuthState("");
    renderOutput({ message: "Logged out successfully." });
    showToast({ title: "Logged out", message: "Google credentials were removed from this app.", type: "success" });
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(logoutBtn, false);
  }
});

scheduleBtn.addEventListener("click", async () => {
  setBusy(scheduleBtn, true, "Scheduling...");
  try {
    const email = getEmail();
    const summary = document.getElementById("summary").value.trim();
    const description = document.getElementById("description").value.trim();
    const date = document.getElementById("date").value;
    const time = document.getElementById("time").value;
    const duration = Number(document.getElementById("duration").value);
    const attendees = document.getElementById("attendees").value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!summary || !date || !time || !duration) {
      throw new Error("Title, date, time, and duration are required.");
    }
    const start = new Date(`${date}T${time}:00`);
    const end = new Date(start.getTime() + duration * 60000);
    const data = await fetchJson(`/events/schedule?email=${encodeURIComponent(email)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        summary,
        description: description || undefined,
        start_datetime: start.toISOString(),
        end_datetime: end.toISOString(),
        attendees: attendees.map((emailAddress) => ({ email: emailAddress })),
      }),
    });
    renderOutput(data);
    showToast({ title: "Meeting scheduled", message: data.hangout_link || data.message, type: "success" });
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(scheduleBtn, false);
  }
});

listBtn.addEventListener("click", async () => {
  setBusy(listBtn, true, "Loading...");
  try {
    const email = getEmail();
    const data = await fetchJson(`/events/list?email=${encodeURIComponent(email)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_results: 10 }),
    });
    renderOutput(data);
    showToast({ title: "Upcoming meetings loaded", message: `${data.length} meeting(s) found.`, type: "success" });
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(listBtn, false);
  }
});

cancelBtn.addEventListener("click", async () => {
  setBusy(cancelBtn, true, "Cancelling...");
  try {
    const email = getEmail();
    const query = document.getElementById("cancelQuery").value.trim();
    if (!query) throw new Error("Provide an event ID or search text to cancel.");
    const data = await fetchJson(`/events/cancel?email=${encodeURIComponent(email)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(meetingIdentifierPayload(query)),
    });
    renderOutput(data);
    showToast({ title: "Meeting cancelled", message: data.message, type: "success" });
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(cancelBtn, false);
  }
});

rescheduleBtn.addEventListener("click", async () => {
  setBusy(rescheduleBtn, true, "Moving...");
  try {
    const email = getEmail();
    const query = document.getElementById("rescheduleQuery").value.trim();
    const date = document.getElementById("newDate").value;
    const time = document.getElementById("newTime").value;
    const duration = Number(document.getElementById("newDuration").value);
    if (!query || !date || !time || !duration) {
      throw new Error("Search text, new date, new time, and duration are required.");
    }
    const start = new Date(`${date}T${time}:00`);
    const end = new Date(start.getTime() + duration * 60000);
    const data = await fetchJson(`/events/reschedule?email=${encodeURIComponent(email)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...meetingIdentifierPayload(query),
        new_start: start.toISOString(),
        new_end: end.toISOString(),
      }),
    });
    renderOutput(data);
    showToast({ title: "Meeting moved", message: data.message, type: "success" });
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(rescheduleBtn, false);
  }
});

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let isListening = false;
let voiceTranscript = "";

const setVoiceButtonState = (label, listening = false) => {
  voiceBtn.classList.toggle("is-listening", listening);
  voiceBtn.setAttribute("aria-label", label);
  voiceBtn.setAttribute("title", label);
};

if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = true;
  recognition.continuous = false;

  recognition.addEventListener("start", () => {
    isListening = true;
    voiceTranscript = "";
    setVoiceButtonState("Listening. Click to stop voice input.", true);
    showToast({ title: "Voice input started", message: "Speak your meeting command.", type: "info" });
  });

  recognition.addEventListener("result", (event) => {
    const transcript = Array.from(event.results)
      .map((result) => result[0].transcript)
      .join(" ")
      .trim();
    voiceTranscript = transcript;
    document.getElementById("nlText").value = transcript;
  });

  recognition.addEventListener("end", () => {
    isListening = false;
    setVoiceButtonState("Start voice input");
    if (voiceTranscript.trim()) {
      runAssistant();
    }
  });

  recognition.addEventListener("error", (event) => {
    showToast({
      title: "Voice input unavailable",
      message: event.error === "not-allowed" ? "Allow microphone access in your browser." : `Speech recognition failed: ${event.error}`,
      type: "error",
    });
  });
} else {
  voiceBtn.disabled = true;
  setVoiceButtonState("Voice input unavailable");
}

voiceBtn.addEventListener("click", () => {
  if (!recognition) return;
  if (isListening) {
    recognition.stop();
    return;
  }
  recognition.start();
});

const runAssistant = async () => {
  setBusy(parseBtn, true, "Working...");
  try {
    const text = document.getElementById("nlText").value.trim();
    if (!text) throw new Error("Enter a meeting request to parse.");
    const parsed = await fetchJson("/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (parsed.action === "list") {
      const email = getEmail();
      const meetings = await fetchJson(`/events/list?email=${encodeURIComponent(email)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ max_results: 10, date: parsed.date || undefined }),
      });
      renderOutput(meetings);
      showToast({
        title: "Meetings loaded",
        message: parsed.date ? `Showing meetings for ${parsed.date}.` : "Showing upcoming meetings.",
        type: "success",
      });
      return;
    }
    if (parsed.action === "schedule") {
      const data = await runScheduleFromParsed(parsed);
      renderOutput(data);
      showToast({ title: "Meeting scheduled", message: data.hangout_link || data.message, type: "success" });
      return;
    }
    if (parsed.action === "cancel") {
      const data = await runCancelFromParsed(parsed);
      renderOutput(data);
      showToast({ title: "Meeting cancelled", message: data.message, type: "success" });
      return;
    }
    if (parsed.action === "reschedule") {
      const data = await runRescheduleFromParsed(parsed);
      renderOutput(data);
      showToast({ title: "Meeting moved", message: data.message, type: "success" });
      return;
    }
    renderOutput(parsed);
    showToast({ title: "Request parsed", message: "I parsed the request, but could not decide which action to run.", type: "warning" });
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(parseBtn, false);
  }
};

parseBtn.addEventListener("click", runAssistant);

clearOutputBtn.addEventListener("click", () => {
  output.textContent = "Ready.";
});

const verifyAuthState = async () => {
  if (!state.email) {
    setAuthState("");
    return;
  }
  try {
    const status = await fetchJson(`/auth/status?email=${encodeURIComponent(state.email)}`);
    if (status.authenticated) {
      setAuthState(status.email);
      return;
    }
    setAuthState("");
    showToast({
      title: "Reconnect Google",
      message: "The browser remembered an email, but the backend has no active Google credentials.",
      type: "warning",
    });
  } catch {
    setAuthState("");
  }
};

const applyAuthRedirect = () => {
  const params = new URLSearchParams(window.location.search);
  const auth = params.get("auth");
  const email = params.get("email");
  const message = params.get("message");

  if (email) {
    setAuthState(email);
  } else {
    setAuthState(state.email);
  }

  if (auth === "success") {
    showToast({ title: "Google connected", message: `Authenticated as ${email}.`, type: "success" });
    renderOutput({ message: "Google authentication successful.", email });
  }
  if (auth === "error") {
    showToast({ title: "Google authentication failed", message: message || "Try connecting again.", type: "error" });
    renderOutput({ error: message || "Google authentication failed." });
  }
  if (auth) {
    window.history.replaceState({}, document.title, window.location.pathname);
    return;
  }
  verifyAuthState();
};

applyAuthRedirect();
