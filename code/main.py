"""
main.py — CLI Entry Point for the Forensic Triage Agent.

Usage:
    python main.py                          # Process support_tickets.csv
    python main.py --input custom.csv       # Custom input file
    python main.py --sample                 # Run on sample tickets (for testing)
    python main.py --dry-run                # Validate setup, don't process

Output is written to support_tickets/output.csv (or --output path).
"""

import os
import csv
import sys
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv

from agent import ForensicTriageAgent
from formatter import (
    console,
    print_banner,
    log_ticket_header,
    log_ticket_result,
    print_summary_table,
)
from config import TICKETS_INPUT, TICKETS_OUTPUT, SAMPLE_TICKETS

# Configure logging (warnings/errors only; Rich handles display)
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()


def estimate_cost_usd(total_api_calls: int) -> float:
    """
    Estimate API cost based on number of calls.

    Pricing (GROQ Llama 3.3 70B):
    - Input: $0.59 per 1M tokens
    - Output: $0.79 per 1M tokens

    Average per call:
    - Input: ~1500 tokens (system + context + ticket)
    - Output: ~300 tokens

    Args:
        total_api_calls: Total number of API calls made

    Returns:
        Estimated cost in USD
    """
    input_tokens = total_api_calls * 1500
    output_tokens = total_api_calls * 300
    return (input_tokens * 0.59 / 1_000_000) + (output_tokens * 0.79 / 1_000_000)


def validate_environment() -> None:
    """
    Validate all required environment variables and paths exist.

    Checks:
    - GROQ_API_KEY is set
    - data/ directory exists
    - support_tickets/ directory exists

    Raises:
        SystemExit if validation fails
    """
    errors = []

    if not os.environ.get("GROQ_API_KEY"):
        errors.append(
            "GROQ_API_KEY not set. "
            "Copy .env.example to .env and add your API key."
        )

    if not Path("data").exists():
        errors.append("data/ directory not found. Run from the repo root.")

    if not Path("support_tickets").exists():
        errors.append("support_tickets/ directory not found.")

    if errors:
        console.print("[bold red]Environment Validation Failed:[/bold red]")
        for error in errors:
            console.print(f"  [red]✗ {error}[/red]")
        sys.exit(1)

    console.print("  [bold green]✓ Environment validated[/bold green]")


def read_tickets(path: str) -> list:
    """
    Read support tickets from a CSV file.

    Expected columns: Issue, Subject, Company (case-insensitive).

    Args:
        path: Path to the CSV file

    Returns:
        List of dicts with keys: Issue, Subject, Company
    """
    tickets = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Handle case variations in column names
                issue = row.get("Issue") or row.get("issue") or ""
                subject = row.get("Subject") or row.get("subject") or ""
                company = row.get("Company") or row.get("company") or ""

                tickets.append(
                    {"Issue": issue.strip(), "Subject": subject.strip(),
                     "Company": company.strip()}
                )
    except FileNotFoundError:
        console.print(f"[red]✗ File not found: {path}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error reading CSV: {e}[/red]")
        sys.exit(1)

    return tickets


def write_output(results: list, path: str) -> None:
    """
    Write processed results to output CSV.

    Columns:
    - issue, subject, company (from input)
    - response, product_area, status, request_type, justification (output)

    Args:
        results: List of result dicts
        path: Output file path
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "issue",
        "subject",
        "company",
        "response",
        "product_area",
        "status",
        "request_type",
        "justification",
    ]

    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(results)
        console.print(f"  [green]✓ Output written to: {path}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Error writing output: {e}[/red]")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Forensic Triage Agent — HackerRank Orchestrate 2026",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input", default=None, help="Input CSV path (default: support_tickets.csv)"
    )
    parser.add_argument(
        "--output", default=TICKETS_OUTPUT, help="Output CSV path"
    )
    parser.add_argument(
        "--sample", action="store_true", help="Use sample tickets (for testing)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate setup, don't process tickets",
    )
    args = parser.parse_args()

    print_banner()

    # Environment validation
    console.print("[dim]Validating environment...[/dim]")
    validate_environment()

    # Determine input file
    input_path = (
        SAMPLE_TICKETS if args.sample
        else args.input if args.input
        else TICKETS_INPUT
    )

    if not Path(input_path).exists():
        console.print(f"[red]✗ Input file not found: {input_path}[/red]")
        sys.exit(1)

    # Read tickets
    tickets = read_tickets(input_path)
    console.print(f"  [dim]Loaded {len(tickets)} tickets from {input_path}[/dim]\n")

    # Dry run (validation only, no processing)
    if args.dry_run:
        console.print("[bold yellow]✓ Dry run complete — environment is valid.[/bold yellow]")
        return

    # Initialize agent (builds BM25 index)
    console.print("[dim]Building BM25 corpus index...[/dim]")
    try:
        agent = ForensicTriageAgent()
    except Exception as e:
        console.print(f"[red]✗ Failed to initialize agent: {e}[/red]")
        sys.exit(1)
    console.print()

    # Process tickets
    pipeline_results = []
    output_rows = []
    total_api_calls = 0

    for i, ticket in enumerate(tickets, 1):
        issue = ticket["Issue"]
        subject = ticket["Subject"]
        company = ticket["Company"]
        preview = (subject or issue)

        # Print ticket header
        log_ticket_header(i, len(tickets), company or "None", preview)

        # Process ticket through pipeline
        try:
            result = agent.process_ticket(issue, subject, company)
        except Exception as e:
            console.print(f"[red]✗ Error processing ticket: {e}[/red]")
            logger.exception("Ticket processing error")
            result = agent.process_ticket("", "", "")  # Return empty result
            result.status = "escalated"
            result.justification = f"Processing error: {str(e)[:100]}"

        # Print result
        log_ticket_result(result, i)
        pipeline_results.append(result)
        total_api_calls += result.api_calls_made

        # Build output row
        output_rows.append(
            {
                "issue": issue,
                "subject": subject,
                "company": company,
                "response": result.response,
                "product_area": result.product_area,
                "status": result.status,
                "request_type": result.request_type,
                "justification": result.justification,
            }
        )

    # Write output and print summary
    write_output(output_rows, args.output)
    est_cost = estimate_cost_usd(total_api_calls)
    print_summary_table(pipeline_results, est_cost)


if __name__ == "__main__":
    main()
