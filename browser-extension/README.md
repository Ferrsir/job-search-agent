# Simone's Career Center Saver

This folder contains a free, unpacked Chrome extension and a Google Apps Script bridge for saving jobs from LinkedIn, Handshake, ATS pages, or company career pages into the Sheet-backed Career Center.

## Architecture

```text
Job page -> Chrome extension popup -> Google Apps Script web app -> Google Sheet Active Roles tab -> scheduled site refresh -> website
```

The extension does **not** contain Google service-account JSON, OAuth tokens, or GitHub credentials. It only stores:

- The deployed Apps Script web app URL.
- A shared submit secret.
- The dashboard URL.

## Files

- `job-save/`: unpacked Chrome extension.
- `apps-script/Code.gs`: Google Apps Script web app that validates the submit secret and appends rows to the backend Sheet.

## Install Locally

1. Open `chrome://extensions`.
2. Turn on **Developer mode**.
3. Click **Load unpacked**.
4. Select:

```text
browser-extension/job-save
```

5. Click the extension's **Details** page and pin it to the toolbar.

## Apps Script Setup

1. Open [script.google.com](https://script.google.com/).
2. Create a new project named `Career Center Job Saver`.
3. Paste the contents of `browser-extension/apps-script/Code.gs`.
4. Open **Project Settings > Script properties** and add:

```text
JOB_SEARCH_SHEET_ID = your backend Sheet ID
JOB_SEARCH_EXTENSION_SECRET = a long random passphrase
```

5. Click **Deploy > New deployment**.
6. Choose **Web app**.
7. Set **Execute as** to `Me`.
8. Set **Who has access** to `Anyone with the link`.
9. Deploy and copy the Web app URL ending in `/exec`.

Anyone with the link still needs the shared submit secret, so do not publish the secret.

## Configure The Extension

1. Right-click the extension icon.
2. Choose **Options**.
3. Paste:
   - Apps Script web app URL.
   - Submit secret.
   - Dashboard URL.
4. Click **Test**.
5. Click **Save Options**.

## Use

1. Open a job posting.
2. Click the extension.
3. Review/edit Role, Company, Location, URL, Fit Summary, and Main Requirements.
4. Click **Save to Sheet**.
5. The job appears on the website after the next `Sheet-Backed Site Refresh` run.

Browser-saved jobs default to `Score = 88`, so they appear in `Top Roles` after the next site refresh. If you choose `Great fit`, they save as `94`; if you choose `Right direction`, they save as `88`; if you choose `Wrong direction`, they save as `45`.

If you need it immediately, manually run the GitHub Action named `Sheet-Backed Site Refresh`.
