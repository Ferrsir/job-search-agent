# Ferris Setup Notes

This repo is personalized for Ferris Jagger-James Childress LaVigne.

## Dashboard Identity

Set these GitHub Actions variables in `Ferrsir/job-search-agent`:

```text
JOB_SEARCH_USER_FIRST_NAME=Ferris
JOB_SEARCH_USER_FULL_NAME=Ferris Jagger-James Childress LaVigne
JOB_SEARCH_USER_INITIALS=FL
JOB_SEARCH_SITE_TITLE=Ferris' Career Center
JOB_SEARCH_SITE_SUBTITLE=Career Center
JOB_SEARCH_PROFILE_SUMMARY=TAMS/SMU student interested in investment banking, private equity, financial analysis, and finance-focused internships involving company research, modeling, valuation, and due diligence.
JOB_SEARCH_DASHBOARD_URL=https://Ferrsir.github.io/job-search-agent/
JOB_SEARCH_APPLICATION_CONTEXT=Use Ferris' uploaded resume, cover-letter examples, and style guide as the source of truth. Target finance internships and early analyst-style roles in DFW/Texas. Do not invent personal facts, credentials, GPA, deal experience, licenses, or university status beyond provided materials.
GMAIL_SEARCH_QUERY=label:"Job Search Agent" newer_than:14d
ENABLE_PUBLIC_SOURCE_SEARCH=true
PUBLIC_SYNC_DRY_RUN=false
```

## Required GitHub Actions Secrets

Set these as repository secrets. Do not commit them.

```text
GOOGLE_SHEET_ID
GOOGLE_APPLICATION_CREDENTIALS_JSON
GOOGLE_OAUTH_TOKEN_JSON
GMAIL_TO
```

Set `GMAIL_TO` to Ferris' weekly brief email address.

Do not add `OPENAI_API_KEY` unless paid OpenAI API research is intentionally enabled.

## Target Profile

Preferred locations:

```text
Dallas-Fort Worth, Denton, Dallas, Plano, Frisco, Richardson, Fort Worth, Irving, Addison, Austin, Houston
```

Preferred roles:

```text
Investment Banking Intern, Private Equity Intern, Search Fund Intern, Financial Analyst Intern, Investment Analyst Intern, Equity Research Intern, Corporate Finance Intern, Valuation Intern, M&A Intern, Wealth Management Intern, Asset Management Intern, Venture Capital Intern
```

Avoid:

```text
Pure sales roles, commission-only financial advisor roles, insurance sales, door-to-door sales, unpaid internships with heavy workload, unrelated customer service roles, roles requiring completed bachelor's degree unless current students are accepted, and out-of-state roles requiring immediate relocation without housing or relocation support.
```

## Gmail Filter

Create the Gmail label:

```text
Job Search Agent
```

Use this Gmail filter:

```text
(from:(jobs-noreply@linkedin.com OR jobs-listings@linkedin.com OR jobalerts-noreply@linkedin.com OR *@mail.joinhandshake.com OR *@notifications.joinhandshake.com)
 OR subject:("new jobs similar to" OR "jobs similar to" OR "new jobs for" OR "job alert" OR "recommended jobs" OR "jobs you may be interested in"))
 AND (
   subject:(intern OR internship OR analyst OR finance OR investment OR banking OR "private equity" OR "search fund" OR valuation OR "M&A" OR "wealth management" OR "asset management" OR "equity research" OR "corporate finance")
   OR ("investment banking intern" OR "private equity intern" OR "search fund intern" OR "financial analyst intern" OR "valuation intern" OR "M&A intern" OR "wealth management intern")
 )
```

Apply the label `Job Search Agent` and set GitHub variable:

```text
GMAIL_SEARCH_QUERY=label:"Job Search Agent" newer_than:14d
```

## First Actions To Run

After the Google Sheet, secrets, and variables are configured, run these workflows manually:

```text
Sheet-Backed Site Refresh
Free Public Job Sync
Email Weekly Brief
```
