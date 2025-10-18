"""
Utility to generate a workflow and usage PDF for the Phish Detector project.

The script avoids third-party dependencies so it can run in constrained
environments. Edit `build_document_lines` to update the narrative and run
`python scripts/generate_workflow_pdf.py` to regenerate the PDF.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap

OUTPUT_PATH = Path("phish_detector_workflow.pdf")


@dataclass
class Section:
    title: str
    paragraphs: list[str]
    bullet_lists: list[list[str]] | None = None


def build_document_lines() -> list[str]:
    """Return the textual content for the PDF split into wrapped lines."""
    width = 94  # suitable for 12pt text on US Letter with margins

    def add_heading(text: str) -> None:
        lines.append(text.upper())
        lines.append("")

    def add_paragraph(text: str) -> None:
        for wrapped in wrap(text, width=width):
            lines.append(wrapped)
        lines.append("")

    def add_list(items: list[str]) -> None:
        for item in items:
            wrapped_lines = wrap(item, width=width - 4) or [""]
            lines.append(f"- {wrapped_lines[0]}")
            for continuation in wrapped_lines[1:]:
                lines.append(f"    {continuation}")
        lines.append("")

    sections: list[Section] = [
        Section(
            title="Project Overview",
            paragraphs=[
                (
                    "Phish Detector is a phishing URL analysis toolkit with three first-class "
                    "entry points: a FastAPI backend with Celery workers, a Typer based CLI for "
                    "power users, and a Manifest v3 browser extension that surfaces risk verdicts "
                    "directly inside the browser. All components share a PostgreSQL datastore so "
                    "analysis history is consistent regardless of the client."
                ),
                (
                    "The repository provides a docker-compose stack for local development and "
                    "bundles infrastructure defaults (Redis, Selenium, PostgreSQL) alongside the "
                    "Python services and web assets. This document captures the recommended "
                    "workflow for contributors and end users."
                ),
            ],
        ),
        Section(
            title="System Architecture",
            paragraphs=[
                (
                    "The system starts with `backend/`, a FastAPI application that exposes "
                    "`/api/analyze`, `/api/result/{task_id}`, and `/api/history`. Incoming "
                    "requests enqueue Celery tasks which perform heuristic scoring, domain age "
                    "lookups, and Selenium powered DOM inspection to flag risky form elements."
                ),
                (
                    "`cli/` hosts a Typer command line client that talks to the API, offering "
                    "`analyze` and `history` commands with verdict aware output. `extension/` "
                    "contains a Chromium compatible popup that submits URLs, polls task status, "
                    "and renders the persisted history table."
                ),
                (
                    "PostgreSQL stores every analysis record and Redis serves as the Celery broker "
                    "and result backend. Selenium Grid (headless Chrome) enables lightweight page "
                    "rendering and credential field detection."
                ),
            ],
        ),
        Section(
            title="Development Workflow",
            paragraphs=[
                "Recommended steps when contributing to the repo:",
            ],
            bullet_lists=[
                [
                    "Install Docker and Docker Compose, then run `docker-compose up --build` "
                    "at least once to seed the database schema.",
                    "Export environment overrides as needed (`DATABASE_URL`, `REDIS_URL`, "
                    "`SELENIUM_URL`, `CORS_ALLOW_ORIGINS`).",
                    "For backend changes, create a virtual environment and install "
                    "`backend/requirements.txt`, then run `uvicorn app.main:app --reload`.",
                    "Run Celery locally with `celery -A app.tasks worker --loglevel=info` while "
                    "developing tasks.",
                    "Execute targeted tests or linting (`pytest`, `ruff`, etc.) if the project "
                    "later adds them. Today, functional verification hinges on manual endpoint "
                    "and client checks.",
                ]
            ],
        ),
        Section(
            title="Running the Stack",
            paragraphs=[
                (
                    "For the simplest local setup, rely on Docker Compose. The shipped file "
                    "starts five services: postgres, redis, selenium, backend, and worker. The "
                    "backend is accessible on http://localhost:8000 after the containers settle."
                ),
                (
                    "When running natively, ensure PostgreSQL and Redis are installed and that "
                    "Selenium (Standalone Chrome or Edge) is reachable at the configured "
                    "`SELENIUM_URL`. Start the FastAPI app and Celery worker separately."
                ),
            ],
        ),
        Section(
            title="CLI Usage",
            paragraphs=[
                (
                    "The CLI defaults to `http://localhost:8000`. Override with "
                    "`PHISH_API_URL` when targeting remote deployments."
                ),
            ],
            bullet_lists=[
                [
                    "`python cli/cli.py analyze https://example.com --verbose` submits a URL "
                    "and streams the final verdict plus optional detail JSON.",
                    "`python cli/cli.py history --limit 20 --verdict phishing` lists the most "
                    "recent results filtered by verdict.",
                    "Network and polling exceptions surface inline; rerun the command once the "
                    "backend is reachable.",
                ]
            ],
        ),
        Section(
            title="Browser Extension Usage",
            paragraphs=[
                (
                    "Load the extension via `chrome://extensions` (Developer Mode -> Load "
                    "unpacked -> select `extension/`). Update the API base inside the popup if "
                    "the backend runs on a different host."
                ),
                (
                    "The popup permits fetching the active tab URL, manual entry, and quick access "
                    "to recent history. Results reuse the same verdict labels (SAFE, WARNING, "
                    "PHISHING, UNKNOWN, FAILED) as the CLI."
                ),
                (
                    "Adjust `CORS_ALLOW_ORIGINS` in the backend configuration and "
                    "`host_permissions` in `manifest.json` before pointing the extension at "
                    "production domains."
                ),
            ],
        ),
        Section(
            title="API Reference",
            paragraphs=[
                "Key HTTP endpoints exposed by the backend:",
            ],
            bullet_lists=[
                [
                    "`POST /api/analyze` - body: `{ \"url\": \"https://target\" }`. Returns "
                    "`task_id` and initial status (QUEUED).",
                    "`GET /api/result/{task_id}` - returns task metadata, risk score, verdict, "
                    "and heuristic details.",
                    "`GET /api/history?limit=20&offset=0&verdict=SAFE` - paginated list of "
                    "persistent analysis records.",
                ]
            ],
        ),
        Section(
            title="Data Model",
            paragraphs=[
                (
                    "The `analysis_results` table tracks task_id, url, status, risk_score, "
                    "detail JSON, and timestamps. Celery creates or updates rows as tasks "
                    "progress, marking failures to aid debugging."
                ),
                (
                    "JSON details capture heuristics (keyword matches, subdomain score), domain "
                    "age metrics, Selenium outcomes, and screenshot path (when enabled)."
                ),
            ],
        ),
        Section(
            title="Testing and Verification",
            paragraphs=[
                (
                    "Before shipping changes, confirm the following:"
                ),
            ],
            bullet_lists=[
                [
                    "Backend endpoints respond with HTTP 200 using `curl` or `httpie`.",
                    "Celery worker processes jobs without crashing and updates history records.",
                    "CLI commands finish successfully against a running backend.",
                    "Browser extension can submit URLs and refresh history without CORS errors.",
                ]
            ],
        ),
        Section(
            title="Deployment Checklist",
            paragraphs=[
                "For production rollouts:",
            ],
            bullet_lists=[
                [
                    "Provision PostgreSQL, Redis, and a Selenium compatible browser sandbox.",
                    "Set secure environment variables and rotate credentials regularly.",
                    "Front the FastAPI app with HTTPS (e.g., via Traefik or Nginx).",
                    "Scale Celery workers based on expected concurrency, adding autoscaling if "
                    "running in Kubernetes or ECS.",
                    "Bake the CLI into automation pipelines (CI, Slack bots) where phishing URLs "
                    "need on-demand evaluation.",
                ]
            ],
        ),
        Section(
            title="Troubleshooting",
            paragraphs=[
                (
                    "If tasks remain stuck in QUEUED or RUNNING, inspect the Celery worker logs "
                    "and verify Redis connectivity. Selenium related errors often stem from "
                    "mismatched driver versions or browsers failing to start in containerized "
                    "environments."
                ),
                (
                    "CORS issues show up as blocked requests in the browser console. Update "
                    "`CORS_ALLOW_ORIGINS` and redeploy the backend to grant the requesting "
                    "origin access."
                ),
            ],
        ),
    ]

    lines: list[str] = []
    add_heading("PHISH DETECTOR WORKFLOW AND USAGE GUIDE")
    add_paragraph("Version 1.0.0 - Generated by scripts/generate_workflow_pdf.py")

    for section in sections:
        add_heading(section.title)
        for paragraph in section.paragraphs:
            add_paragraph(paragraph)
        if section.bullet_lists:
            for bullet_list in section.bullet_lists:
                add_list(bullet_list)

    while lines and lines[-1] == "":
        lines.pop()
    return lines


def pdf_escape(text: str) -> str:
    """Escape parentheses and backslashes for PDF literal strings."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def chunk_lines(lines: list[str], lines_per_page: int) -> list[list[str]]:
    return [lines[i : i + lines_per_page] for i in range(0, len(lines), lines_per_page)]


