from job_search_agent.public_sources import discover_public_jobs


class FakeResponse:
    def __init__(self, text="", json_payload=None):
        self.text = text
        self._json_payload = json_payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._json_payload


def test_discover_public_jobs_from_career_page_links():
    def fake_get(url, timeout, headers):
        return FakeResponse(
            text="""
            <html>
              <head><title>Orbit Works Careers</title></head>
              <body>
                <a href="/jobs/strategic-partnerships">Strategic Partnerships Manager</a>
                <a href="/about">About</a>
              </body>
            </html>
            """
        )

    jobs = discover_public_jobs(["https://orbit.example/careers"], fetcher=fake_get)

    assert len(jobs) == 1
    assert jobs[0].title == "Strategic Partnerships Manager"
    assert jobs[0].company == "Orbit Works"
    assert jobs[0].url == "https://orbit.example/jobs/strategic-partnerships"
    assert jobs[0].source == "Public career page"


def test_discover_public_jobs_skips_generic_career_landing_links():
    def fake_get(url, timeout, headers):
        return FakeResponse(
            text="""
            <html>
              <head><title>MegaBank Careers</title></head>
              <body>
                <a href="/careers">Careers</a>
                <a href="/careers/students-and-graduates">Careers and Internships: Students &amp; Graduates</a>
                <a href="/search-jobs">Search jobs</a>
                <a href="/jobs/investment-banking-intern-dallas">Investment Banking Intern Dallas</a>
              </body>
            </html>
            """
        )

    jobs = discover_public_jobs(["https://megabank.example/careers"], fetcher=fake_get)

    assert len(jobs) == 1
    assert jobs[0].title == "Investment Banking Intern Dallas"
    assert jobs[0].company == "MegaBank"


def test_discover_jobs_from_schema_org_jobposting_json_ld():
    def fake_get(url, timeout, headers):
        return FakeResponse(
            text="""
            <html>
              <head>
                <title>Frontier Careers</title>
                <script type="application/ld+json">
                {
                  "@context": "https://schema.org",
                  "@type": "JobPosting",
                  "title": "Public Policy Strategy Lead",
                  "url": "https://frontier.example/jobs/policy",
                  "datePosted": "2026-06-03",
                  "employmentType": "FULL_TIME",
                  "hiringOrganization": {"name": "Frontier Labs"},
                  "jobLocation": {
                    "@type": "Place",
                    "address": {
                      "addressLocality": "Austin",
                      "addressRegion": "TX",
                      "addressCountry": "US"
                    }
                  },
                  "description": "Policy strategy for frontier technology."
                }
                </script>
              </head>
            </html>
            """
        )

    jobs = discover_public_jobs(["https://frontier.example/careers"], fetcher=fake_get)

    assert len(jobs) == 1
    assert jobs[0].title == "Public Policy Strategy Lead"
    assert jobs[0].company == "Frontier Labs"
    assert jobs[0].location == "Austin, TX, US"
    assert jobs[0].url == "https://frontier.example/jobs/policy"
    assert jobs[0].source == "Schema.org JobPosting"


def test_discover_jobs_from_public_rss_feed():
    def fake_get(url, timeout, headers):
        return FakeResponse(
            text="""
            <rss version="2.0">
              <channel>
                <title>Defense Ventures Jobs</title>
                <item>
                  <title>Investment Research Associate Job</title>
                  <link>https://jobs.example/research-associate</link>
                  <description>Venture and dual-use market research role.</description>
                </item>
                <item>
                  <title>Company update</title>
                  <link>https://jobs.example/news</link>
                </item>
              </channel>
            </rss>
            """
        )

    jobs = discover_public_jobs(["https://jobs.example/feed.xml"], fetcher=fake_get)

    assert len(jobs) == 1
    assert jobs[0].title == "Investment Research Associate Job"
    assert jobs[0].company == "Defense Ventures Jobs"
    assert jobs[0].url == "https://jobs.example/research-associate"
    assert jobs[0].source == "Public RSS/Atom feed"


def test_discover_jobs_from_public_sitemap():
    def fake_get(url, timeout, headers):
        return FakeResponse(
            text="""
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url><loc>https://quantum.example/jobs/market-intelligence-analyst</loc></url>
              <url><loc>https://quantum.example/about</loc></url>
            </urlset>
            """
        )

    jobs = discover_public_jobs(["https://quantum.example/sitemap.xml"], fetcher=fake_get)

    assert len(jobs) == 1
    assert jobs[0].title == "Market Intelligence Analyst"
    assert jobs[0].company == "quantum.example"
    assert jobs[0].url == "https://quantum.example/jobs/market-intelligence-analyst"
    assert jobs[0].source == "Public sitemap"


