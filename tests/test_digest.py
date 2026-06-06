from datetime import date, timedelta

from job_search_agent.digest import _group_jobs, _weekly_takeaway, render_preferences_page, render_weekly_digest
from job_search_agent.models import Classification, JobRecord, NetworkContact, ScoredJob


def test_digest_groups_requested_tabs_and_duplicates_roles():
    job = JobRecord(
        title="Strategy Analyst",
        company="Orbit Works",
        location="Dallas, TX",
        url="https://example.com/job",
        source="Sheet",
        source_email_id="1",
    )
    scored = ScoredJob(
        job=job,
        total_score=88,
        labels=[Classification.APPLY_NOW, Classification.DALLAS_MATCH],
        score_breakdown={"Sheet score": 88},
        rationale=["Sheet score: 88"],
        destination_tab="Active Roles",
    )

    groups = _group_jobs([scored])

    assert list(groups) == ["Top Roles", "Dallas", "Austin", "Remote", "Discarded", "Expired"]
    assert groups["Top Roles"][0] == scored
    assert groups["Dallas"][0] == scored
    assert groups["Austin"] == []
    assert groups["Remote"] == []
    assert groups["Discarded"] == []


def test_digest_groups_discarded_roles():
    job = JobRecord(
        title="Software Engineer",
        company="Prime Defense",
        location="Washington, DC",
        url="https://example.com/job",
        source="Sheet",
        source_email_id="1",
    )
    scored = ScoredJob(
        job=job,
        total_score=10,
        labels=[Classification.REJECTED_NOTABLE],
        score_breakdown={"Sheet score": 10},
        rationale=["Sheet score: 10"],
        destination_tab="Rejected Notable",
    )

    groups = _group_jobs([scored])

    assert list(groups) == ["Top Roles", "Dallas", "Austin", "Remote", "Discarded", "Expired"]
    assert groups["Top Roles"] == []
    assert groups["Discarded"][0] == scored


def test_digest_uses_best_non_discarded_roles_when_no_apply_now_labels():
    job = JobRecord(
        title="Strategy Manager",
        company="Shield AI",
        location="Dallas, TX",
        url="https://example.com/job",
        source="Sheet",
        source_email_id="1",
    )
    scored = ScoredJob(
        job=job,
        total_score=70,
        labels=[Classification.WARM_INTRO_FIRST, Classification.DALLAS_MATCH],
        score_breakdown={"Sheet score": 70},
        rationale=["Sheet score: 70"],
        destination_tab="Active Roles",
    )

    groups = _group_jobs([scored])

    assert groups["Top Roles"] == [scored]


def test_digest_supplements_top_roles_to_keep_shortlist_stable():
    explicit = ScoredJob(
        job=JobRecord(
            title="Strategic Partnerships Lead",
            company="Orbit Works",
            location="Dallas, TX",
            url="https://example.com/orbit",
            source="Sheet",
            source_email_id="1",
        ),
        total_score=80,
        labels=[Classification.APPLY_NOW],
        score_breakdown={"Sheet score": 80},
        rationale=["Sheet score: 80"],
        destination_tab="Active Roles",
    )
    warm = ScoredJob(
        job=JobRecord(
            title="Investment Research Associate",
            company="Frontier Capital",
            location="Remote",
            url="https://example.com/frontier",
            source="Sheet",
            source_email_id="2",
        ),
        total_score=72,
        labels=[Classification.WARM_INTRO_FIRST, Classification.REMOTE_MATCH],
        score_breakdown={"Sheet score": 72},
        rationale=["Sheet score: 72"],
        destination_tab="Active Roles",
    )

    groups = _group_jobs([warm, explicit])

    assert groups["Top Roles"] == [explicit, warm]


def test_weekly_takeaway_summarizes_top_roles():
    first = ScoredJob(
        job=JobRecord(
            title="Technical Product Manager",
            company="Shield AI",
            location="Dallas, TX",
            url="https://example.com/shield",
            source="Sheet",
            source_email_id="1",
        ),
        total_score=85,
        labels=[Classification.APPLY_NOW, Classification.DALLAS_MATCH],
        score_breakdown={"Sheet score": 85},
        rationale=["Sheet score: 85"],
        destination_tab="Active Roles",
    )
    second = ScoredJob(
        job=JobRecord(
            title="Contracts Manager",
            company="CesiumAstro",
            location="Austin, TX",
            url="https://example.com/cesium",
            source="Sheet",
            source_email_id="2",
        ),
        total_score=70,
        labels=[Classification.WARM_INTRO_FIRST, Classification.AUSTIN_MATCH],
        score_breakdown={"Sheet score": 70},
        rationale=["Sheet score: 70"],
        destination_tab="Active Roles",
    )

    takeaway = _weekly_takeaway([first, second])

    assert "Technical Product Manager at Shield AI" in takeaway
    assert "Contracts Manager at CesiumAstro" in takeaway
    assert "Texas-forward" in takeaway