def build_pdf_bytes(lines: list[str]) -> bytes:
    """Construct a simple multi-page PDF containing the provided lines."""
    page_width = 612  # 8.5 in at 72 dpi
    page_height = 792  # 11 in at 72 dpi
    margin_left = 54
    margin_top = 54
    line_height = 16
    font_size = 12

    lines_per_page = (page_height - 2 * margin_top) // line_height
    pages = chunk_lines(lines, lines_per_page)
    if not pages:
        pages = [[]]

    objects: list[bytes] = []
    xref_offsets: list[int] = []

    pdf_parts: bytearray = bytearray(b"%PDF-1.4\n")

    next_obj_id = 1

    # Build content streams ahead of object creation
    content_streams = []
    for page_lines in pages:
        text_operators = [
            "BT",
            f"/F1 {font_size} Tf",
            f"{margin_left} {page_height - margin_top} Td",
        ]
        first_line = True
        for line in page_lines:
            escaped_line = pdf_escape(line if line else " ")
            if not first_line:
                text_operators.append(f"0 {-line_height} Td")
            text_operators.append(f"({escaped_line}) Tj")
            first_line = False
        text_operators.append("ET")
        content_streams.append("\n".join(text_operators).encode("ascii"))

    # Determine font object id after pages and contents
    font_obj_id = next_obj_id + len(pages) * 2 + 2  # catalog + pages + per-page + per-content + font

    # Catalog object
    catalog_obj = f"{next_obj_id} 0 obj\n<< /Type /Catalog /Pages {next_obj_id + 1} 0 R >>\nendobj\n".encode(
        "ascii"
    )
    objects.append(catalog_obj)
    next_obj_id += 1

    # Pages object
    pages_obj_id = next_obj_id
    kids_refs = " ".join(f"{pages_obj_id + 1 + i * 2} 0 R" for i in range(len(pages)))
    pages_obj = (
        f"{pages_obj_id} 0 obj\n<< /Type /Pages /Count {len(pages)} /Kids [{kids_refs}] >>\nendobj\n".encode(
            "ascii"
        )
    )
    objects.append(pages_obj)
    next_obj_id += 1

    # Page and content objects
    for stream in content_streams:
        page_obj_id = next_obj_id
        content_obj_id = next_obj_id + 1

        page_obj = (
            f"{page_obj_id} 0 obj\n"
            f"<< /Type /Page /Parent {pages_obj_id} 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 {font_obj_id} 0 R >> >> "
            f"/Contents {content_obj_id} 0 R >>\n"
            "endobj\n"
        ).encode("ascii")
        objects.append(page_obj)
        next_obj_id += 1

        content_obj = (
            f"{content_obj_id} 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream\nendobj\n"
        )
        objects.append(content_obj)
        next_obj_id += 1

    # Font object
    font_obj = (
        f"{font_obj_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".encode(
            "ascii"
        )
    )
    objects.append(font_obj)

    # Append objects while tracking offsets
    for obj in objects:
        xref_offsets.append(len(pdf_parts))
        pdf_parts.extend(obj)

    # Cross-reference table
    xref_start = len(pdf_parts)
    total_objects = len(objects) + 1  # include the null object
    pdf_parts.extend(f"xref\n0 {total_objects}\n".encode("ascii"))
    pdf_parts.extend(b"0000000000 65535 f \n")
    for offset in xref_offsets:
        pdf_parts.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    # Trailer
    pdf_parts.extend(
        f"trailer\n<< /Size {total_objects} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode(
            "ascii"
        )
    )

    return bytes(pdf_parts)


def main() -> None:
    lines = build_document_lines()
    pdf_bytes = build_pdf_bytes(lines)
    OUTPUT_PATH.write_bytes(pdf_bytes)
    print(f"PDF generated at {OUTPUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
