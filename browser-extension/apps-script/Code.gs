const CONFIG = {
  sheetIdProperty: "JOB_SEARCH_SHEET_ID",
  submitSecretProperty: "JOB_SEARCH_EXTENSION_SECRET",
  activeTabName: "Active Roles"
};

const HEADERS = [
  "ID",
  "Date Found",
  "Company",
  "Role",
  "Organization Type",
  "Sector",
  "Location Type",
  "City",
  "Work Mode",
  "Source",
  "URL",
  "Score",
  "Dedupe Key",
  "Fit Summary",
  "Main Requirements",
  "Geography",
  "Role Family",
  "Qualifications",
  "Salary Min",
  "Salary Max",
  "Salary Text",
  "Seniority",
  "Degree Requirement",
  "Clearance Requirement",
  "Contact Strength",
  "Network Summary",
  "First Reach Contacts",
  "Feedback",
  "Wrong Reasons",
  "Direction Reasons"
];

function doPost(event) {
  try {
    const body = JSON.parse((event.postData && event.postData.contents) || "{}");
    const props = PropertiesService.getScriptProperties();
    const expectedSecret = props.getProperty(CONFIG.submitSecretProperty);
    if (!expectedSecret || body.secret !== expectedSecret) {
      return json_({ ok: false, error: "Unauthorized." });
    }
    if (body.ping) return json_({ ok: true });

    const sheetId = props.getProperty(CONFIG.sheetIdProperty);
    if (!sheetId) return json_({ ok: false, error: "Missing JOB_SEARCH_SHEET_ID script property." });

    const job = normalizeJob_(body.job || {});
    if (!job.title || !job.company || !job.url) {
      return json_({ ok: false, error: "Role, company, and URL are required." });
    }

    const spreadsheet = SpreadsheetApp.openById(sheetId);
    const sheet = ensureSheet_(spreadsheet, CONFIG.activeTabName);
    const header = ensureHeaders_(sheet);
    const dedupeKey = dedupeKey_(job);
    if (hasDuplicate_(sheet, header, dedupeKey, job.url)) {
      return json_({ ok: true, duplicate: true, dedupeKey });
    }

    const row = rowForHeader_(header, job, dedupeKey);
    sheet.appendRow(row);
    return json_({ ok: true, duplicate: false, dedupeKey });
  } catch (error) {
    return json_({ ok: false, error: error && error.message ? error.message : String(error) });
  }
}

function normalizeJob_(job) {
  const location = clean_(job.location) || "Unknown";
  const feedback = clean_(job.feedback);
  const normalizedFeedback = feedback === "great" ? "Great Fit" : feedback === "right" ? "Right Direction" : feedback === "wrong" ? "Wrong Direction" : "";
  return {
    title: clean_(job.title),
    company: clean_(job.company),
    location,
    url: clean_(job.url),
    source: clean_(job.source) || "Browser Extension",
    fitSummary: clean_(job.fitSummary) || "Browser-saved role; prioritize review because it was manually selected.",
    requirements: clean_(job.requirements),
    feedback: normalizedFeedback,
    score: scoreForFeedback_(normalizedFeedback),
    dateFound: new Date()
  };
}

function ensureSheet_(spreadsheet, name) {
  return spreadsheet.getSheetByName(name) || spreadsheet.insertSheet(name);
}

function ensureHeaders_(sheet) {
  const lastColumn = Math.max(sheet.getLastColumn(), HEADERS.length);
  const current = sheet.getRange(1, 1, 1, lastColumn).getValues()[0];
  const normalized = current.map(normalizeHeader_);
  const missing = HEADERS.filter((header) => normalized.indexOf(normalizeHeader_(header)) === -1);
  const next = current.filter(String).concat(missing);
  if (next.length && next.join("|") !== current.slice(0, next.length).join("|")) {
    sheet.getRange(1, 1, 1, next.length).setValues([next]);
    sheet.setFrozenRows(1);
  }
  return headerMap_(next);
}

function rowForHeader_(header, job, dedupeKey) {
  const row = Array(Object.keys(header).length).fill("");
  set_(row, header, ["ID"], dedupeKey);
  set_(row, header, ["Date Found"], Utilities.formatDate(job.dateFound, Session.getScriptTimeZone(), "yyyy-MM-dd"));
  set_(row, header, ["Company"], job.company);
  set_(row, header, ["Role"], job.title);
  set_(row, header, ["City", "Location"], job.location);
  set_(row, header, ["Work Mode"], /remote/i.test(job.location) ? "Remote" : "");
  set_(row, header, ["Source"], job.source);
  set_(row, header, ["URL"], job.url);
  set_(row, header, ["Score"], String(job.score));
  set_(row, header, ["Dedupe Key"], dedupeKey);
  set_(row, header, ["Fit Summary"], job.fitSummary);
  set_(row, header, ["Main Requirements"], job.requirements);
  set_(row, header, ["Feedback"], job.feedback);
  return row;
}

function scoreForFeedback_(feedback) {
  if (feedback === "Great Fit") return 94;
  if (feedback === "Right Direction") return 88;
  if (feedback === "Wrong Direction") return 45;
  return 88;
}

function hasDuplicate_(sheet, header, dedupeKey, url) {
  const rowCount = sheet.getLastRow();
  if (rowCount < 2) return false;
  const values = sheet.getRange(2, 1, rowCount - 1, sheet.getLastColumn()).getValues();
  const dedupeIndex = indexFor_(header, ["Dedupe Key", "ID"]);
  const urlIndex = indexFor_(header, ["URL"]);
  return values.some((row) => {
    const existingKey = dedupeIndex >= 0 ? clean_(row[dedupeIndex]) : "";
    const existingUrl = urlIndex >= 0 ? clean_(row[urlIndex]) : "";
    return existingKey === dedupeKey || normalizeUrl_(existingUrl) === normalizeUrl_(url);
  });
}

function headerMap_(headers) {
  const map = {};
  headers.forEach((header, index) => {
    if (header) map[normalizeHeader_(header)] = index;
  });
  return map;
}

function set_(row, header, names, value) {
  const index = indexFor_(header, names);
  if (index >= 0) row[index] = value;
}

function indexFor_(header, names) {
  for (const name of names) {
    const index = header[normalizeHeader_(name)];
    if (index !== undefined) return index;
  }
  return -1;
}

function dedupeKey_(job) {
  const base = `${job.company}|${job.title}|${normalizeUrl_(job.url)}`.toLowerCase();
  return base.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 160);
}

function normalizeUrl_(url) {
  try {
    const parsed = new URL(url);
    ["trk", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"].forEach((key) => parsed.searchParams.delete(key));
    parsed.hash = "";
    return parsed.toString().replace(/\/$/, "");
  } catch (error) {
    return clean_(url);
  }
}

function normalizeHeader_(value) {
  return clean_(value).toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
}

function clean_(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function json_(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload)).setMimeType(ContentService.MimeType.JSON);
}
