from datetime import date

from job_search_agent.models import Classification, JobRecord, NetworkContact, ScoredJob
from job_search_agent.sheets_client import SheetsClient, scored_jobs_from_sheet_rows


def test_scored_jobs_from_sheet_rows_reconstructs_active_roles():
    rows = [
        [
            date.today().isoformat(),
            "Strategic Partnerships Manager",
            "Orbit Works",
            "Austin, TX",
            "https://example.com/job",
            "ChatGPT Task",
            "88",
            "orbit|strategic|https://example.com/job",
            "Strong strategy and Austin match.",
        ]
    ]

    scored = scored_jobs_from_sheet_rows(rows)

    assert len(scored) == 1
    assert scored[0].job.company == "Orbit Works"
    assert scored[0].job.fit_summary == "Strong strategy and Austin match."
    assert scored[0].total_score == 88
    assert Classification.APPLY_NOW in scored[0].labels
    assert Classification.AUSTIN_MATCH in scored[0].labels


def test_scored_jobs_from_sheet_rows_marks_rejected_rows():
    rejected = [
        [
            date.today().isoformat(),
            "Software Engineer",
            "Prime Defense",
            "Washington, DC",
            "https://example.com/eng",
            "ChatGPT Task",
            "22",
            "prime|engineer|https://example.com/eng",
        ]
    ]

    scored = scored_jobs_from_sheet_rows([], rejected)

    assert len(scored) == 1
    assert scored[0].destination_tab == "Rejected Notable"
    assert scored[0].labels == [Classification.REJECTED_NOTABLE]


def test_scored_jobs_from_sheet_rows_understands_backend_header_shape():
    rows = [
        [
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
            "Fit Summary",
            "Main Requirements",
        ],
        [
            "JR-0007",
            "2026-06-02",
            "CesiumAstro",
            "Senior Financial Planning and Analysis Specialist II",
            "Space-tech startup",
            "Space / aerospace defense",
            "Austin",
            "Austin, TX",
            "On-site",
            "Company careers / Lever",
            "https://jobs.lever.co/CesiumAstro/123",
            "Strong fit for space sector and Austin location.",
            "5+ years of strategy, finance, or operations experience.",
        ],
    ]

    scored = scored_jobs_from_sheet_rows(rows)

    assert len(scored) == 1
    assert scored[0].job.company == "CesiumAstro"
    assert scored[0].job.title == "Senior Financial Planning and Analysis Specialist II"
    assert scored[0].job.url == "https://jobs.lever.co/CesiumAstro/123"
    assert scored[0].job.source == "Company careers / Lever"
    assert scored[0].job.location == "Austin, TX"
    assert scored[0].job.fit_summary == "Strong fit for space sector and Austin location."
    assert scored[0].job.requirements_summary == "5+ years of strategy, finance, or operations experience."
    assert scored[0].job.source_email_id == "google-sheet:JR-0007"


def test_scored_jobs_from_sheet_rows_restores_date_and_marks_expired():
    rows = [
        ["ID", "Date Found", "Company", "Role", "City", "URL", "Score"],
        ["JR-OLD", "2026-01-01", "Frontier Capital", "Investment Research Associate", "Remote", "https://example.com/old", "80"],
    ]

    scored = scored_jobs_from_sheet_rows(rows)

    assert scored[0].job.date_found.isoformat() == "2026-01-01"
    assert scored[0].labels == [Classification.EXPIRED]
    assert scored[0].destination_tab == "Expired"


def test_scored_jobs_from_sheet_rows_generates_fit_summary_when_sheet_lacks_one():
    rows = [
        [
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
        ],
        [
            "JR-0004",
            "2026-06-02",
            "Impulse Space",
            "Technical Business Development Manager (Defense)",
            "Space-tech startup",
            "Space / defense",
            "Non-Texas exceptional",
            "Redondo Beach, CA",
            "On-site",
            "Company careers / Pinpoint",
            "https://impulsespace.pinpointhq.com/en/postings/example",
        ],
    ]

    scored = scored_jobs_from_sheet_rows(rows)

    assert len(scored) == 1
    assert scored[0].job.fit_summary
    assert scored[0].job.fit_summary != "Loaded from Google Sheets backend."
    assert "Space / defense" in scored[0].job.fit_summary


