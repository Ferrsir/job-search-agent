# Job Search Agent

Python 3.11+ automation for a personalized job-search intelligence pipeline. It reads Gmail job alerts, parses LinkedIn and Handshake roles, monitors approved public career/source URLs, deduplicates and scores jobs against the personalized rubric, writes new records to Google Sheets, publishes an updated role dashboard, and generates a weekly email rundown.

The Google Sheet is the backend source of truth. The website is the always-current review surface. The weekly digest email is a recap. The MVP avoids direct LinkedIn scraping: LinkedIn and Handshake enter through Gmail job-alert emails.

You can also save individual roles while browsing with the included unpacked Chrome extension in [`browser-extension/`](browser-extension/). It captures the current job page, lets you review or edit the fields, and sends the role to the Sheet through a Google Apps Script web app. The extension does not store Google service-account credentials.

To set up a standardized version for a friend, start with [`docs/friend-setup-guide.md`](docs/friend-setup-guide.md). It lists every required input, account, connector, GitHub secret, Google credential, Gmail filter, LinkedIn/Handshake alert, ChatGPT Task prompt, and Codex prompt needed to reach the same operating setup.

## Backend

Canonical Google Sheet:

https://docs.google.com/spreadsheets/d/1hUdPtfQY4Fo6iZ9pDYWyWrJT2lCht2LeR7QPI5KsrsA/edit?usp=sharing

Expected tabs include `Active Roles` and `Rejected Notable`. The site renderer reads the Sheet by header name, including the richer backend columns such as `Company`, `Role`, `City`, `Source`, `URL`, `Score`, and `Fit Summary`. When new rows are appended, the agent also maintains analysis-ready columns: `Geography`, `Role Family`, `Qualifications`, `Salary Min`, `Salary Max`, `Salary Text`, `Seniority`, `Degree Requirement`, `Clearance Requirement`, `Work Mode`, and `Contact Strength`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Create a Google Cloud project, enable the Gmail API and Google Sheets API, and configure credentials:

1. For Gmail, create an OAuth desktop or web client and generate an authorized-user token JSON with `gmail.readonly` and `gmail.compose`. `GOOGLE_OAUTH_TOKEN_JSON` must be the raw token JSON containing fields such as `token`, `refresh_token`, `client_id`, `client_secret`, and `scopes`; do not set it to the downloaded OAuth client file path.
2. For Sheets, create a service account, share the backend Sheet with the service-account email, and store the service-account JSON in `GOOGLE_APPLICATION_CREDENTIALS_JSON`.
3. Never commit credential files or JSON. Put JSON values in local `.env` or GitHub Actions secrets.

Useful environment variables:

```bash
DRY_RUN=true
JOB_SEARCH_USER_FIRST_NAME=Simone
JOB_SEARCH_USER_FULL_NAME="Simone Montandon"
JOB_SEARCH_USER_INITIALS=SM
JOB_SEARCH_SITE_TITLE="Simone's Career Center"
JOB_SEARCH_SITE_SUBTITLE="Career Center"
JOB_SEARCH_PROFILE_SUMMARY="Strategy, capital, policy, and dual-use technology"
JOB_SEARCH_DASHBOARD_URL=https://gusim1.github.io/job-search-agent/
JOB_SEARCH_APPLICATION_CONTEXT="Use the uploaded resume, cover-letter examples, and style guide as the source of truth. Do not invent personal facts."
GOOGLE_SHEET_ID=1hUdPtfQY4Fo6iZ9pDYWyWrJT2lCht2LeR7QPI5KsrsA
GMAIL_TO=simone@montandon.it
GMAIL_SEARCH_QUERY='label:"Job Search Agent" newer_than:14d'
FEEDBACK_EXPORT_PATH=./job-search-feedback.json
LINKEDIN_DATA_DIRS='/Users/simonemontandon/Downloads/Pull One'
ENABLE_PUBLIC_SOURCE_SEARCH=false
PUBLIC_SOURCE_URLS='https://example.com/careers,https://jobs.example.com'
GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account",...}'
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
GOOGLE_OAUTH_TOKEN_JSON='{"token":"...","refresh_token":"..."}'
```