def test_weekly_email_renders_inline_newsletter_without_dashboard_script():
    scored = ScoredJob(
        job=JobRecord(
            title="Autonomy Lead",
            company="Skyways",
            location="Austin, TX",
            url="https://example.com/skyways",
            source="Sheet",
            source_email_id="google-sheet:JR-0001",
            fit_summary="Good Austin autonomy signal.",
            requirements_summary="3+ years of partnerships or market strategy experience.",
        ),
        total_score=74,
        labels=[Classification.WARM_INTRO_FIRST, Classification.AUSTIN_MATCH],
        score_breakdown={"Sheet score": 74},
        rationale=["Good Austin autonomy signal."],
        destination_tab="Active Roles",
    )

    from job_search_agent.digest import render_weekly_email

    html = render_weekly_email([scored])

    assert "Simone's Career Center" in html
    assert "This week's shortlist" in html
    assert "Priority queue" in html
    assert "Location pulse" in html
    assert "Open live dashboard" in html
    assert "Autonomy Lead" in html
    assert "Good Austin autonomy signal." in html
    assert "Main requirements" in html
    assert "3+ years of partnerships" in html
    assert "migrateLegacyFeedback" not in html
    assert "job-search-agent.feedback" not in html


def test_dashboard_renders_main_requirements():
    scored = ScoredJob(
        job=JobRecord(
            title="Strategic Growth Manager",
            company="Frontier",
            location="Austin, TX",
            url="https://example.com/frontier",
            source="Sheet",
            source_email_id="google-sheet:JR-0002",
            fit_summary="Strong Austin strategy signal.",
            requirements_summary="5+ years in partnerships, strategy, or market development.",
        ),
        total_score=82,
        labels=[Classification.APPLY_NOW, Classification.AUSTIN_MATCH],
        score_breakdown={"Sheet score": 82},
        rationale=["Strong Austin strategy signal."],
        destination_tab="Active Roles",
    )

    html = render_weekly_digest([scored])

    assert "Main requirements" in html
    assert "5+ years in partnerships" in html


def test_dashboard_renders_dynamic_time_based_greeting():
    scored = ScoredJob(
        job=JobRecord(
            title="Strategic Growth Manager",
            company="Frontier",
            location="Austin, TX",
            url="https://example.com/frontier",
            source="Sheet",
            source_email_id="google-sheet:JR-0002",
            fit_summary="Strong Austin strategy signal.",
        ),
        total_score=82,
        labels=[Classification.APPLY_NOW, Classification.AUSTIN_MATCH],
        score_breakdown={"Sheet score": 82},
        rationale=["Strong Austin strategy signal."],
        destination_tab="Active Roles",
    )

    html = render_weekly_digest([scored])

    assert "data-greeting-title" in html
    assert "function greetingForHour(hour)" in html
    assert 'if (hour >= 22 || hour < 5) return "Good Night";' in html
    assert 'if (hour < 12) return "Morning";' in html
    assert 'if (hour < 17) return "Afternoon";' in html
    assert 'return "Evening";' in html


def test_dashboard_renders_application_packet_button():
    scored = ScoredJob(
        job=JobRecord(
            title="Strategic Growth Manager",
            company="Frontier",
            location="Austin, TX",
            url="https://example.com/frontier",
            source="Sheet",
            source_email_id="google-sheet:JR-0002",
            fit_summary="Strong Austin strategy signal.",
            requirements_summary="5+ years in partnerships, strategy, or market development.",
        ),
        total_score=82,
        labels=[Classification.APPLY_NOW, Classification.AUSTIN_MATCH],
        score_breakdown={"Sheet score": 82},
        rationale=["Strong Austin strategy signal."],
        destination_tab="Active Roles",
    )

    html = render_weekly_digest([scored])

    assert "Application packet" in html
    assert "Application Packet Prompt" in html
    assert "Voice And Structure Profile" in html
    assert "Use the uploaded resume, cover-letter examples, and style guide as the source of truth" in html
    assert "Open in ChatGPT" in html
    assert "https://chatgpt.com/g/g-p-6a1f49c34ec481918bc839b79a99932d-job-search/project?tab=chats" in html
    assert "Downloadable Files" in html
    assert "python3 -m job_search_agent.application_materials --job-id" in html
    assert "copy-packet-prompt" in html


