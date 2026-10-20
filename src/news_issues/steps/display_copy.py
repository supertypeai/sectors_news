from llm.caller import invoke_structured_llm_async
from llm.client import TokenUsageLogger

from ..utils.constant import CONCURRENCY
from ..prompts.display import get_display_system_prompt, DISPLAY_USER_PROMPT, DisplayCopy, Slot

import json
import asyncio
import logging


LOGGER = logging.getLogger(__name__)


def build_display_payload(development: dict) -> str:
    return json.dumps(
        {
            "event": development["event"],
            "title": development["title"],
            "summary": development["summary"],
            "tickers": development["tickers"],
        },
        ensure_ascii=False,
        indent=2,
    )


async def generate_display_copy(
    development: dict,
    slot: Slot,
    semaphore: asyncio.Semaphore,
    models: list[str],
    as_of: str,
    exchange: str,
    effort: str,
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict:
    # A story readers already saw, with nothing new, keeps its words
    if development.get("carried_copy"):
        return {**development, **development["carried_copy"]}

    async with semaphore:
        response = await invoke_structured_llm_async(
            pydantic_output=DisplayCopy,
            system_prompt=get_display_system_prompt(exchange),
            user_prompt=DISPLAY_USER_PROMPT,
            log_name=f"Display copy | {slot.value}",
            input_data={
                "as_of": as_of,
                "slot": slot.value,
                "development": build_display_payload(development=development),
                # Set when readers saw this story earlier today, so the
                # rewrite says what moved on
                "new_fact": json.dumps(development.get("new_fact"), ensure_ascii=False),
            },
            models=models,
            effort=effort,
            token_usage_logger=token_usage_logger,
        )

    if response is None:
        LOGGER.warning(
            "Display copy | no response for %s", 
            development["supporting_news_ids"]
        )
        return {
            **development, 
            "headline": development["title"], 
            "blurb": None
        }

    return {
        **development, 
        "headline": response["headline"], 
        "blurb": response["blurb"],
    }


async def run_display_copy(
    issue_layout: dict,
    models: list[str],
    as_of: str,
    exchange: str = "IDX",
    effort: str = "medium",
    concurrency: int = CONCURRENCY,
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict:
    semaphore = asyncio.Semaphore(concurrency)

    slots = []

    if issue_layout["lead"] is not None:
        slots.append((None, Slot.LEAD, issue_layout["lead"]))

    for section, stories in issue_layout["sections"].items():
        for story in stories:
            slots.append((section, Slot.STORY, story))

    written = await asyncio.gather(
        *(
            generate_display_copy(
                development=development,
                slot=slot,
                semaphore=semaphore,
                models=models,
                as_of=as_of,
                exchange=exchange,
                effort=effort,
                token_usage_logger=token_usage_logger,
            )
            for _, slot, development in slots
        )
    )

    lead = None
    sections = {}

    for (section, slot, _), development in zip(slots, written):
        if slot == Slot.LEAD:
            lead = development
        else:
            sections.setdefault(section, []).append(development)

    # Flash items only show a headline, so the development title is used as is,
    # unless the item keeps the headline readers already saw
    flash = [
        (
            {**development, **development["carried_copy"]}
            if development.get("carried_copy")
            else {
                **development,
                "headline": development["title"],
                "blurb": None
            }
        )
        for development in issue_layout["flash"]
    ]

    return {
        "lead": lead, 
        "sections": sections, 
        "flash": flash
    }
