from pathlib import Path

from job_search_agent.linkedin_network import LinkedInNetwork, enrich_jobs_with_network, recommend_contacts
from job_search_agent.models import Classification, JobRecord, ScoredJob


def test_linkedin_network_reads_connections_with_preamble(tmp_path: Path):
    (tmp_path / "Connections.csv").write_text(
        "\n".join(
            [
                "Notes:",
                "LinkedIn export preamble",
                "",
                "First Name,Last Name,URL,Email Address,Company,Position,Connected On",
                "Ava,Chen,https://linkedin.com/in/ava,,CesiumAstro,Director of Partnerships,Jun 1 2026",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "Company Follows.csv").write_text("Organization,Followed On\nCesiumAstro,today\n", encoding="utf-8")
    (tmp_path / "SearchQueries.csv").write_text("Time,Search Query\n2026,CesiumAstro contracts\n", encoding="utf-8")
    jobs = tmp_path / "Jobs"
    jobs.mkdir()
    (jobs / "Saved Jobs.csv").write_text("Saved Date,Job Url,Job Title,Company Name\n2026,u,Contracts Manager,CesiumAstro\n", encoding="utf-8")
    (jobs / "Job Applications.csv").write_text(
        "Application Date,Contact Email,Contact Phone Number,Company Name,Job Title,Job Url,Resume Name,Question And Answers\n",
        encoding="utf-8",
    )
    (tmp_path / "Skills.csv").write_text("Name\nStrategy\n", encoding="utf-8")
    (tmp_path / "Profile.csv").write_text(
        "First Name,Last Name,Summary\nSimone,Montandon,Defense innovation profile\n",
        encoding="utf-8",
    )

    network = LinkedInNetwork.from_dir(tmp_path)

    assert len(network.connections) == 1
    assert network.connections[0].name == "Ava Chen"
    assert "CesiumAstro" in network.followed_companies
    assert network.searched_terms == ["CesiumAstro contracts"]


def test_enrich_jobs_with_network_adds_first_reach_context():
    network = LinkedInNetwork(
        connections=[
            _connection("Ava Chen", "CesiumAstro", "Director of Partnerships"),
            _connection("Bo Diaz", "Other Co", "Contracts Manager"),
        ],
        followed_companies={"CesiumAstro"},
        searched_terms=["cesiumastro contracts"],
        saved_jobs=["CesiumAstro Contracts Manager"],
    )
    scored = _scored_job("Contracts Manager", "CesiumAstro")

    contacts = recommend_contacts(scored, network)
    enriched = enrich_jobs_with_network([scored], network)[0]

    assert contacts[0].name == "Ava Chen"
    assert "current company match" in contacts[0].reason
    assert enriched.job.network_contacts[0].name == "Ava Chen"
    assert "you already follow CesiumAstro" in enriched.job.network_summary


def _connection(name: str, company: str, position: str):
    from job_search_agent.linkedin_network import LinkedInConnection

    return LinkedInConnection(name=name, company=company, position=position, profile_url=f"https://example.com/{name}")


def _scored_job(title: str, company: str) -> ScoredJob:
    return ScoredJob(
        job=JobRecord(
            title=title,
            company=company,
            location="Austin, TX",
            url="https://example.com/job",
            source="Sheet",
            source_email_id="google-sheet:JR-1",
        ),
        total_score=72,
        labels=[Classification.WARM_INTRO_FIRST, Classification.AUSTIN_MATCH],
        score_breakdown={"Sheet score": 72},
        rationale=["Promising fit."],
        destination_tab="Active Roles",
    )
