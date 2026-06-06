const statusNode = document.getElementById("status");
const defaults = {
  endpointUrl: "",
  submitSecret: "",
  dashboardUrl: "https://gusim1.github.io/job-search-agent/"
};

const setStatus = (message, kind = "") => {
  statusNode.textContent = message;
  statusNode.className = `status ${kind}`.trim();
};

const readForm = () => ({
  endpointUrl: document.getElementById("endpointUrl").value.trim(),
  submitSecret: document.getElementById("submitSecret").value.trim(),
  dashboardUrl: document.getElementById("dashboardUrl").value.trim()
});

document.getElementById("options-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await chrome.storage.local.set(readForm());
  setStatus("Options saved.", "ok");
});

document.getElementById("test").addEventListener("click", async () => {
  const settings = readForm();
  if (!settings.endpointUrl || !settings.submitSecret) {
    setStatus("Add the endpoint and submit secret first.", "error");
    return;
  }
  setStatus("Testing...");
  try {
    const response = await fetch(settings.endpointUrl, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify({ secret: settings.submitSecret, ping: true })
    });
    const result = JSON.parse(await response.text());
    if (!result.ok) throw new Error(result.error || "Test failed.");
    setStatus("Connection works.", "ok");
  } catch (error) {
    setStatus(error.message || "Could not reach Apps Script.", "error");
  }
});

(async () => {
  const settings = await chrome.storage.local.get(defaults);
  for (const [key, value] of Object.entries(settings)) {
    const node = document.getElementById(key);
    if (node) node.value = value || "";
  }
})();