def test_dashboard_renders_wrong_direction_reason_picker():
    scored = ScoredJob(
        job=JobRecord(
            title="Strategic Growth Manager",
            company="Frontier",
            location="Austin, TX",
            url="https://example.com/frontier",
            source="Sheet",
            source_email_id="google-sheet:JR-0002",
            fit_summary="Strong Austin strategy signal.",
        ),
        total_score=82,
        labels=[Classification.APPLY_NOW, Classification.AUSTIN_MATCH],
        score_breakdown={"Sheet score": 82},
        rationale=["Strong Austin strategy signal."],
        destination_tab="Active Roles",
    )

    html = render_weekly_digest([scored])

    assert "Why wrong?" in html
    assert 'value="too_senior"' in html
    assert 'value="too_junior"' in html
    assert 'value="wrong_qualifications"' in html
    assert 'value="wrong_location"' in html
    assert 'value="wrong_job_type"' in html
    assert "Push feedback" in html
    assert "function selectedWrongReasons(row)" in html
    assert 'if (button.dataset.feedback === "wrong")' in html
    assert 'feedback[row.dataset.jobId] = "wrong";' in html
    assert "job-search-agent.wrongReasons" in html
    assert "wrongReasons" in html
    assert "function paintFeedbackForJob(jobId, options = {})" in html
    assert "keepPanelsClosed" in html
    assert "paintFeedbackForJob(row.dataset.jobId, { keepPanelsClosed: true })" in html
    assert 'const calibrationPayloadKey = "job-search-agent.calibrationPayload";' in html
    assert "function buildCalibrationPayload()" in html
    assert "localStorage.setItem(calibrationPayloadKey, JSON.stringify(buildCalibrationPayload()));" in html
    assert 'viewKind === "category"\n                ? rowFeedback !== "wrong" && !isStaticDiscarded' in html
    assert "function applyPanelFilters(panel)" in html


def test_dashboard_renders_right_direction_reason_picker_and_preferences_link():
    scored = ScoredJob(
        job=JobRecord(
            title="Strategic Growth Manager",
            company="Frontier",
            location="Austin, TX",
            url="https://example.com/frontier",
            source="Sheet",
            source_email_id="google-sheet:JR-0002",
            fit_summary="Strong Austin strategy signal.",
        ),
        total_score=82,
        labels=[Classification.APPLY_NOW, Classification.AUSTIN_MATCH],
        score_breakdown={"Sheet score": 82},
        rationale=["Strong Austin strategy signal."],
        destination_tab="Active Roles",
    )

    html = render_weekly_digest([scored])

    assert 'href="preferences.html" target="_blank"' in html
    assert "What's strong?" in html
    assert 'value="strong_seniority_match"' in html
    assert 'value="strong_job_type"' in html
    assert 'value="strong_qualifications"' in html
    assert "job-search-agent.directionReasons" in html
    assert "directionReasons" in html
    assert "function selectedDirectionReasons(row)" in html
    assert 'if (button.dataset.feedback === "direction")' in html
    assert 'feedback[row.dataset.jobId] = "direction";' in html
    assert "setDirectionReasonPanelOpen(row, true)" in html
    assert "paintFeedbackForJob(row.dataset.jobId, { keepPanelsClosed: true })" in html


def test_preferences_page_renders_interactive_questionnaire():
    html = render_preferences_page()

    assert "Career signal calibration." in html
    assert "Start fresh" in html
    assert "Restore current answers" in html
    assert "Download intake HTML" in html
    assert "Save preferences" in html
    assert "This tells the scoring algorithm which job families should rise to the top" in html
    assert "Strategic Partnerships" in html
    assert "job-search-agent.preferences" in html
    assert "questionnaireAnswers" in html
    assert "function preferencesFromAnswers" in html
    assert "function completedIntakeHtml(answers)" in html
    assert "job-search-agent-intake" in html
    assert "machine-readable JSON" in html


def test_dashboard_renders_network_context_in_card_and_prompt():
    scored = ScoredJob(
        job=JobRecord(
            title="Contracts Manager",
            company="CesiumAstro",
            location="Austin, TX",
            url="https://example.com/cesium",
            source="Sheet",
            source_email_id="google-sheet:JR-0003",
            fit_summary="Strong space and contracts fit.",
            requirements_summary="Contracts, vendors, and aerospace customer experience.",
            network_summary="Ava Chen appears connected to CesiumAstro.",
            network_contacts=[
                NetworkContact(
                    name="Ava Chen",
                    company="CesiumAstro",
                    position="Director of Partnerships",
                    profile_url="https://example.com/ava",
                    reason="current company match",
                )
            ],
        ),
        total_score=78,
        labels=[Classification.APPLY_NOW, Classification.AUSTIN_MATCH],
        score_breakdown={"Sheet score": 78},
        rationale=["Strong space and contracts fit."],
        destination_tab="Active Roles",
    )

    html = render_weekly_digest([scored])

    assert "First reach context" in html
    assert "Ava Chen appears connected to CesiumAstro." in html
    assert "Ava Chen" in html
    assert "suggested_first_reaches" in html
    assert "First-Reach Note" in html


