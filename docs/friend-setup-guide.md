# Standard Job Search Agent Setup Guide

This guide lets a friend create their own version of the job-search agent with the same infrastructure:

- Google Sheet as the backend source of truth.
- GitHub Actions as the automation runner.
- GitHub Pages as the live website.
- Gmail labels as the intake path for LinkedIn and Handshake alerts.
- Free public job-board sync every other day.
- Optional Chrome extension intake for saving individual roles while browsing.
- Weekly HTML newsletter sent by Gmail.
- Browser-based preference questionnaire, role feedback, analytics, and application-packet prompts.
- Optional ChatGPT Task for recurring no-API-cost web research.

The fastest setup is to fork this repository, create a Google Sheet backend, connect GitHub secrets, and run the included Actions.

## 1. Inputs Needed From Each Friend

Ask each friend to fill this out before setup starts.

```text
Full name:
First name:
Initials:
Primary email for weekly brief:
GitHub username:
Preferred site title, e.g. "Alex's Career Center":
One-line profile summary for the sidebar:

Top locations:
Locations to avoid:
Preferred work modes:
Target compensation range:

Preferred role types:
Role types to avoid:
Preferred sectors/industries:
Target company types:
Seniority target:
Hard constraints, e.g. visa, citizenship, degree, clearance, relocation:

LinkedIn job-alert searches they will create:
Handshake job-alert searches they will create:
Public company/ATS/careers URLs to monitor:

Path to LinkedIn data export on their computer, optional:
Paths to current resume and representative cover-letter examples, optional:
ChatGPT project link for application-material generation, optional:
```

## 2. Accounts And Folders

Each friend needs:

- A GitHub account.
- A Google account with Gmail, Google Drive, Google Sheets, and Google Cloud access.
- A LinkedIn account.
- A Handshake account if they use Handshake.
- A ChatGPT account if they want the no-API recurring Task workflow or application-material prompts.

Recommended Codex/ChatGPT connections:

- GitHub: required if Codex will inspect Actions, push setup changes, or manage repository settings.
- Google Drive: recommended for finding the backend Sheet and context folder.
- Gmail: recommended for checking whether LinkedIn and Handshake alerts are labeled correctly.
- Browser or Chrome: useful for testing the local site, Google Cloud setup screens, and GitHub Pages.
- Chrome: required only if the friend wants the optional browser-extension job saver.
- Build Web Data Visualization: already useful for the analytics/map/dashboard layer; install/use it when changing charts, maps, or dashboards.

Recommended ChatGPT project context:

- Current resume.
- Strongest cover-letter examples.
- A short application-materials style guide.
- The downloaded preference questionnaire HTML intake file.
- A link to the live dashboard.
- A link to the backend Sheet if the user is comfortable granting ChatGPT access.

Minimum ChatGPT capabilities for the recurring Task:

- Tasks enabled.
- Access to browse/research the web.
- Google Drive or Google Sheets connector access if the Task should update the Sheet directly. Without this, it should return a copy/paste table.

Create this Google Drive folder structure:

```text
Job Search Agent/
  Backend/
    Job Search Backend Google Sheet
  Context/
    Current Resume
    Cover Letter Examples
    Style Guide
  LinkedIn Exports/
  Generated Application Packets/
```

Do not put private credentials in GitHub, Drive shares, or the public website.

## 2A. Preference Questionnaire Handoff

The live dashboard publishes a separate preference page:

```text
https://GITHUB_USERNAME.github.io/job-search-agent/preferences.html
```

The friend should:

1. Open `preferences.html`.
2. Click **Start fresh** if the page contains default answers from a template.
3. Fill out the rendered questionnaire. Each question includes a short explanation of why it matters.
4. Click **Download intake HTML**.
5. Save the downloaded file in the Drive folder:

```text
Job Search Agent/Context/
```

6. Upload the downloaded HTML file to ChatGPT or Codex as setup context.

Use this prompt when re-uploading the completed intake file:

```text
I uploaded my completed Job Search Agent preference intake HTML.
Please read the visible answers and the embedded JSON.
Use it to configure my job-search-agent fork:

- summarize my preferred roles, locations, sectors, seniority, compensation, constraints, and avoid rules
- propose GitHub Actions variables for JOB_SEARCH_PROFILE_SUMMARY and JOB_SEARCH_APPLICATION_CONTEXT
- propose Gmail/LinkedIn/Handshake job-alert search language
- propose public-source company/ATS URLs to monitor
- identify any answers that create hard filters versus soft scoring preferences
- do not invent missing facts; ask only for truly necessary missing setup inputs
```

If the friend later changes direction, they can reopen `preferences.html`, update answers, download a new intake HTML file, and upload the replacement file to ChatGPT/Codex.

## 3. Create The Google Sheet Backend

Create a Google Sheet named:

```text
Job Search Agent Backend
```

Add these tabs:

```text
Active Roles
Rejected Notable
Calibration Examples
Source List
```

Use these headers for `Active Roles` and `Rejected Notable`:

```text
ID
Date Found
Company
Role
Organization Type
Sector
Location Type
City
Work Mode
Source
URL
Score
Dedupe Key
Fit Summary
Main Requirements
Geography
Role Family
Qualifications
Salary Min
Salary Max
Salary Text
Seniority
Degree Requirement
Clearance Requirement
Contact Strength
Network Summary
First Reach Contacts
Feedback
Wrong Reasons
Direction Reasons
```

Importable header files are also included:

- [`docs/sheet-templates/active_roles_headers.csv`](sheet-templates/active_roles_headers.csv)
- [`docs/sheet-templates/rejected_notable_headers.csv`](sheet-templates/rejected_notable_headers.csv)
- [`docs/sheet-templates/calibration_examples_headers.csv`](sheet-templates/calibration_examples_headers.csv)
- [`docs/sheet-templates/source_list_headers.csv`](sheet-templates/source_list_headers.csv)

Use these headers for `Calibration Examples`:

```text
Company
Role
URL
Feedback
Wrong Reasons
Direction Reasons
Notes
```

Use these headers for `Source List`:

```text
Name
URL
Notes
Active
```

Paste public careers, Greenhouse, Lever, Ashby, Pinpoint, Workday, sitemap, or RSS URLs into `Source List`. Set `Active` to `TRUE`.

Copy the Sheet ID from the URL. In this example, the Sheet ID is the long middle part:

```text
https://docs.google.com/spreadsheets/d/SHEET_ID_IS_HERE/edit
```

## 3A. Optional Browser Extension Intake

Use this if the friend wants to save a job directly from LinkedIn, Handshake, an ATS page, or a company career site while browsing.

The flow is:

```text
Job page -> Chrome extension -> Google Apps Script web app -> Google Sheet Active Roles -> website after refresh
```

This keeps Google service-account JSON, OAuth tokens, and GitHub credentials out of the extension.

### Create The Apps Script Bridge