Recommended Gmail filter for finance, capital, strategy, and partnerships alerts:

```text
(from:(jobs-noreply@linkedin.com OR jobs-listings@linkedin.com OR jobalerts-noreply@linkedin.com OR *@mail.joinhandshake.com OR *@notifications.joinhandshake.com)
 OR subject:("new jobs similar to" OR "jobs similar to" OR "new jobs for" OR "job alert" OR "recommended jobs" OR "jobs you may be interested in"))
 AND (
   subject:(investment OR finance OR "strategic finance" OR "corporate development" OR "venture capital" OR "private equity" OR "growth equity" OR "capital markets" OR "investor relations" OR FP&A OR "business development" OR partnerships OR strategy OR "strategic partner" OR "market intelligence" OR "research analyst")
   OR ("investment analyst" OR "venture capital" OR "private capital" OR "strategic finance" OR "corporate development" OR "market intelligence" OR "strategic partnerships" OR "business development")
 )
```

Apply the label `Job Search Agent`; optionally also apply `Job Search Agent/Finance Strategy`.

## Run

```bash
job-search-agent
```

Dry run is the default. It reads Gmail, builds an HTML dashboard/rundown under `artifacts/`, and logs what would be appended or drafted. Set `DRY_RUN=false` only after reviewing dry-run output.

To render the website from the Google Sheet backend only:

```bash
job-search-site
```

To render the website with local LinkedIn network context for first reaches:

```bash
LINKEDIN_DATA_DIRS="/Users/simonemontandon/Downloads/Pull One" job-search-site
```

To send the Sheet-backed weekly email brief:

```bash
DRY_RUN=false job-search-brief
```

To pull free public-source jobs into the Sheet without touching Gmail or OpenAI:

```bash
DRY_RUN=false job-search-public-sync
```

To backfill analysis-ready fields for existing Sheet rows:

```bash
job-search-backfill-analysis
```

To save jobs from the browser, install the unpacked Chrome extension from:

```text
browser-extension/job-save
```

Configure it with the Apps Script endpoint created from [`browser-extension/apps-script/Code.gs`](browser-extension/apps-script/Code.gs). Full instructions are in [`browser-extension/README.md`](browser-extension/README.md).

To build a ChatGPT-ready application packet for a job you want to apply to:

```bash
job-search-apply --list-jobs
job-search-apply --job-id "paste-job-id-here"
```

This creates a tailored prompt under `artifacts/application_packets/` using the Sheet job context plus local `.docx` resume and cover-letter examples. It does not call the OpenAI API unless you explicitly pass `--generate`. See [`docs/application-materials.md`](docs/application-materials.md).

## Website

The generated HTML site is the main dashboard for reviewing roles:

- Retake or edit the career-preference profile used for calibration notes.
- Filter roles by location, minimum score, feedback status, and text search.
- Mark each job as `Great fit`, `Right direction`, or `Wrong direction`. If the same role appears in multiple tabs, the feedback state follows every copy.
- Export preferences and feedback as `job-search-feedback.json`.
- Review an `Analytics` tab that summarizes role demand by geography, top hiring companies by geography, strongest first-reach paths, qualifications in demand, role-family mix, and salary signals when postings expose compensation.

The Analytics tab intentionally uses standardized buckets rather than raw job titles. Job types are forced into a small taxonomy such as `Partnerships / BD`, `Strategy / BizOps`, `Investment / Finance`, `Policy / Government`, `Research / Intelligence`, `Program / Operations`, `Contracts / Legal`, and `Communications / Marketing`. Rows with packed URLs or clearly technical/non-target titles are excluded from aggregate charts and counted in the cleanup queue instead.

If `LINKEDIN_DATA_DIRS` points to a LinkedIn data export folder, the dashboard and email also show a sanitized `First reach context` block for matching jobs. The importer uses `Connections.csv`, `Company Follows.csv`, `SearchQueries.csv`, saved jobs, applications, skills, and profile text to recommend likely first-reach contacts and network signals. Raw LinkedIn exports and email addresses should stay local and should not be committed to the repository. If you want network recommendations to persist in the Sheet, add optional columns named `Network Summary` and `First Reach Contacts`; the Sheet parser will read and render them.

