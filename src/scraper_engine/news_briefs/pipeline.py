from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from scraper_engine.llm.client import TokenUsageLogger
from scraper_engine.llm.constant import MODEL_NAMES
from .brief_generation import run_brief_generation
from .constant import BACKFILL_OUTPUT_DIR, BRIEFS_TABLE, MARKETS, PREVIOUS_BRIEFS_FOR_RECONCILE
from .development_filtering import (
    process_development_to_topic,
    run_development_generation,
    run_development_reconcile,
)
from .policy_filtering import run_policy_news_filtering
from .utils.brief_helper import (
    get_db,
    log_total_cost,
    to_news_brief_row,
    upsert_news_brief,
    write_json_output,
)
from .utils.brief_state import get_previous_topic_states, read_state, write_state
from .utils.market_sessions import build_brief_windows, get_slot_before

import asyncio
import logging


LOGGER = logging.getLogger(__name__)


def run_brief_window(
    brief_window: dict,
    models: list[str],
    previous_topic_states: list[dict],
    token_usage_logger: TokenUsageLogger,
) -> dict:
    start_window = brief_window["start_window"]
    end_window = brief_window["end_window"]
    exchange = MARKETS[brief_window["market"]]["exchange"]

    records = get_db(
        table=MARKETS[brief_window["market"]]["table"],
        query=lambda query_builder: (
            query_builder
            .gte(
                "created_at",
                start_window.astimezone(timezone.utc).isoformat(),
            )
            .lt(
                "created_at",
                end_window.astimezone(timezone.utc).isoformat(),
            )
            .order("created_at", desc=False)
        ),
    )

    LOGGER.info(
        "%s %s %s | %s -> %s | articles: %d",
        brief_window["market"],
        brief_window["market_date"],
        brief_window["session"],
        start_window.isoformat(),
        end_window.isoformat(),
        len(records),
    )

    brief_result = {
        "market": brief_window["market"],
        "market_date": brief_window["market_date"].isoformat(),
        "session": brief_window["session"],
        "start_window": start_window.isoformat(),
        "end_window": end_window.isoformat(),
        "article_count": len(records),
        "policies": [],
        "policy_explanation": None,
        "merged_developments": None,
        "development_reconcile": None,
        "reconciled_developments": [],
        "development_topics": {"topics": []},
        "market_brief": None,
        "what_to_watch": None,
    }

    if not records:
        return brief_result

    policy_result = run_policy_news_filtering(
        articles=records,
        exchange=exchange,
        brief_as_of=end_window.isoformat(),
        models=models,
        effort="medium",
        token_usage_logger=token_usage_logger,
    )

    development_result = asyncio.run(
        run_development_generation(
            articles=records,
            exchange=exchange,
            effort_chunk="high",
            effort_merger="high",
            models=models,
            token_usage_logger=token_usage_logger,
        )
    )

    merged_developments = development_result["developments"]
    current_developments = merged_developments
    reconcile_result = None

    if previous_topic_states and merged_developments:
        reconcile_result = run_development_reconcile(
            current_developments=merged_developments,
            topic_developments=previous_topic_states,
            exchange=exchange,
            models=models,
            effort="high",
            token_usage_logger=token_usage_logger,
        )

        if reconcile_result is None:
            raise RuntimeError("Development reconciliation failed.")

        decisions = reconcile_result["developments"]

        decisions_by_id = {
            decision["development_id"]: decision["is_changed"]
            for decision in decisions
        }

        expected_ids = {
            development["development_id"]
            for development in merged_developments
        }

        if set(decisions_by_id) != expected_ids or len(decisions) != len(expected_ids):
            raise ValueError("Reconciliation must return each development ID exactly once.")

        current_developments = [
            development
            for development in merged_developments
            if decisions_by_id[development["development_id"]]
        ]

    LOGGER.info(
        "Reconciliation | previous topics: %d | developments retained: %d/%d",
        len(previous_topic_states),
        len(current_developments),
        len(merged_developments),
    )

    market_brief = None
    what_to_watch = None

    if current_developments:
        brief_generation_result = asyncio.run(
            run_brief_generation(
                merged_developments=current_developments,
                exchange=exchange,
                brief_as_of=end_window.isoformat(),
                effort="high",
                models=models,
                token_usage_logger=token_usage_logger,
            )
        )

        market_brief = brief_generation_result["market_brief"]
        what_to_watch = brief_generation_result["what_to_watch"]

    topic_result = {"topics": []}

    if merged_developments:
        topic_result = process_development_to_topic(
            merged_developments=merged_developments,
            exchange=exchange,
            models=models,
            effort="high",
            token_usage_logger=token_usage_logger,
        )

    if topic_result is None:
        raise RuntimeError("Development topic generation failed.")

    return {
        **brief_result,
        "policies": policy_result["policies"],
        "policy_explanation": policy_result["explanation"],
        "merged_developments": development_result,
        "development_reconcile": reconcile_result,
        "reconciled_developments": current_developments,
        "development_topics": topic_result,
        "market_brief": market_brief,
        "what_to_watch": what_to_watch,
    }