def test_backend_scored_jobs_filters_engineer_titles_from_site():
    service = FakeSheetsService(
        {
            "'Active Roles'!A1:Z": [
                ["ID", "Company", "Role", "City", "URL", "Source", "Score", "Fit Summary"],
                ["1", "CesiumAstro", "EHS Engineer II", "Westminster, CO", "https://example.com/eng", "Public", "24", ""],
                ["2", "Orbit Works", "Strategic Partnerships Manager", "Austin, TX", "https://example.com/strategy", "Public", "82", ""],
            ],
            "'Rejected Notable'!A1:Z": [],
        }
    )
    client = SheetsClient(service, "sheet")

    jobs = client.backend_scored_jobs()

    assert len(jobs) == 1
    assert jobs[0].job.title == "Strategic Partnerships Manager"


def test_existing_dedupe_keys_reads_id_from_first_header_column():
    service = FakeSheetsService(
        {
            "'Active Roles'!A1:Z": [
                ["ID", "Company", "Role", "City"],
                ["orbit|strategic|https://example.com/strategy", "Orbit Works", "Strategic Partnerships Manager", "Austin, TX"],
            ],
            "'Rejected Notable'!A1:Z": [],
        }
    )
    client = SheetsClient(service, "sheet")

    assert client.existing_dedupe_keys() == {"orbit|strategic|https://example.com/strategy"}


def test_append_scored_jobs_uses_sheet_header_order_and_skips_engineers():
    service = FakeSheetsService(
        {
            "'Active Roles'!A1:Z": [
                ["ID", "Date Found", "Company", "Role", "City", "Source", "URL", "Score", "Fit Summary", "Main Requirements"]
            ]
        }
    )
    client = SheetsClient(service, "sheet")
    strategy = ScoredJob(
        job=JobRecord(
            title="Strategic Partnerships Manager",
            company="Orbit Works",
            location="Austin, TX",
            url="https://example.com/strategy",
            source="Public",
            source_email_id="1",
            fit_summary="Strong fit.",
            requirements_summary="5+ years in partnerships.",
        ),
        total_score=82,
        labels=[Classification.APPLY_NOW],
        score_breakdown={},
        rationale=["Strong fit."],
        destination_tab="Active Roles",
    )
    engineer = strategy.model_copy(
        update={
            "job": strategy.job.model_copy(update={"title": "EHS Engineer II", "company": "CesiumAstro"}),
            "total_score": 24,
        }
    )

    client.append_scored_jobs([strategy, engineer])

    assert len(service.appended) == 1
    appended = service.appended[0]["body"]["values"][0]
    assert appended[2] == "Orbit Works"
    assert appended[3] == "Strategic Partnerships Manager"
    assert appended[8] == "Strong fit."
    assert appended[9] == "5+ years in partnerships."


def test_sheet_rows_round_trip_network_context_columns():
    rows = [
        [
            "ID",
            "Company",
            "Role",
            "City",
            "URL",
            "Score",
            "Network Summary",
            "First Reach Contacts",
        ],
        [
            "JR-9",
            "CesiumAstro",
            "Contracts Manager",
            "Austin, TX",
            "https://example.com/cesium",
            "72",
            "Ava Chen appears connected to CesiumAstro.",
            "Ava Chen - CesiumAstro - Director of Partnerships - https://example.com/ava",
        ],
    ]

    scored = scored_jobs_from_sheet_rows(rows)

    assert scored[0].job.network_summary == "Ava Chen appears connected to CesiumAstro."
    assert scored[0].job.network_contacts[0].name == "Ava Chen"
    assert scored[0].job.network_contacts[0].company == "CesiumAstro"


