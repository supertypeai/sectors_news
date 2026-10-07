from datetime import date

from llm.client import TokenUsageLogger

from .utils.constant import NEWS_TABLES
from .utils.previous_issue import resolve_issue_window, is_already_built, to_previous_issue
from .utils.json_io import write_json
from .utils.supporting_news import attach_supporting_news, attach_what_to_watch_supporting_news
from llm.cost import log_total_cost
from .steps.news_input import get_data
from .steps.grouping import run_grouping, remove_duplicate_ids
from .steps.development_generation import run_group_generation
from .steps.importance import run_importance
from .steps.issue_layout import get_market_caps, build_issue_layout
from .steps.display_copy import run_display_copy
from .steps.what_to_watch import run_what_to_watch_generation
from .steps.final_data import get_final_data_clean

import asyncio
import logging


LOGGER = logging.getLogger(__name__)


def run_daily_issue(
    issue_date: date,
    exchange: str,
    models: list[str],
    previous_issue: dict | None,
) -> dict | None:
    run_date = issue_date.isoformat()

    if is_already_built(issue_date, previous_issue):
        LOGGER.warning(
            "Issue %s: skipped, the saved previous issue is already %s",
            run_date,
            previous_issue["issue_date"],
        )
        return None

    window_start, window_end = resolve_issue_window(
        issue_date,
        exchange,
        previous_issue,
    )

    LOGGER.info(
        "Issue %s: window %s to %s",
        run_date,
        window_start,
        window_end,
    )

    as_of = f"{issue_date.day} {issue_date:%B %Y}"

    token_usage_logger = TokenUsageLogger()

    news_records = get_data(
        start_date=window_start,
        end_date=window_end,
        table=NEWS_TABLES[exchange],
    )

    LOGGER.info(
        "Issue %s: total news fetched: %d", 
        run_date, 
        len(news_records)
    )

    # step 1: group based on event
    group_result = run_grouping(
        news_records=news_records,
        exchange=exchange,
        models=models,
        effort="high",
        token_usage_logger=token_usage_logger,
    )

    group_result["result"] = remove_duplicate_ids(
        group_result["result"]
    )

    LOGGER.info(
        "Issue %s: grouping: %d groups, %d excluded | check %s",
        run_date,
        len(group_result["result"]["groups"]),
        len(group_result["result"]["excluded_news_ids"]),
        group_result["check"],
    )

    # step 2: generate event
    developments = asyncio.run(
        run_group_generation(
            news_db=news_records,
            exchange=exchange,
            group_result=group_result["result"],
            models=models,
            as_of=as_of,
            token_usage_logger=token_usage_logger,
        )
    )

    LOGGER.info(
        "Issue %s: development generation: %d developments",
        run_date,
        len(developments),
    )

    # step 3
    importance_result = run_importance(
        developments=developments,
        exchange=exchange,
        models=models,
        as_of=as_of,
        previous_issue=previous_issue,
        effort="high",
        token_usage_logger=token_usage_logger,
    )

    LOGGER.info(
        "Issue %s: importance: lead %s | check %s",
        run_date,
        importance_result["lead_development_id"],
        importance_result["check"],
    )

    # step 4
    market_caps = get_market_caps(
        tickers=[
            ticker
            for development in developments
            for ticker in development["tickers"]
        ],
        as_of_date=run_date,
        exchange=exchange,
    )

    issue_layout = build_issue_layout(
        developments=developments,
        result=importance_result,
        market_caps=market_caps,
    )

    LOGGER.info(
        "Issue %s: layout: lead %s, %d section stories, %d flash",
        run_date,
        "yes" if issue_layout["lead"] is not None else "none",
        sum(len(stories) for stories in issue_layout["sections"].values()),
        len(issue_layout["flash"]),
    )

    # step 5
    display_result = asyncio.run(
        run_display_copy(
            issue_layout=issue_layout,
            exchange=exchange,
            models=models,
            as_of=as_of,
            token_usage_logger=token_usage_logger,
        )
    )

    display_result = attach_supporting_news(
        display_result=display_result,
        news_records=news_records,
    )

    # step 6
    what_to_watch_result = run_what_to_watch_generation(
        developments=developments,
        exchange=exchange,
        models=models,
        as_of=as_of,
        effort="high",
        token_usage_logger=token_usage_logger,
    )

    what_to_watch_result = attach_what_to_watch_supporting_news(
        what_to_watch_result=what_to_watch_result,
        news_records=news_records,
    )

    LOGGER.info(
        "Issue %s: what to watch: %d items | check %s",
        run_date,
        len((what_to_watch_result or {}).get("items", [])),
        (what_to_watch_result or {}).get("check"),
    )

    log_total_cost(token_usage_logger)

    final_data = get_final_data_clean(
        display_result=display_result,
        what_to_watch_result=what_to_watch_result,
    )

    write_json(
        data={
            "issue_date": run_date,
            "window_start": window_start,
            "window_end": window_end,
            **final_data,
        },
        name="final_data_clean", 
        exchange=exchange,
    )

    return to_previous_issue(
        display_result=display_result,
        issue_date=run_date,
        window_start=window_start,
        window_end=window_end,
    )
