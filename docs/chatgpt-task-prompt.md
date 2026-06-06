# ChatGPT Task Prompt

Use this prompt to create a recurring ChatGPT Task that researches roles and updates the Google Sheet backend without using the OpenAI API. Replace every bracketed placeholder before creating the Task.

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
- Other public ATS or company job pages

Do not scrape LinkedIn directly. LinkedIn and Handshake should enter through email alerts, not direct scraping.

Preferences:
- Locations: [PREFERRED LOCATIONS]
- Strong roles: [PREFERRED ROLE TYPES]
- Sectors: [PREFERRED SECTORS]
- Avoid: [AVOID RULES]
- Seniority: [SENIORITY TARGET]
- Compensation: [COMPENSATION TARGET]
- Hard constraints: [HARD CONSTRAINTS]

Scoring:
- Use the existing 100-point rubric if available.
- Great Fit should generally score 75+.
- Possible Fit should generally score 62-74.
- Weak Fit should score below 62.

Success criteria:
Consider the task successful only if you find at least 5 roles and at least 1 Great Fit. Otherwise, report failure and explain what limited the search.

Final response:
Summarize:
- How many roles were found
- How many were Great Fit
- Which rows were appended
- Any rows skipped as duplicates
- Whether the task met the success criteria
```
