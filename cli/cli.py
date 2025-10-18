import os
import time
from typing import Optional, Tuple

import requests
import typer
from rich import print
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

API = os.getenv("PHISH_API_URL", "http://localhost:8000")

VERDICT_STYLES = {
    "SAFE": ("SAFE", "green"),
    "WARNING": ("WARNING", "yellow"),
    "PHISHING": ("PHISHING", "red"),
    "FAILED": ("FAILED", "red"),
    "UNKNOWN": ("UNKNOWN", "grey50"),
}

VALID_VERDICTS = {"SAFE", "WARNING", "PHISHING", "UNKNOWN"}


def verdict_style(verdict: Optional[str]) -> Tuple[str, str]:
    if verdict is None:
        return VERDICT_STYLES["UNKNOWN"]
    return VERDICT_STYLES.get(verdict.upper(), VERDICT_STYLES["UNKNOWN"])


def validate_verdict(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    upper = value.strip().upper()
    if upper not in VALID_VERDICTS:
        choices = ", ".join(sorted(VALID_VERDICTS))
        raise typer.BadParameter(f"Unsupported verdict '{value}'. Choose from: {choices}.")
    return upper


def format_timestamp(ts: Optional[str]) -> str:
    if not ts:
        return "--"
    return ts.replace("T", " ").split(".")[0]


@app.command()
def analyze(
    url: str = typer.Argument(..., help="URL to analyze"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed JSON"),
):
    """Submit a URL for phishing analysis and stream the result."""
    try:
        response = requests.post(f"{API}/api/analyze", json={"url": url}, timeout=10)
    except requests.RequestException as exc:
        console.print(
            f"[bold red]Error:[/bold red] Could not reach backend at {API}. Is it running?\n{exc}"
        )
        raise typer.Exit(code=1)

    if response.status_code != 200:
        console.print(f"[bold red]Backend error:[/bold red] {response.text}")
        raise typer.Exit(code=1)

    payload = response.json()
    task_id = payload.get("task_id")
    status = payload.get("status", "QUEUED")
    if not task_id:
        console.print("[bold red]Backend response missing task_id.[/bold red]")
        raise typer.Exit(code=1)

    console.print(
        f"Submitted [bold]{url}[/bold]. task_id: [bold]{task_id}[/bold] (status: {status})"
    )

    with console.status("[bold cyan]Polling for result...[/bold cyan]", spinner="dots"):
        while True:
            try:
                poll = requests.get(f"{API}/api/result/{task_id}", timeout=10)
            except requests.RequestException:
                console.print("[yellow]Network error while polling. Retrying...[/yellow]")
                time.sleep(2)
                continue

            if poll.status_code == 404:
                console.print("[bold red]Task not found. Exiting.[/bold red]")
                raise typer.Exit(code=1)

            result = poll.json()
            state = (result.get("status") or "").upper()

            if state == "FAILED":
                console.print("[bold red]Analysis failed.[/bold red]")
                details = result.get("details")
                if details:
                    if verbose:
                        console.print_json(data=details)
                    else:
                        console.print(details)
                raise typer.Exit(code=1)

            if state == "COMPLETED":
                verdict = result.get("verdict")
                score = result.get("risk_score")
                label, color = verdict_style(verdict or state)
                console.print()
                score_display = str(score) if score is not None else "n/a"
                console.print(f"[bold {color}]{label}[/bold {color}]  Risk score: [bold]{score_display}[/bold]")

                details = result.get("details") or {}
                if verbose:
                    console.print_json(data=details)
                else:
                    table = Table(title="Summary")
                    table.add_column("Check")
                    table.add_column("Value")
                    selenium_info = details.get("selenium", {})
                    heur = details.get("heuristic", {})
                    table.add_row(
                        "Has password field",
                        str(selenium_info.get("has_password_field")),
                    )
                    table.add_row(
                        "Found keywords",
                        ", ".join(heur.get("found_keywords", [])) or "--",
                    )
                    table.add_row(
                        "Domain age (days)",
                        str(details.get("domain_age_days", "n/a")),
                    )
                    console.print(table)
                break

            time.sleep(2)


@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-l", min=1, max=100, help="Number of entries to display"),
    verdict: Optional[str] = typer.Option(None, "--verdict", "-f", callback=validate_verdict, help="Filter by verdict"),
):
    """Show recent analysis history."""
    params = {"limit": limit}
    if verdict:
        params["verdict"] = verdict

    try:
        response = requests.get(f"{API}/api/history", params=params, timeout=10)
    except requests.RequestException as exc:
        console.print(f"[bold red]Error:[/bold red] Could not reach backend at {API}.\n{exc}")
        raise typer.Exit(code=1)

    if response.status_code != 200:
        console.print(f"[bold red]Backend error:[/bold red] {response.text}")
        raise typer.Exit(code=1)

    payload = response.json()
    items = payload.get("items", [])
    if not items:
        console.print("[yellow]No history found.[/yellow]")
        return

    table = Table(title="Recent URL checks")
    table.add_column("URL", overflow="fold")
    table.add_column("Verdict")
    table.add_column("Score")
    table.add_column("Status")
    table.add_column("Created")

    for item in items:
        verdict_label, color = verdict_style(item.get("verdict"))
        score = item.get("risk_score")
        score_display = str(score) if score is not None else "n/a"
        table.add_row(
            item.get("url", "--"),
            f"[{color}]{verdict_label}[/{color}]",
            score_display,
            item.get("status", "--"),
            format_timestamp(item.get("created_at")),
        )

    console.print(table)


if __name__ == "__main__":
    app()