def run_news_briefs_pipeline(market: str) -> None:
    """
    Brief every session that has closed since the last one in the state file.
    Normally that is the one session that just closed; after a missed or failed run
    it catches up on each skipped session in order.
    """
    now = datetime.now(MARKETS[market]["timezone"])
    state = read_state(market)

    if state:
        start_window = datetime.fromisoformat(state["end_window"])
        recent_briefs = state["recent_briefs"]

    else:
        # First run: brief only the latest closed session.
        start_window = get_slot_before(
            market, 
            get_slot_before(market, now + timedelta(microseconds=1))
        )
        recent_briefs = []

        LOGGER.info(
            "No state for %s | starting from %s", 
            market, start_window.isoformat()
        )

    brief_windows = build_brief_windows(
        market=market,
        start_window=start_window,
        until=now,
    )

    if not brief_windows:
        LOGGER.info(
            "No %s session has closed since %s, nothing to do", 
            market, 
            start_window.isoformat()
        )
        return

    # The latest window runs up to now, so a brief delayed behind the scrape in the
    # queue still picks up everything that scrape inserted
    brief_windows[-1]["end_window"] = now

    token_usage_logger = TokenUsageLogger()

    for brief_window in brief_windows:
        brief_result = run_brief_window(
            brief_window=brief_window,
            models=MODEL_NAMES,
            previous_topic_states=get_previous_topic_states(
                recent_briefs
            ),
            token_usage_logger=token_usage_logger,
        )

        upsert_news_brief(brief_result)

        recent_briefs = [
            *recent_briefs, 
            brief_result
        ][-PREVIOUS_BRIEFS_FOR_RECONCILE:]

        write_state(market, recent_briefs)

        LOGGER.info(
            "Saved %s %s %s to %s",
            market,
            brief_result["market_date"],
            brief_result["session"],
            BRIEFS_TABLE,
        )

    log_total_cost(token_usage_logger)


def run_news_briefs_backfill(
    market: str, 
    start_date: date, 
    end_date: date
) -> Path:
    """
    Brief every session between two dates into a local file, without touching the table or state.
    """
    market_timezone = MARKETS[market]["timezone"]

    first_day = datetime.combine(
        start_date, 
        time.min, 
        tzinfo=market_timezone
    )

    brief_windows = build_brief_windows(
        market=market,
        start_window=get_slot_before(market, first_day),
        until=datetime.combine(
            end_date, 
            time.max, 
            tzinfo=market_timezone
        ),
    )

    token_usage_logger = TokenUsageLogger()
    brief_results = []

    for brief_window in brief_windows:
        brief_results.append(
            run_brief_window(
                brief_window=brief_window,
                models=MODEL_NAMES,
                previous_topic_states=get_previous_topic_states(brief_results),
                token_usage_logger=token_usage_logger,
            )
        )

    output_path = (
        BACKFILL_OUTPUT_DIR
        / f"brief_{market}_{start_date.isoformat()}_{end_date.isoformat()}.json"
    )

    write_json_output(
        output_path=output_path,
        records=[
            {**brief_result, "news_brief_row": to_news_brief_row(brief_result)}
            for brief_result in brief_results
        ],
    )

    LOGGER.info(
        "Wrote %d brief windows to %s",
        len(brief_results), output_path
    )

    log_total_cost(token_usage_logger)

    return output_path
