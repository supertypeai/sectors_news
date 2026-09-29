from datetime import datetime
from typing_extensions import Annotated

from .pipeline import run_news_briefs_backfill, run_news_briefs_pipeline

import logging
import sys
import typer


app = typer.Typer(
    help="Generate pre-open and post-close news briefs",
    no_args_is_help=True,
)


@app.callback()
def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)],
    )


@app.command(name="run")
def run_command(
    market: Annotated[str, typer.Option(help="idx or sgx")],
):
    """
    Brief the sessions closed since the last run, save to news_briefs and the state file.
    """
    run_news_briefs_pipeline(market)


@app.command(name="backfill")
def backfill_command(
    market: Annotated[str, typer.Option(help="idx or sgx")],
    start_date: Annotated[datetime, typer.Option(formats=["%Y-%m-%d"])],
    end_date: Annotated[datetime, typer.Option(formats=["%Y-%m-%d"])],
):
    """
    Brief every session in a date range into a local JSON file, for testing.
    """
    run_news_briefs_backfill(
        market, 
        start_date.date(), 
        end_date.date()
    )


if __name__ == "__main__":
    app()


# uv run -m scraper_engine.news_briefs.cli run --market idx
# uv run -m scraper_engine.news_briefs.cli backfill --market idx --start-date 2026-09-28 --end-date 2026-09-28
