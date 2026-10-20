from datetime import date
from typing_extensions import Annotated, Optional

from config.logging_setup import setup_logging

from .processor import run_daily_issue
from .steps.upsert import upsert_data
from .utils.constant import DEFAULT_MODELS, Exchange
from .utils.issue_window import build_issue_dates, is_before_cutoff
from .utils.previous_issue import (
    load_current_issue,
    load_previous_issue,
    save_current_issue,
    save_previous_issue,
)

import typer


app = typer.Typer(
    help='A CLI for news issue',
    no_args_is_help=True
)


@app.callback()
def main() -> None:
    """
    News Issue CLI.

    This callback function treats this as a multi-command app
    """
    setup_logging()


@app.command(name="run")
def run(
    exchange: Annotated[Exchange, typer.Option(case_sensitive=False, help="Market to build the issue for")],
    issue_date: Annotated[str, typer.Option(help="First issue date (cutoff day), YYYY-MM-DD")],
    issue_count: Annotated[int, typer.Option(help="Number of consecutive issues to build")] = 1,
    model: Annotated[Optional[list[str]], typer.Option(help="LLM model, repeat for fallbacks")] = None,
    upsert: Annotated[bool, typer.Option(help="Upsert each issue into news_issue after it is built")] = False,
    update: Annotated[bool, typer.Option(help="Rebuild the day's issue up to now, leaving previous_issue.json for the final run")] = False,
    scheduled: Annotated[bool, typer.Option(help="Run as an update before the day's cutoff and as the final run after it")] = False,
) -> None:
    """
    Build issues from the news window and save the latest one under data/news_issues/<market>.
    """
    if scheduled:
        update = is_before_cutoff(
            issue_date=date.fromisoformat(issue_date),
            exchange=exchange.value,
        )

    if update and issue_count != 1:
        raise typer.BadParameter("--update rebuilds one issue, so --issue-count must be 1")

    models = model or DEFAULT_MODELS

    # The last saved issue lets the first issue of this run skip stories already covered
    previous_issue = load_previous_issue(exchange.value)

    for current_issue_date in build_issue_dates(
        issue_date, 
        issue_count, 
        exchange.value
    ):
        today_issue = run_daily_issue(
            issue_date=current_issue_date,
            exchange=exchange.value,
            models=models,
            previous_issue=previous_issue,
            current_issue=load_current_issue(
                issue_date=current_issue_date,
                exchange=exchange.value,
            ),
            update=update,
        )

        if today_issue is None:
            continue

        save_current_issue(
            current_issue=today_issue,
            exchange=exchange.value,
        )

        # An update keeps yesterday's final as the previous issue, so the next
        # update still starts at its cutoff and repeats none of its stories
        if not update:
            save_previous_issue(
                previous_issue=today_issue,
                exchange=exchange.value,
            )

            previous_issue = today_issue

        if upsert:
            upsert_data(
                exchange=exchange.value,
                data_path="final_data_clean",
            )


if __name__ == "__main__":
    app()


# uv run -m news_issues.pipeline run --exchange IDX --issue-date 2026-10-07
# uv run -m news_issues.pipeline run --exchange IDX --issue-date 2026-10-20 --update --upsert
# uv run -m news_issues.pipeline run --exchange IDX --issue-date 2026-09-28 --issue-count 7 --upsert
# uv run -m news_issues.pipeline run --exchange SGX --issue-date 2026-10-02