def test_scored_jobs_repairs_packed_public_source_fields():
    rows = [
        [
            "ID",
            "Date Found",
            "Company",
            "Role",
            "City",
            "Source",
            "URL",
            "Score",
            "Fit Summary",
        ],
        [
            "2026-06-03",
            "2026-06-03",
            "CesiumAstro",
            "Washington D.C.",
            "cesiumastro|director of business development national security intelligence|https://jobs.lever.co/CesiumAstro/e32be311",
            "Lever public postings API",
            "",
            "53",
            "Promising direction because it matches relevant Lever public postings API and cesiumastro|director of business development national security intelligence|https://jobs.lever.co/CesiumAstro/e32be311 signals.",
        ],
    ]

    scored = scored_jobs_from_sheet_rows(rows)

    assert scored[0].job.company == "CesiumAstro"
    assert scored[0].job.title == "Director of Business Development National Security Intelligence"
    assert scored[0].job.location == "Washington D.C."
    assert scored[0].job.url == "https://jobs.lever.co/CesiumAstro/e32be311"
    assert "cesiumastro|" not in scored[0].job.fit_summary
    assert "Washington D.C." in scored[0].job.fit_summary


def test_scored_jobs_repairs_swapped_company_and_title_fields():
    rows = [
        [
            "ID",
            "Company",
            "Role",
            "City",
            "Source",
            "URL",
            "Score",
        ],
        [
            "JR-10",
            "Business Development Lead, Central Europe (DACH, Czech Republic, Slovakia) (R5054)",
            "shieldai",
            "Munich",
            "https://jobs.lever.co/shieldai/1382eb7c",
            "Lever public postings API",
            "40",
        ],
    ]

    scored = scored_jobs_from_sheet_rows(rows)

    assert scored[0].job.company == "Shield AI"
    assert scored[0].job.title == "Business Development Lead, Central Europe (DACH, Czech Republic, Slovakia) (R5054)"
    assert scored[0].job.location == "Munich"
    assert scored[0].job.url == "https://jobs.lever.co/shieldai/1382eb7c"


def test_append_scored_jobs_writes_network_context_when_headers_exist():
    service = FakeSheetsService(
        {
            "'Active Roles'!A1:Z": [
                [
                    "ID",
                    "Company",
                    "Role",
                    "Network Summary",
                    "First Reach Contacts",
                ]
            ]
        }
    )
    client = SheetsClient(service, "sheet")
    scored = ScoredJob(
        job=JobRecord(
            title="Contracts Manager",
            company="CesiumAstro",
            location="Austin, TX",
            url="https://example.com/cesium",
            source="Public",
            source_email_id="1",
            network_summary="Ava Chen appears connected to CesiumAstro.",
            network_contacts=[
                NetworkContact(
                    name="Ava Chen",
                    company="CesiumAstro",
                    position="Director of Partnerships",
                    profile_url="https://example.com/ava",
                )
            ],
        ),
        total_score=72,
        labels=[Classification.WARM_INTRO_FIRST],
        score_breakdown={},
        rationale=["Promising fit."],
        destination_tab="Active Roles",
    )

    client.append_scored_jobs([scored])

    appended = service.appended[0]["body"]["values"][0]
    assert appended[3] == "Ava Chen appears connected to CesiumAstro."
    assert "Ava Chen - CesiumAstro - Director of Partnerships - https://example.com/ava" in appended[4]


