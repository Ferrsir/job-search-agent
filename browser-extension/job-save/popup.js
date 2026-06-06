const fields = ["title", "company", "location", "url", "fitSummary", "requirements", "feedback"];
const statusNode = document.getElementById("status");
const setupNotice = document.getElementById("setup-notice");
const saveButton = document.getElementById("save");

const setStatus = (message, kind = "") => {
  statusNode.textContent = message;
  statusNode.className = `status ${kind}`.trim();
};

const getSettings = () =>
  chrome.storage.local.get({
    endpointUrl: "",
    submitSecret: "",
    dashboardUrl: "https://gusim1.github.io/job-search-agent/"
  });

const setFormValues = (job) => {
  for (const field of fields) {
    const node = document.getElementById(field);
    if (node && job[field] !== undefined) node.value = job[field] || "";
  }
};

const collectFormValues = () => {
  const payload = {};
  for (const field of fields) payload[field] = document.getElementById(field).value.trim();
  payload.savedAt = new Date().toISOString();
  return payload;
};

const extractFromActiveTab = async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("No active tab found.");
  const [response] = await chrome.tabs.sendMessage(tab.id, { type: "extract-job" })
    .then((data) => [data])
    .catch(async () => {
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
      return [await chrome.tabs.sendMessage(tab.id, { type: "extract-job" })];
    });
  return response || {};
};

const saveJob = async (event) => {
  event.preventDefault();
  const settings = await getSettings();
  if (!settings.endpointUrl || !settings.submitSecret) {
    setStatus("Open Options and add the Apps Script endpoint plus submit secret.", "error");
    setupNotice.hidden = false;
    return;
  }

  saveButton.disabled = true;
  setStatus("Saving...");
  try {
    const payload = {
      secret: settings.submitSecret,
      job: collectFormValues()
    };
    const response = await fetch(settings.endpointUrl, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify(payload)
    });
    const text = await response.text();
    let result = {};
    try {
      result = JSON.parse(text);
    } catch {
      throw new Error(text || "Apps Script returned a non-JSON response.");
    }
    if (!result.ok) throw new Error(result.error || "The job was not saved.");
    setStatus(result.duplicate ? "Already in the Sheet. No duplicate row added." : "Saved to the Sheet. It will appear after the next site refresh.", "ok");
  } catch (error) {
    setStatus(error.message || "Could not save this job.", "error");
  } finally {
    saveButton.disabled = false;
  }
};

document.getElementById("job-form").addEventListener("submit", saveJob);
document.getElementById("options").addEventListener("click", () => chrome.runtime.openOptionsPage());

(async () => {
  const settings = await getSettings();
  setupNotice.hidden = Boolean(settings.endpointUrl && settings.submitSecret);
  try {
    const job = await extractFromActiveTab();
    setFormValues(job);
    setStatus("Review the fields, then save.");
  } catch (error) {
    setStatus("Could not auto-read this page. Fill the fields manually.", "error");
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.url) document.getElementById("url").value = tab.url;
    if (tab?.title) document.getElementById("title").value = tab.title;
  }
})();
