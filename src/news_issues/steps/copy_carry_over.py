from ..prompts.display import Slot
from .importance import current_issue_stories

import logging


LOGGER = logging.getLogger(__name__)


def decide_copy(
    development: dict,
    slot: Slot,
    current_by_id: dict[str, dict],
    matched_ids: set[str],
) -> tuple[dict | None, str]:
    match_id = development.get("same_as_current_story")
    
    if match_id is None:
        return None, "new story"

    current_story = current_by_id[match_id]

    if match_id in matched_ids:
        return None, f"rewritten: {match_id} already kept by another story"

    # A story that drops to flash shows only its headline, which still holds.
    # Any other move needs a blurb written for the new slot
    moved_to_flash = current_story["slot"] != slot.value and slot == Slot.FLASH
    
    if current_story["slot"] != slot.value and not moved_to_flash:
        return None, f"rewritten: moved from {current_story['slot']} to {slot.value}"

    current_article_ids = set(current_story["supporting_news_ids"])
    article_ids = set(development["supporting_news_ids"])

    dropped_count = len(current_article_ids - article_ids)
    
    if dropped_count:
        return None, f"rewritten: regrouped, {dropped_count} of its articles moved out"

    new_count = len(article_ids - current_article_ids)
    
    if new_count and development.get("adds_new_fact", True):
        new_fact = development.get("new_fact") or "not stated"
        return None, f"rewritten: {new_count} new articles with a new fact: {new_fact}"

    carried_copy = {
        "event": current_story["event"],
        "headline": current_story["headline"],
        "blurb": None if moved_to_flash else current_story["blurb"],
        "tickers": current_story["tickers"],
    }
    
    moved_note = f", headline kept in flash from {current_story['slot']}" if moved_to_flash else ""
    
    if new_count:
        return carried_copy, f"kept: {new_count} new articles, no new fact{moved_note}"
    
    return carried_copy, f"kept: same articles{moved_note}"


# Marks each placed development with copy_decision, and with carried_copy when
# the display step should reuse the current version's words
def carry_over_copy(
    issue_layout: dict,
    current_issue: dict | None,
) -> dict:
    current_by_id = {
        story["id"]: story
        for story in current_issue_stories(current_issue)
    }
    matched_ids: set[str] = set()

    def mark(development: dict, slot: Slot) -> dict:
        carried_copy, decision = decide_copy(
            development=development,
            slot=slot,
            current_by_id=current_by_id,
            matched_ids=matched_ids,
        )
        if carried_copy is not None:
            matched_ids.add(development["same_as_current_story"])

        LOGGER.info(
            "Copy | %s %s: %s | %s",
            slot.value,
            development.get("same_as_current_story") or "-",
            decision,
            development["event"],
        )

        marked = {**development, "copy_decision": decision}
        if carried_copy is not None:
            marked["carried_copy"] = carried_copy
        return marked

    # The lead first, then the sections in rank order, so the highest-placed
    # story keeps the copy when two developments match one current story
    return {
        **issue_layout,
        "lead": (
            mark(issue_layout["lead"], Slot.LEAD)
            if issue_layout["lead"] is not None
            else None
        ),
        "sections": {
            section: [mark(story, Slot.STORY) for story in stories]
            for section, stories in issue_layout["sections"].items()
        },
        "flash": [mark(story, Slot.FLASH) for story in issue_layout["flash"]],
    }