def test_dashboard_renders_analytics_view():
    scored = ScoredJob(
        job=JobRecord(
            title="Strategic Partnerships Manager",
            company="Orbit Works",
            location="Dallas, TX",
            url="https://example.com/orbit",
            source="Sheet",
            source_email_id="google-sheet:JR-4",
            fit_summary="Strong Dallas strategy and space signal.",
            requirements_summary="Business development, aerospace, and government market strategy experience. $110k-$140k.",
            network_contacts=[
                NetworkContact(name="Ava Chen", company="Orbit Works", position="Partnerships Lead")
            ],
        ),
        total_score=84,
        labels=[Classification.APPLY_NOW, Classification.DALLAS_MATCH],
        score_breakdown={"Sheet score": 84},
        rationale=["Strong fit."],
        destination_tab="Active Roles",
    )

    html = render_weekly_digest([scored])

    assert "Search Analytics" in html
    assert "Where The Market Is Showing Up" in html
    assert "Job Types By Geography" in html
    assert "Companies Hiring Most" in html
    assert "Strongest First-Reach Paths" in html
    assert "Qualifications In Demand" in html
    assert "Average Salary Signals" in html
    assert "Standard Job Type Mix" in html
    assert "Quality Distribution" in html
    assert "Seniority Fit" in html
    assert "Work Mode" in html
    assert "Degree Signals" in html
    assert "Clearance / Citizenship Signals" in html
    assert "Analytics Matches" in html
    assert "analytics-filter-chip" in html
    assert "data-analytics-filter=\"roleFamily\"" in html
    assert "data-analytics-filter=\"company\"" in html
    assert "data-analytics-filter=\"qualification\"" in html
    assert "data-analytics-company=\"Orbit Works\"" in html
    assert "data-qualifications=\"" in html
    assert "data-role-family=\"Partnerships / BD\"" in html
    assert "data-score-band=\"80+ priority\"" in html
    assert "function matchesAnalyticsFilter(row)" in html
    assert 'activeAnalyticsFilter.type === "qualification"' in html
    assert "activeAnalyticsFilter" in html
    assert "analyticsMatchCount.textContent" in html
    assert "display: block;\n        height: 9px;" in html
    assert "display: block;\n        height: 100%;" in html
    assert "Data Cleanup Queue" in html
    assert "Dallas-Fort Worth" in html
    assert "Partnerships / BD" in html
    assert "geo-map" in html
    assert "us-map-svg" in html
    assert "job-market-map" in html
    assert "d3.geoAlbersUsa" in html
    assert "assets/us-states-10m.json" in html
    assert "activateCityMarker" in html
    assert "top open roles by rating" in html
    assert "stack-track" in html
    assert "metric-chip" in html


def test_dashboard_persists_active_view_on_refresh():
    scored = ScoredJob(
        job=JobRecord(
            title="Strategic Partnerships Manager",
            company="Orbit Works",
            location="Dallas, TX",
            url="https://example.com/orbit",
            source="Sheet",
            source_email_id="google-sheet:JR-4",
            fit_summary="Strong Dallas strategy signal.",
        ),
        total_score=84,
        labels=[Classification.APPLY_NOW, Classification.DALLAS_MATCH],
        score_breakdown={"Sheet score": 84},
        rationale=["Strong fit."],
        destination_tab="Active Roles",
    )

    html = render_weekly_digest([scored])

    assert 'const viewStateKey = "job-search-agent.viewState";' in html
    assert "function saveViewState(view, panelTarget)" in html
    assert "function restoreViewState()" in html
    assert "window.history.replaceState(null, \"\", `#${panelTarget}`);" in html
    assert 'saveViewState("this-week", button.dataset.tabTarget);' in html
    assert "saveViewState(view, button.dataset.tabTarget);" in html
    assert "restoreViewState();\n      applyFilters();" in html


def test_digest_groups_expired_roles_separately():
    expired = ScoredJob(
        job=JobRecord(
            title="Strategy Associate",
            company="OldCo",
            location="Austin, TX",
            url="https://example.com/old",
            source="Sheet",
            source_email_id="old",
            date_found=date.today() - timedelta(days=46),
        ),
        total_score=90,
        labels=[Classification.EXPIRED, Classification.APPLY_NOW, Classification.AUSTIN_MATCH],
        score_breakdown={},
        rationale=["Old role."],
        destination_tab="Expired",
    )

    groups = _group_jobs([expired])

    assert groups["Top Roles"] == []
    assert groups["Austin"] == []
    assert groups["Expired"] == [expired]
