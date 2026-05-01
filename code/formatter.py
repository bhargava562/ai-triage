"""
formatter.py — Ubuntu Boot-Style Forensic Terminal Dashboard.

Uses the Rich library to produce a visually distinct terminal experience
that makes the triage process transparent and auditable in real time.
Every gate decision is logged so a human watching can audit the logic.

Colors based on Ubuntu terminal palette:
- ORANGE: branding (#E95420)
- GREEN: success (#77b65e)
- YELLOW: warning (#EFB92E)
- RED: error (#cc0000)
"""

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich import box
from typing import List

console = Console()

# Ubuntu terminal color palette
ORANGE = "bold #E95420"
GREEN = "bold #77b65e"
BLUE = "bold #0073E6"
RED = "bold #cc0000"
YELLOW = "bold #EFB92E"
GRAY = "dim white"
WHITE = "white"


def print_banner() -> None:
    """Print the main banner at startup."""
    banner = Text()
    banner.append("  ╔══════════════════════════════════════════════════╗\n", style=ORANGE)
    banner.append("  ║   FORENSIC TRIAGE AGENT v1.0                    ║\n", style=ORANGE)
    banner.append("  ║   HackerRank Orchestrate | May 2026             ║\n", style=GRAY)
    banner.append("  ║   Architecture: 6-Gate Deterministic Pipeline   ║\n", style=GRAY)
    banner.append("  ╚══════════════════════════════════════════════════╝\n", style=ORANGE)
    console.print(banner)


def log_ticket_header(ticket_num: int, total: int, company: str, issue_preview: str) -> None:
    """
    Print header for a new ticket being processed.

    Args:
        ticket_num: Current ticket number (1-indexed)
        total: Total tickets
        company: Company field from CSV
        issue_preview: First 80 chars of issue text
    """
    console.print(
        Rule(f"[{ORANGE}]Ticket #{ticket_num}/{total} — {company}[/]")
    )
    preview = issue_preview[:80] + ("..." if len(issue_preview) > 80 else "")
    console.print(f"  [dim]Issue: {preview}[/dim]")


def log_gate(
    gate_num: int, gate_name: str, result: str, detail: str = ""
) -> None:
    """
    Print a single gate decision (like Ubuntu boot log style).

    Args:
        gate_num: Gate number (1-6)
        gate_name: Human-readable gate name
        result: Status string (e.g., "PASS", "ESCALATE", "RETRIEVE")
        detail: Optional additional detail
    """
    # Determine status icon and color based on result
    if "PASS" in result or "OK" in result or "RETRIEVE" in result:
        status_icon = "✓"
        status_style = GREEN
    elif "WARN" in result or "BORDERLINE" in result:
        status_icon = "⚠"
        status_style = YELLOW
    elif "FAIL" in result or "ESCALATE" in result:
        status_icon = "✗"
        status_style = RED
    else:
        status_icon = "→"
        status_style = BLUE

    elapsed = f"[ {gate_num * 0.08:.2f}s ]"

    # Print gate line: [time] [GATE N] name ✓ result (detail)
    console.print(f"  {elapsed} ", end="", style=GRAY)
    console.print(f"[GATE {gate_num}] ", end="", style=ORANGE)
    console.print(f"{gate_name:<28}", end="", style=WHITE)
    console.print(f" {status_icon} ", end="", style=status_style)
    console.print(f"{result}", end="", style=status_style)

    if detail:
        console.print(f"  ({detail})", style=GRAY)
    else:
        console.print()


def log_ticket_result(result, ticket_num: int) -> None:
    """
    Print final result summary for a ticket.

    Args:
        result: TicketResult object
        ticket_num: Ticket number for logging
    """
    status_color = GREEN if result.status == "replied" else YELLOW
    console.print(
        f"  [dim]→[/dim] "
        f"[{status_color}]{result.status.upper()}[/{status_color}] "
        f"| {result.request_type} "
        f"| {result.product_area} "
        f"| [{GRAY}]{result.processing_time_ms:.0f}ms | "
        f"{result.api_calls_made} API call(s)[/{GRAY}]"
    )


def print_summary_table(results: List, total_cost_usd: float) -> None:
    """
    Print final statistics table after all tickets are processed.

    Args:
        results: List of TicketResult objects
        total_cost_usd: Estimated API cost in USD
    """
    console.print()
    console.print(Rule(f"[{ORANGE}]TRIAGE COMPLETE — FINAL REPORT[/]"))

    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style=ORANGE,
        border_style="dim white",
    )
    table.add_column("Metric", style="white")
    table.add_column("Value", style="bold white")

    # Compute statistics
    replied = sum(1 for r in results if r.status == "replied")
    escalated = sum(1 for r in results if r.status == "escalated")
    gate_stops = {}
    for r in results:
        gate_stops[r.gate_stopped] = gate_stops.get(r.gate_stopped, 0) + 1

    avg_ms = sum(r.processing_time_ms for r in results) / max(len(results), 1)
    total_api = sum(r.api_calls_made for r in results)

    # Add rows
    table.add_row("Total Tickets", str(len(results)))
    table.add_row("Replied", f"[{GREEN}]{replied}[/{GREEN}]")
    table.add_row("Escalated", f"[{YELLOW}]{escalated}[/{YELLOW}]")
    table.add_row("Avg Processing Time", f"{avg_ms:.0f}ms")
    table.add_row("Total API Calls", str(total_api))
    table.add_row("Est. Cost (USD)", f"${total_cost_usd:.5f}")

    for gate, count in sorted(gate_stops.items()):
        if count > 0:
            table.add_row(f"  Gate {gate} Exits", str(count))

    console.print(table)
    console.print()