1. Open [script.google.com](https://script.google.com/).
2. Create a new project named `Career Center Job Saver`.
3. Copy the code from:

```text
browser-extension/apps-script/Code.gs
```

4. Paste it into the Apps Script editor.
5. Open **Project Settings > Script properties**.
6. Add:

```text
JOB_SEARCH_SHEET_ID = PASTE_BACKEND_SHEET_ID
JOB_SEARCH_EXTENSION_SECRET = PASTE_LONG_RANDOM_SECRET
```

`JOB_SEARCH_EXTENSION_SECRET` should be a long random phrase. It is not the Google Sheet ID, not a Google API key, and not a GitHub token.

7. Click **Deploy > New deployment**.
8. Choose **Web app**.
9. Set **Execute as** to `Me`.
10. Set **Who has access** to `Anyone with the link`.
11. Deploy and copy the Web app URL ending in `/exec`.

Anyone with the URL still needs the shared submit secret, so do not publish the secret.

### Install The Extension

1. Open Chrome.
2. Go to:

```text
chrome://extensions
```

3. Turn on **Developer mode**.
4. Click **Load unpacked**.
5. Select:

```text
browser-extension/job-save
```

6. Pin the extension to the Chrome toolbar.
7. Right-click the extension icon and choose **Options**.
8. Paste:
   - Apps Script web app URL.
   - Submit secret.
   - Dashboard URL.
9. Click **Test**.
10. Click **Save Options**.

### Use The Extension

1. Open a job posting.
2. Click the extension icon.
3. Review or edit:
   - Role
   - Company
   - Location
   - URL
   - Why it may fit
   - Main requirements
   - Initial status
4. Click **Save to Sheet**.
5. Run or wait for `Sheet-Backed Site Refresh`.

The row is appended to `Active Roles`. Browser-saved jobs default to `Score = 88`, so they appear in `Top Roles` after the next site refresh. If the user chooses `Great fit`, the row saves as `94`; `Right direction` saves as `88`; `Wrong direction` saves as `45`. If the role is a duplicate by URL or dedupe key, Apps Script returns a duplicate success and does not add another row.

## 4. Fork And Configure GitHub

1. Open the source repository.
2. Click **Fork**.
3. Name the fork `job-search-agent`.
4. In the fork, go to **Settings > Pages**.
5. Set **Build and deployment > Source** to **GitHub Actions**.
6. Your dashboard URL will be:

```text
https://GITHUB_USERNAME.github.io/job-search-agent/
```

## 4A. Visual Identity And Design System

The current website and newsletter use the warm-paper Career Center design system:

- Light dashboard surface with coral, teal, and lime accents.
- Compact data-room cards for weekly signals, filters, analytics, and role review.
- Matching dark HTML newsletter for the weekly email brief.
- Comet logo assets in `assets/`.

The design-system source files are:

```text
templates/weekly_digest.html.j2
templates/weekly_email.html.j2
templates/preferences.html.j2
assets/logo-comet-1024.png
assets/logo-comet-icon-1024.png
```

For a friend setup, update the profile variables rather than redesigning from scratch:

```text
JOB_SEARCH_USER_FIRST_NAME
JOB_SEARCH_USER_FULL_NAME
JOB_SEARCH_USER_INITIALS
JOB_SEARCH_SITE_TITLE
JOB_SEARCH_SITE_SUBTITLE
JOB_SEARCH_PROFILE_SUMMARY
JOB_SEARCH_DASHBOARD_URL
```

If the friend has their own logo, replace the two logo files with the same filenames and rerun `Sheet-Backed Site Refresh`.

## 5. Create Google Credentials

Create a Google Cloud project named `job-search-agent`.

Enable APIs:

- Google Sheets API
- Gmail API
- Google Drive API, optional but useful for future Drive automation

### Sheets Service Account

1. In Google Cloud, go to **IAM & Admin > Service Accounts**.
2. Create a service account named `job-search-agent`.
3. Create a JSON key and download it.
4. Open the JSON file in a text editor.
5. Copy the service-account email from `client_email`.
6. Share the backend Google Sheet with that service-account email as **Editor**.

The service-account JSON goes into GitHub as `GOOGLE_APPLICATION_CREDENTIALS_JSON`.

### Gmail OAuth Token

1. In Google Cloud, go to **Google Auth Platform**.
2. Configure the OAuth app as **External** in testing mode.
3. Add the friend's Gmail address as a test user.
4. Create an OAuth client. For local token generation, choose **Desktop app**.
5. Download the OAuth client file.
6. Use the local token-generation flow from this repo or Codex to create an authorized-user token with Gmail scopes.

The GitHub secret `GOOGLE_OAUTH_TOKEN_JSON` must be the raw authorized-user token JSON. It is not the OAuth client download, not a file path, and not a single token string. It should contain fields like:

```json
{
  "token": "...",
  "refresh_token": "...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "...apps.googleusercontent.com",
  "client_secret": "...",
  "scopes": ["https://www.googleapis.com/auth/gmail.compose"]
}
```

## 6. GitHub Secrets And Variables

In the fork, go to **Settings > Secrets and variables > Actions**.

Add these **Secrets**:

```text
GOOGLE_SHEET_ID
GOOGLE_APPLICATION_CREDENTIALS_JSON
GOOGLE_OAUTH_TOKEN_JSON
GMAIL_TO
```

Optional secret:

```text
OPENAI_API_KEY
```

Only add `OPENAI_API_KEY` if the friend chooses paid API research. The default setup does not need it.

Add these **Variables**:

```text
JOB_SEARCH_USER_FIRST_NAME
JOB_SEARCH_USER_FULL_NAME
JOB_SEARCH_USER_INITIALS
JOB_SEARCH_SITE_TITLE
JOB_SEARCH_SITE_SUBTITLE
JOB_SEARCH_PROFILE_SUMMARY
JOB_SEARCH_DASHBOARD_URL
JOB_SEARCH_APPLICATION_CONTEXT
GMAIL_SEARCH_QUERY
ENABLE_PUBLIC_SOURCE_SEARCH
PUBLIC_SOURCE_URLS
PUBLIC_SYNC_DRY_RUN
```

Optional variables:

```text
LINKEDIN_DATA_DIRS
FEEDBACK_EXPORT_PATH
OPENAI_RESEARCH_MODEL
RESEARCH_MIN_JOBS
RESEARCH_MIN_GREAT_FITS
RESEARCH_TIMEOUT_SECONDS
```

Recommended values:

```text
ENABLE_PUBLIC_SOURCE_SEARCH=true
PUBLIC_SYNC_DRY_RUN=false
JOB_SEARCH_DASHBOARD_URL=https://GITHUB_USERNAME.github.io/job-search-agent/
```

`PUBLIC_SOURCE_URLS` is a comma-separated list, for example:

```text
https://boards.greenhouse.io/company,https://jobs.lever.co/company,https://jobs.ashbyhq.com/company
```

If the friend has GitHub CLI installed and authenticated, they can set non-secret variables from Terminal:

```bash
gh variable set JOB_SEARCH_USER_FIRST_NAME --repo GITHUB_USERNAME/job-search-agent --body "Alex"
gh variable set JOB_SEARCH_USER_FULL_NAME --repo GITHUB_USERNAME/job-search-agent --body "Alex Example"
gh variable set JOB_SEARCH_USER_INITIALS --repo GITHUB_USERNAME/job-search-agent --body "AE"
gh variable set JOB_SEARCH_SITE_TITLE --repo GITHUB_USERNAME/job-search-agent --body "Alex's Career Center"
gh variable set JOB_SEARCH_SITE_SUBTITLE --repo GITHUB_USERNAME/job-search-agent --body "Career Center"
gh variable set JOB_SEARCH_PROFILE_SUMMARY --repo GITHUB_USERNAME/job-search-agent --body "Strategy, finance, policy, and technology"
gh variable set JOB_SEARCH_DASHBOARD_URL --repo GITHUB_USERNAME/job-search-agent --body "https://GITHUB_USERNAME.github.io/job-search-agent/"
gh variable set GMAIL_SEARCH_QUERY --repo GITHUB_USERNAME/job-search-agent --body 'label:"Job Search Agent" newer_than:14d'
gh variable set ENABLE_PUBLIC_SOURCE_SEARCH --repo GITHUB_USERNAME/job-search-agent --body "true"
gh variable set PUBLIC_SYNC_DRY_RUN --repo GITHUB_USERNAME/job-search-agent --body "false"
```

Set secrets without printing values in chat:

```bash
gh secret set GOOGLE_SHEET_ID --repo GITHUB_USERNAME/job-search-agent --body "PASTE_SHEET_ID"
gh secret set GMAIL_TO --repo GITHUB_USERNAME/job-search-agent --body "friend@example.com"
gh secret set GOOGLE_APPLICATION_CREDENTIALS_JSON --repo GITHUB_USERNAME/job-search-agent < /path/to/service-account.json
gh secret set GOOGLE_OAUTH_TOKEN_JSON --repo GITHUB_USERNAME/job-search-agent < /path/to/gmail-authorized-user-token.json
```

## 7. Gmail Label And Filter

Create a Gmail label:

```text
Job Search Agent
```

Use this broad filter to catch LinkedIn and Handshake alerts:

```text
(from:(jobs-noreply@linkedin.com OR jobs-listings@linkedin.com OR jobalerts-noreply@linkedin.com OR *@mail.joinhandshake.com OR *@notifications.joinhandshake.com)
 OR subject:("new jobs similar to" OR "jobs similar to" OR "new jobs for" OR "job alert" OR "recommended jobs" OR "jobs you may be interested in"))
```

In Gmail filter settings:

- Apply label: `Job Search Agent`
- Never send to Spam
- Do not automatically archive unless the friend wants a quiet inbox

Set the GitHub variable:

```text
GMAIL_SEARCH_QUERY=label:"Job Search Agent" newer_than:14d
```

## 8. LinkedIn And Handshake Alerts

The agent does not scrape LinkedIn or Handshake behind logins. Those systems should feed the agent through Gmail alerts.

Create LinkedIn job alerts for:

- Each preferred role family.
- Each preferred city.
- Remote roles.
- A few broader searches that discover adjacent roles.

Example LinkedIn searches:

```text
Strategic Partnerships Manager Austin
Business Development Manager Dallas
Strategy Associate Remote
Investment Analyst Austin
Corporate Development Associate Dallas
Government Affairs Manager Remote
Research Analyst Austin
```

Create Handshake alerts for similar searches, especially school-affiliated opportunities.

When a LinkedIn or Handshake alert has interesting roles, the agent will try to find a public company/ATS version of that posting. If no public page exists, it will use the alert body and mark requirements for manual review.

## 9. ChatGPT Task For No-API Research

Use this if the friend wants recurring GPT-powered research without paying for OpenAI API calls.

Create a ChatGPT Task that runs every other day. Use this prompt and replace the bracketed placeholders:

```text
Every other day, research current publicly available job postings for [FULL NAME] and update the job-search backend Google Sheet.

Goal:
Find at least 5 current roles, with at least 1 Great Fit.

Backend:
Use the Google Sheet named "[SHEET NAME]" or this Sheet link: [GOOGLE SHEET URL].
Append successful results to the Active Roles tab.
If a result clearly violates an avoid rule, append it to Rejected Notable instead.
If you cannot update the sheet directly, return a copy/paste-ready table and say clearly that sheet update failed.

Expected row shape:
- ID
- Date Found
- Company
- Role
- Organization Type
- Sector
- Location Type
- City
- Work Mode
- Source
- URL
- Score
- Dedupe Key
- Fit Summary
- Main Requirements
- Geography
- Role Family
- Qualifications
- Salary Min
- Salary Max
- Salary Text
- Seniority
- Degree Requirement
- Clearance Requirement

Use this dedupe key format:
normalized company + "|" + normalized title + "|" + normalized URL

Search sources:
- Public company career pages
- Greenhouse
- Lever
- Ashby
- Workday
- Public ATS pages
- Public company job pages

Do not scrape LinkedIn directly.
Do not bypass logins or access controls.
LinkedIn and Handshake should enter through email alerts, not direct scraping.

Preferences:
- Locations: [PREFERRED LOCATIONS]
- Strong roles: [PREFERRED ROLE TYPES]
- Sectors: [PREFERRED SECTORS]
- Avoid: [AVOID RULES]
- Seniority: [SENIORITY TARGET]
- Compensation: [COMPENSATION TARGET]
- Hard constraints: [HARD CONSTRAINTS]

Scoring:
- Use a 100-point rubric.
- Great Fit should generally score 75+.
- Possible Fit should generally score 62-74.
- Weak Fit should score below 62.
- Reject roles that violate hard constraints.

Success criteria:
Consider the task successful only if you find at least 5 roles and at least 1 Great Fit.
Otherwise, report failure and explain what limited the search.

Final response:
Summarize:
- How many roles were found
- How many were Great Fit
- Which rows were appended
- Any rows skipped as duplicates
- Whether the task met the success criteria
```

## 10. Codex Prompts For Setup

Give these prompts to Codex inside the forked repository.

### Prompt 1: Personalize The Fork

```text
I forked this job-search-agent repo for my own job search.
Use my details below to configure the project for me without committing secrets:

Full name:
First name:
Initials:
Dashboard URL:
Profile summary:
Primary email:
Google Sheet ID:
Preferred locations:
Preferred roles:
Preferred sectors:
Avoid rules:
Public source URLs:

Please update docs or local env examples as needed, verify tests pass, and tell me exactly which GitHub Secrets and Variables to set.
```

### Prompt 1A: Check Required Plugins And Connections

```text
I am setting up the job-search-agent for myself.
Please check which Codex/ChatGPT connectors are available or missing for this setup:

- GitHub for repo and Actions work
- Google Drive for Docs/Sheets context
- Gmail for job alert intake validation
- Browser or Chrome for local/GitHub Pages testing
- Chrome for installing and testing the optional browser-extension job saver
- Build Web Data Visualization for dashboard/chart/map changes

Tell me what each connection is used for, which are required versus optional, and exactly what I should authenticate next. Do not ask for or print secrets.
```

### Prompt 2: Build My Sheet Schema

```text
Create a Google-Sheet-ready backend schema for my job-search agent.
Use the expected tabs Active Roles, Rejected Notable, Calibration Examples, and Source List.
Give me exact headers to paste into each tab and a short explanation of which columns are required versus optional.
```

### Prompt 3: Validate My GitHub Actions Setup

```text
Check this repo's GitHub Actions setup for the job-search agent.
Confirm that GitHub Pages publishes from Actions, that the Sheet-backed site refresh can run, that the free public job sync can run every other day, and that the weekly brief workflow has all required secrets.
Do not print any secret values.
```

### Prompt 4: Set Up Browser Job Saver

```text
Help me set up the optional Chrome extension intake for the job-search-agent.
Use browser-extension/job-save as the unpacked extension and browser-extension/apps-script/Code.gs as the Google Apps Script bridge.
Walk me through Apps Script properties, deployment, Chrome extension loading, and the extension Options page.
Do not ask me to paste secrets into chat. Tell me where each secret goes.
```

### Prompt 5: Generate My Application Context Packet

```text
I uploaded my current resume and several old cover letters.
Evaluate which examples are strongest for style, create a concise application-materials style guide, and produce a downloadable context packet I can upload to my ChatGPT project.
The goal is to generate tailored resumes and cover letters that sound like me and do not look AI-generated.
```

### Prompt 6: Troubleshoot Intake

```text
My Google Sheet has new jobs but the website/newsletter is not reflecting them.
Please inspect the Sheet-backed site workflow, the Sheet headers, the latest Actions logs, and the site renderer.
Find whether the issue is credentials, headers, stale GitHub Pages deployment, browser-extension Apps Script intake, parsing, filtering, or localStorage feedback state.
Fix what can be fixed in the repo and give me exact next steps for anything external.
```

## 11. First Run Checklist

Run these Actions manually from GitHub:

1. `Sheet-Backed Site Refresh`
2. `Free Public Job Sync`
3. `Email Weekly Brief`

Expected outcomes:

- The Pages site opens at `https://GITHUB_USERNAME.github.io/job-search-agent/`.
- The preference questionnaire opens from the dashboard.
- The optional Chrome extension can save a test role to `Active Roles` if configured.
- Jobs from the Sheet appear in the dashboard.
- Public-source sync appends deduped roles to the Sheet if source URLs are configured.
- Weekly email arrives as a rendered HTML newsletter.

If the email workflow fails with `GOOGLE_OAUTH_TOKEN_JSON must contain raw JSON`, the secret is wrong. Replace it with the authorized-user token JSON, not the OAuth client download or a local file path.

## 12. Maintenance Rhythm

Every week:

- Review new roles on the site.
- Mark `Great Fit`, `Right Direction`, or `Wrong Direction`.
- Export feedback if you want to feed it into local calibration.
- Add or remove public source URLs in the Sheet `Source List`.
- Check that LinkedIn and Handshake alerts are still sending to Gmail.

Every month:

- Remove stale roles or mark them expired.
- Revisit preferences.
- Add better cover-letter/resume examples to the ChatGPT project context.
- Audit source balance so one sector does not crowd out better-fit opportunities.