def test_discover_greenhouse_jobs_from_public_board_api():
    called = []

    def fake_get(url, timeout, headers):
        called.append(url)
        return FakeResponse(
            json_payload={
                "jobs": [
                    {
                        "title": "Strategy Associate",
                        "absolute_url": "https://boards.greenhouse.io/orbitworks/jobs/1",
                        "location": {"name": "Austin, TX"},
                        "departments": [{"name": "Strategy"}],
                        "offices": [{"name": "Austin"}],
                        "content": "<p>Defense innovation role.</p>",
                    }
                ]
            }
        )

    jobs = discover_public_jobs(["https://boards.greenhouse.io/orbitworks"], fetcher=fake_get)

    assert called == ["https://boards-api.greenhouse.io/v1/boards/orbitworks/jobs?content=true"]
    assert len(jobs) == 1
    assert jobs[0].title == "Strategy Associate"
    assert jobs[0].company == "orbitworks"
    assert jobs[0].location == "Austin, TX"
    assert jobs[0].source == "Greenhouse public board"
    assert "Strategy" in jobs[0].fit_summary


def test_discover_greenhouse_jobs_from_direct_public_api_url():
    def fake_get(url, timeout, headers):
        return FakeResponse(json_payload={"jobs": []})

    jobs = discover_public_jobs(
        ["https://boards-api.greenhouse.io/v1/boards/orbitworks/jobs"],
        fetcher=fake_get,
    )

    assert jobs == []


def test_discover_lever_jobs_from_public_postings_api():
    def fake_get(url, timeout, headers):
        return FakeResponse(
            json_payload=[
                {
                    "text": "Strategic Partnerships Lead",
                    "hostedUrl": "https://jobs.lever.co/frontier/abc",
                    "categories": {"location": "Remote US", "team": "Partnerships"},
                    "workplaceType": "remote",
                    "descriptionPlain": "Build partner ecosystem.",
                }
            ]
        )

    jobs = discover_public_jobs(["https://jobs.lever.co/frontier"], fetcher=fake_get)

    assert len(jobs) == 1
    assert jobs[0].title == "Strategic Partnerships Lead"
    assert jobs[0].company == "frontier"
    assert jobs[0].location == "Remote US"
    assert jobs[0].source == "Lever public postings API"
    assert "Partnerships" in jobs[0].fit_summary


def test_discover_ashby_jobs_from_public_job_board_api():
    def fake_get(url, timeout, headers):
        return FakeResponse(
            json_payload={
                "jobs": [
                    {
                        "title": "Market Intelligence Analyst",
                        "jobUrl": "https://jobs.ashbyhq.com/autonomy/123",
                        "location": {"name": "Dallas, TX"},
                        "department": "Strategy",
                        "employmentType": "FullTime",
                        "descriptionPlain": "Autonomy market analysis.",
                    }
                ]
            }
        )

    jobs = discover_public_jobs(["https://jobs.ashbyhq.com/autonomy"], fetcher=fake_get)

    assert len(jobs) == 1
    assert jobs[0].title == "Market Intelligence Analyst"
    assert jobs[0].company == "autonomy"
    assert jobs[0].location == "Dallas, TX"
    assert jobs[0].source == "Ashby public job board API"
    assert "Strategy" in jobs[0].fit_summary


def test_discover_pinpoint_public_posting():
    def fake_get(url, timeout, headers):
        return FakeResponse(
            text="""
            <html>
              <head><title>Mission Architect - Redondo Beach | Impulse Space Careers</title></head>
              <body>
                <h1>Mission Architect</h1>
                <div>Department</div><div>Product Management</div>
                <div>Employment Type</div><div>Full Time</div>
                <div>Location</div><div>Redondo Beach</div>
                <div>Workplace type</div><div>Onsite</div>
                <div>Compensation</div><div>$150,000 - $200,000 / year</div>
                <h2>About Impulse Space</h2>
              </body>
            </html>
            """
        )

    jobs = discover_public_jobs(
        ["https://impulsespace.pinpointhq.com/postings/747f7c0b-c29a-4514-8eeb-b39287b79a37"],
        fetcher=fake_get,
    )

    assert len(jobs) == 1
    assert jobs[0].title == "Mission Architect"
    assert jobs[0].company == "Impulse Space"
    assert jobs[0].location == "Redondo Beach"
    assert jobs[0].source == "Pinpoint public posting"
    assert "Product Management" in jobs[0].fit_summary


def test_discover_pinpoint_posting_from_company_careers_page():
    calls = []

    def fake_get(url, timeout, headers):
        calls.append(url)
        if url == "https://frontier.example/careers":
            return FakeResponse(
                text="""
                <html>
                  <head><title>Frontier Careers</title></head>
                  <body>
                    <a href="https://frontier.pinpointhq.com/postings/abc">Strategic Growth Manager Austin</a>
                  </body>
                </html>
                """
            )
        return FakeResponse(
            text="""
            <html>
              <head><title>Strategic Growth Manager - Austin | Frontier Careers</title></head>
              <body>
                <h1>Strategic Growth Manager</h1>
                <p>Department</p><p>Business Development</p>
                <p>Employment Type</p><p>Full Time</p>
                <p>Location</p><p>Austin</p>
                <p>Workplace type</p><p>Hybrid</p>
              </body>
            </html>
            """
        )

    jobs = discover_public_jobs(["https://frontier.example/careers"], fetcher=fake_get)

    assert calls == ["https://frontier.example/careers", "https://frontier.pinpointhq.com/postings/abc"]
    assert len(jobs) == 1
    assert jobs[0].title == "Strategic Growth Manager"
    assert jobs[0].company == "Frontier"
    assert jobs[0].location == "Austin"
    assert jobs[0].source == "Pinpoint public posting"
