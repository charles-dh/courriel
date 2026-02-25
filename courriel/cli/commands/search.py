"""Search command implementation.

Provides local email search via notmuch. Remote search is planned for v2.

Usage:
    courriel search "from:alice@example.com"
    courriel search "subject:invoice" --account work
    courriel search "date:2024.." --limit 20 --output summary
"""

import json

import typer
from typing_extensions import Annotated

from courriel.config import get_account, get_account_names, load_config
from courriel.search import (
    NotmuchDatabaseError,
    NotmuchError,
    NotmuchNotFoundError,
    SearchResult,
    search_local,
)
from pathlib import Path

app = typer.Typer(help="Search emails locally or remotely")


@app.command()
def search(
    query: Annotated[
        str,
        typer.Argument(
            help="Search query (notmuch syntax, e.g., 'from:alice@example.com')"
        ),
    ],
    all_accounts: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Search all accounts (default behavior)",
        ),
    ] = False,
    account: Annotated[
        str | None,
        typer.Option(
            "--account",
            help="Search specific account only",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            help="Maximum results to return",
        ),
    ] = 50,
    output: Annotated[
        str,
        typer.Option(
            "--output",
            help="Output format: json, summary, files",
        ),
    ] = "json",
    remote: Annotated[
        bool,
        typer.Option(
            "--remote",
            help="Search remote provider instead of local (v2, not implemented)",
        ),
    ] = False,
) -> None:
    """Search emails using notmuch query syntax.

    Examples:
        courriel search "from:alice@example.com"
        courriel search "subject:meeting" --account work
        courriel search "date:2024.." --output summary
        courriel search "tag:unread" --output files

    Query syntax: https://notmuchmail.org/doc/latest/man7/notmuch-search-terms.html
    """
    # Validate output format
    if output not in ("json", "summary", "files"):
        typer.echo(f"Error: Invalid output format '{output}'", err=True)
        typer.echo("Valid formats: json, summary, files", err=True)
        raise typer.Exit(1)

    # Remote search not yet implemented
    if remote:
        typer.echo(
            "Error: Remote search not yet implemented (planned for v2)", err=True
        )
        raise typer.Exit(1)

    # Load configuration
    config = load_config()
    all_account_names = get_account_names(config)

    if not all_account_names:
        typer.echo("Error: No accounts configured.", err=True)
        typer.echo("Run 'courriel config init' and add an account.", err=True)
        raise typer.Exit(1)

    # Determine which accounts to search
    if account:
        if account not in all_account_names:
            typer.echo(f"Error: Account '{account}' not configured.", err=True)
            typer.echo(f"Available accounts: {', '.join(all_account_names)}", err=True)
            raise typer.Exit(1)
        accounts_to_search = [account]
    else:
        # Default: search all accounts (--all is just for explicitness)
        accounts_to_search = all_account_names

    # Get config defaults for limit/output if not explicitly set
    defaults = config.get("defaults", {})
    if limit == 50:  # Default value, check if config has different default
        limit = defaults.get("search_limit", 50)
    if output == "json":  # Default value, check if config has different default
        output = defaults.get("search_output", "json")

    # Perform search across accounts
    all_results: list[SearchResult] = []

    try:
        for acct_name in accounts_to_search:
            account_config = get_account(config, acct_name)
            if not account_config:
                continue

            mail_dir_str = account_config.get("mail_dir", "~/Mail")
            mail_dir = Path(mail_dir_str).expanduser()

            if not mail_dir.exists():
                typer.echo(
                    f"Warning: Mail directory not found for '{acct_name}': {mail_dir}",
                    err=True,
                )
                continue

            results = search_local(
                query=query,
                mail_dir=mail_dir,
                account_name=acct_name,
                limit=limit,
            )
            all_results.extend(results)

    except NotmuchNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except NotmuchDatabaseError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except NotmuchError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    # Sort by date (newest first) and apply limit across all accounts
    all_results.sort(key=lambda r: r.date, reverse=True)
    all_results = all_results[:limit]

    # Format and output results
    if output == "json":
        _output_json(query, all_results)
    elif output == "summary":
        _output_summary(all_results)
    elif output == "files":
        _output_files(all_results)


def _output_json(query: str, results: list[SearchResult]) -> None:
    """Output results as JSON."""
    output_data = {
        "query": query,
        "total": len(results),
        "results": [r.to_dict() for r in results],
    }
    typer.echo(json.dumps(output_data, indent=2))


def _output_summary(results: list[SearchResult]) -> None:
    """Output results as human-readable summary grouped by account."""
    if not results:
        typer.echo("No results found.")
        return

    # Group by account
    by_account: dict[str, list[SearchResult]] = {}
    for r in results:
        by_account.setdefault(r.account, []).append(r)

    for acct_name, acct_results in by_account.items():
        count_word = "result" if len(acct_results) == 1 else "results"
        typer.echo(f"{acct_name}: {len(acct_results)} {count_word}")

        for r in acct_results:
            date_str = r.date.strftime("%Y-%m-%d")
            # Truncate from_addr and subject for display
            from_display = _truncate(r.from_addr, 30)
            subject_display = _truncate(r.subject, 40)
            typer.echo(f"  {date_str} {from_display:30} {subject_display}")

        typer.echo()  # Blank line between accounts


def _output_files(results: list[SearchResult]) -> None:
    """Output results as file paths, one per line."""
    for r in results:
        if r.file:
            typer.echo(r.file)


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "..."