def test_append_scored_jobs_adds_analysis_columns_and_values_when_headers_exist():
    service = FakeSheetsService(
        {
            "'Active Roles'!A1:Z1": [["ID", "Company", "Role", "City", "URL", "Score"]],
            "'Rejected Notable'!A1:Z1": [],
            "'Active Roles'!A1:Z": [["ID", "Company", "Role", "City", "URL", "Score"]],
        }
    )
    client = SheetsClient(service, "sheet")
    scored = ScoredJob(
        job=JobRecord(
            title="Strategic Partnerships Manager",
            company="Orbit Works",
            location="Dallas, TX",
            url="https://example.com/orbit",
            source="Public",
            source_email_id="1",
            requirements_summary="Business development, strategy, and aerospace market experience. $110k-$140k.",
        ),
        total_score=84,
        labels=[Classification.APPLY_NOW, Classification.DALLAS_MATCH],
        score_breakdown={},
        rationale=["Strong fit."],
        destination_tab="Active Roles",
    )

    client.append_scored_jobs([scored])

    assert "Geography" in service.updated["body"]["values"][0]
    appended = service.appended[0]["body"]["values"][0]
    updated_header = service.updated["body"]["values"][0]
    assert appended[updated_header.index("Geography")] == "Dallas-Fort Worth"
    assert appended[updated_header.index("Role Family")] == "Partnerships / BD"
    assert appended[updated_header.index("Salary Min")] == "110000"
    assert appended[updated_header.index("Salary Max")] == "140000"


def test_backfill_analysis_columns_updates_existing_rows():
    service = FakeSheetsService(
        {
            "'Active Roles'!A1:Z1": [
                [
                    "ID",
                    "Company",
                    "Role",
                    "City",
                    "URL",
                    "Score",
                    "Main Requirements",
                    "Geography",
                    "Role Family",
                    "Salary Min",
                    "Salary Max",
                ]
            ],
            "'Rejected Notable'!A1:Z1": [],
            "'Active Roles'!A1:AZ": [
                [
                    "ID",
                    "Company",
                    "Role",
                    "City",
                    "URL",
                    "Score",
                    "Main Requirements",
                    "Geography",
                    "Role Family",
                    "Salary Min",
                    "Salary Max",
                ],
                [
                    "JR-1",
                    "Orbit Works",
                    "Strategic Partnerships Manager",
                    "Austin, TX",
                    "https://example.com/orbit",
                    "84",
                    "Business development, strategy, and aerospace market experience. $110k-$140k.",
                    "",
                    "",
                    "",
                    "",
                ],
            ],
            "'Rejected Notable'!A1:AZ": [],
        }
    )
    client = SheetsClient(service, "sheet")

    counts = client.backfill_analysis_columns(["Active Roles"])

    assert counts["Active Roles"] >= 4
    updated_rows = service.updated["body"]["values"]
    header = updated_rows[0]
    row = updated_rows[1]
    assert row[header.index("Geography")] == "Austin"
    assert row[header.index("Role Family")] == "Partnerships / BD"
    assert row[header.index("Salary Min")] == "110000"
    assert row[header.index("Salary Max")] == "140000"


class FakeSheetsService:
    def __init__(self, values_by_range):
        self.values_by_range = values_by_range
        self.appended = []

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, spreadsheetId, range):
        self._range = range
        return self

    def append(self, spreadsheetId, range, valueInputOption, insertDataOption, body):
        self.appended.append(
            {
                "spreadsheetId": spreadsheetId,
                "range": range,
                "valueInputOption": valueInputOption,
                "insertDataOption": insertDataOption,
                "body": body,
            }
        )
        return self

    def update(self, spreadsheetId, range, valueInputOption, body):
        self.updated = {
            "spreadsheetId": spreadsheetId,
            "range": range,
            "valueInputOption": valueInputOption,
            "body": body,
        }
        tab, cell_range = range.split("!", 1)
        if cell_range.endswith("1"):
            self.values_by_range[f"{tab}!A1:Z1"] = body["values"]
            for wide_range in ("A1:Z", "A1:AZ"):
                existing = self.values_by_range.get(f"{tab}!{wide_range}", [])
                self.values_by_range[f"{tab}!{wide_range}"] = [body["values"][0], *existing[1:]]
        else:
            self.values_by_range[f"{tab}!A1:Z"] = body["values"]
            self.values_by_range[f"{tab}!A1:AZ"] = body["values"]
        return self

    def execute(self):
        if self.appended:
            return {}
        return {"values": self.values_by_range.get(self._range, [])}
