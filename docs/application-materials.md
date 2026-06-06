# AI Application Materials

This project can build a job-specific prompt packet for a tailored resume and cover letter.

The workflow is intentionally privacy-conscious and cost-conscious:

- By default, it does not call the OpenAI API.
- It reads the Google Sheet backend to pull the target job.
- It reads local `.docx` resume and cover-letter examples only from your machine.
- It writes a complete `prompt.md` packet under `artifacts/application_packets/`.
- You can paste that prompt into ChatGPT, or opt into API generation with `--generate`.

## 1. List Jobs

If you are running this locally from Terminal, first point the app at your Google Sheets service-account file:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/to/service-account.json"
```

Use the service-account JSON, not the Gmail OAuth client file. The service-account email must have access to the backend Google Sheet.

```bash
cd "/path/to/job-search-agent"
PYTHONPATH=src python3 -m job_search_agent.application_materials --list-jobs
```

This prints the highest-scored Sheet jobs with their stable job IDs.

## 2. Build A Prompt Packet

Use a job ID from the list:

```bash
PYTHONPATH=src python3 -m job_search_agent.application_materials --job-id "paste-job-id-here"
```

Or match by company/title:

```bash
PYTHONPATH=src python3 -m job_search_agent.application_materials --company "Shield AI" --title "Operations"
```

If your local Google credentials are not loaded yet, you can still build a packet manually:

```bash
PYTHONPATH=src python3 -m job_search_agent.application_materials \
  --manual-company "Shield AI" \
  --manual-title "Strategic Operations Associate" \
  --manual-location "Dallas, TX" \
  --manual-url "https://example.com/job" \
  --manual-requirements "Stakeholder management, strategic communications, and defense innovation experience."
```

The output folder will look like:

```text
artifacts/application_packets/company-role/
  prompt.md
  job_context.json
```

Paste `prompt.md` into ChatGPT to generate the tailored resume, cover letter, and tailoring note.

## 3. Use Different Examples

Pass one or more local `.docx` examples with `--example`:

```bash
PYTHONPATH=src python3 -m job_search_agent.application_materials \
  --company "Shield AI" \
  --title "Operations" \
  --example "/path/to/current-resume.docx" \
  --example "/path/to/old-cover-letter.docx"
```

You can also set a comma-separated environment variable:

```bash
APPLICATION_EXAMPLE_FILES="/path/resume.docx,/path/letter.docx" PYTHONPATH=src python3 -m job_search_agent.application_materials --job-id "paste-job-id-here"
```

## 4. Optional API Generation

If you explicitly want to use API credits, set `OPENAI_API_KEY` and pass `--generate`:

```bash
OPENAI_API_KEY="sk-..." PYTHONPATH=src python3 -m job_search_agent.application_materials --job-id "paste-job-id-here" --generate
```

That creates:

```text
ai_draft.md
```

No API call is made unless `--generate` is present.

## Style Rules

The prompt tells the model to:

- Match the user's real cover-letter voice: formal, direct, specific, and not overproduced.
- Treat older examples as style references rather than current facts.
- Emphasize the recurring professional center of gravity found in the user's resume, examples, and `JOB_SEARCH_APPLICATION_CONTEXT`.
- Avoid invented facts and flag missing requirements instead of filling gaps.
- Flag jobs that appear to require engineering degrees or deep technical implementation.