Those browser-side choices are stored in `localStorage` for the current browser and use the Sheet `ID` column as the stable job key when available, so marks survive site refreshes and regenerated pages. Export the JSON when you want to use the feedback to update scoring weights, calibration examples, or search targeting.

## Feedback Calibration

The scoring algorithm can adjust from website feedback in two ways:

1. Export browser feedback from the site and set `FEEDBACK_EXPORT_PATH` to that JSON file before running the agent.
2. Add rows to the backend Sheet's `Calibration Examples` tab. Flexible headers are supported, including `Company`, `Role` or `Title`, `URL`, and `Feedback`.

Supported feedback values:

- `shortlist`, `right job`, `priority`, or `yes`: boosts the job and promotes it toward `Apply Now`.
- `direction`, `right direction`, `maybe`, or `not priority`: lightly boosts the job and promotes it toward `Warm Intro First`.
- `wrong`, `wrong direction`, `no`, or `reject`: penalizes the job and moves exact matches to `Rejected / Notable`.

When you mark a role as `Wrong direction` on the website, you can also select one or more reason tags:

- `Too Senior`
- `Too Junior`
- `Wrong Qualifications`
- `Wrong Location`
- `Wrong Job Type`

Those reason tags are stored with the same stable job key and exported as `wrongReasons`. The scorer uses them as conservative calibration signals: repeated `Too Senior` feedback penalizes future roles that look director/principal/executive level, `Wrong Location` uses the exported job location as an avoid term, `Wrong Job Type` uses the title as an avoid term, and `Wrong Qualifications` penalizes future technical/credential mismatch signals.

Preference edits exported from the site also become scoring signals: preferred locations, roles, sectors, and priorities add small positive adjustments, while avoid terms subtract points.

## Role Quality Guardrails

The tracker is tuned for strategy, partnerships, policy, market intelligence, investment/platform, operations, and business-development roles. It should avoid jobs that require an engineering degree or deep technical execution. The scoring layer now:

- Auto-rejects roles that explicitly require an engineering, computer science, or related technical degree.
- Auto-rejects clearly engineering roles such as software engineer or engineering manager.
- Penalizes roles with heavy coding, embedded systems, CAD, machine-learning, propulsion, avionics, or other technical implementation signals unless the title is clearly strategy, policy, partnerships, business development, or operations.
- Preserves a `Main Requirements` snippet from public posting text and shows it on the website and email brief.

The search is not limited to the original company list. Add any free public careers page, ATS board, RSS/Atom feed, or sitemap to `PUBLIC_SOURCE_URLS` or the Sheet's `Source List` tab.

New job intake is balanced before writing to the Sheet. The balancer caps any one company and limits sector concentration so space/defense boards cannot crowd out finance/capital, strategy/partnerships, policy/research, and other target roles. It cannot create finance roles by itself; it preserves room for them when LinkedIn, Handshake, public sources, or manual research surfaces them.

LinkedIn and Handshake requirements can be used when they are available in Gmail alert content, public posting URLs, or Sheet-entered/pasted posting text. The agent should not scrape behind LinkedIn or Handshake logins or bypass their access controls. If a role is login-gated, paste/export the requirements into a Sheet column named `Main Requirements`, `Requirements`, `Job Requirements`, or `Qualifications`.

When a LinkedIn or Handshake Gmail alert surfaces a role, the agent now attempts a free public enrichment pass before scoring: it searches for the same company, exact title, and location; ignores LinkedIn/Handshake result URLs; prefers canonical company or ATS pages; and extracts public requirements when available. If no public posting is found, it falls back to the alert body and marks requirements as needing manual review.

## Public Sources

Set `ENABLE_PUBLIC_SOURCE_SEARCH=true` to include public career-page discovery in the weekly run. The agent reads URLs from:

- `PUBLIC_SOURCE_URLS`, a comma-separated environment variable.
- The backend Sheet's `Source List` tab, when Sheets credentials are configured.

The public-source layer is free of cost and uses only public, unauthenticated sources. It does not bypass logins, scrape LinkedIn directly, or require paid job-board APIs. Current source methods:

- Greenhouse public job-board JSON feeds, from URLs such as `https://boards.greenhouse.io/company`.
- Lever public postings JSON feeds, from URLs such as `https://jobs.lever.co/company`.
- Ashby public job-board JSON feeds, from URLs such as `https://jobs.ashbyhq.com/company`.
- Pinpoint public posting pages, including company careers pages that link to `*.pinpointhq.com/postings/...`.
- Normal public company career pages, using structured `JobPosting` metadata, public ATS links, and HTML link discovery.
- Public RSS/Atom feeds that include job-like items.
- Public sitemap XML files with job/career/opening URLs.

Structured ATS records are appended as public-source jobs with the role title, company/board token, location, canonical posting URL, source name, a short fit-review note, and a compact requirements summary when posting text is available. The scoring layer then evaluates them against the same feedback-calibrated rubric as LinkedIn, Handshake, and Sheet-entered jobs.

Suggested free expansion order:

1. Add target companies and their public ATS/careers URLs to the Sheet's `Source List` tab.
2. Prefer official public ATS feeds first because they are cleaner and less brittle than HTML pages.
3. Add public careers pages, RSS/Atom feeds, or sitemap URLs when a company does not expose a clean ATS board.
4. Add more no-cost adapters only when a target source publishes accessible public postings, such as USAJobs, Wellfound public search pages, or company Workday career sites.
5. Keep paid GPT/web-search research manual or disabled unless you explicitly choose to use API credits.

The `Free Public Job Sync` GitHub Action runs every other day and appends new deduped public-source jobs to the Sheet. It uses only:

- `GOOGLE_SHEET_ID`
- `GOOGLE_APPLICATION_CREDENTIALS_JSON`
- `PUBLIC_SOURCE_URLS`, optionally, plus the Sheet `Source List` tab

It does not use `OPENAI_API_KEY`, Gmail OAuth, LinkedIn scraping, or paid job-search databases.

## GPT Research

The `GPT Role Research` workflow is manual-only by default so it does not spend OpenAI API credits on a schedule. If you choose to run it manually from GitHub Actions, it uses the OpenAI Responses API with web search to find current public job postings, score them, and publish the latest successful research dashboard.

Required GitHub Secret:

```text
OPENAI_API_KEY
```

Optional GitHub Variables:

```text
OPENAI_RESEARCH_MODEL=gpt-5
RESEARCH_MIN_JOBS=5
RESEARCH_MIN_GREAT_FITS=1
RESEARCH_TIMEOUT_SECONDS=900
```

A research run is marked successful only when it surfaces at least five jobs and at least one `Apply Now`-level role. If it cannot meet that bar, or if `OPENAI_API_KEY` is missing, the run records a failure artifact and moves on without blocking indefinitely.

For no-API-cost research, use a ChatGPT Task to research roles and append them to the Google Sheet. The `Sheet-Backed Site Refresh` workflow then republishes the website from the Sheet every six hours without using OpenAI API credits.

See [`docs/chatgpt-task-prompt.md`](docs/chatgpt-task-prompt.md) for a copy/paste-ready ChatGPT Task prompt.

## GitHub Pages

The `Sheet-Backed Site Refresh` workflow publishes the latest generated dashboard to GitHub Pages. In the repository settings, go to **Settings > Pages** and set **Build and deployment > Source** to **GitHub Actions**.

After a successful workflow run, the latest brief is served from:

```text
https://gusim1.github.io/job-search-agent/
```

Keep in mind that GitHub Pages can expose the dashboard as a website. Review your GitHub plan and Pages visibility settings before publishing sensitive job-search details.

## Tests

```bash
pytest
```

The tests cover LinkedIn parsing, scoring and classification, and deduplication. Google API behavior is kept in thin adapter classes so the core logic can run offline.
