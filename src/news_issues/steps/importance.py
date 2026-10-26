from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from llm.caller import invoke_structured_llm
from llm.client import TokenUsageLogger

from ..prompts.importance import get_assignment_system_prompt, ASSIGNMENT_USER_PROMPT, AssignmentResult
from ..utils.constant import MARKET_TIME_ZONES

import json
import logging


LOGGER = logging.getLogger(__name__)


def build_developments_payload(developments: list[dict]) -> str:
    payload = []

    for position, development in enumerate(
        developments, start=1
    ):
        payload.append(
            {
                "id": f"dev_{position:03d}",
                "event": development["event"],
                "title": development["title"],
                "summary": development["summary"],
                "tickers": development["tickers"],
                "article_count": len(development["supporting_news_ids"]),
            }
        )
        
    return json.dumps(payload, ensure_ascii=False, indent=2)


def check_assignment_result(
    development_count: int,
    result: dict,
) -> dict:
    input_ids = {
        f"dev_{position:03d}" 
        for position in range(1, development_count + 1)
    }
    
    assigned_ids = [
        assignment["development_id"] 
        for assignment in result["assignments"]
    ]
    
    id_counts = Counter(assigned_ids)
    
    importance_by_id = {
        assignment["development_id"]: assignment["importance"]
        for assignment in result["assignments"]
    }
    
    lead_id = result["lead_development_id"]
    
    highest_importance = max(
        importance_by_id.values(), 
        default=None
    )
    
    return {
        "unknown_ids": sorted(set(assigned_ids) - input_ids),
        "duplicated_ids": sorted(
            development_id
            for development_id, count in id_counts.items()
            if count > 1
        ),
        "missing_ids": sorted(input_ids - set(assigned_ids)),
        "lead_is_top_scored": (
            lead_id is not None
            and importance_by_id.get(lead_id) == highest_importance
        ),
    }


def build_issue_stories_payload(issue: dict | None) -> str:
    if issue is None:
        return "[]"

    stories = []

    if issue["lead"] is not None:
        stories.append(issue["lead"])

    for section_stories in issue["sections"].values():
        stories.extend(section_stories)

    payload = [
        {
            "event": story["event"],
            "headline": story["headline"],
            "blurb": story["blurb"],
            "tickers": story["tickers"],
        }
        for story in stories
    ]

    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2
    )


def build_previous_cutoff(issue: dict | None, exchange: str) -> str:
    # When the previous issue stopped collecting news, in market time, so a
    # step dated before it counts as already known
    if issue is None or not issue.get("window_end"):
        return "none"

    window_end = datetime.fromisoformat(issue["window_end"].replace("Z", "+00:00"))
    local_end = window_end.astimezone(ZoneInfo(MARKET_TIME_ZONES[exchange]))

    return f"{local_end.day} {local_end:%B %Y, %H:%M} ({MARKET_TIME_ZONES[exchange]})"


def current_issue_stories(current_issue: dict | None) -> list[dict]:
    if current_issue is None:
        return []

    stories = []

    if current_issue["lead"] is not None:
        stories.append(current_issue["lead"])

    for section_stories in current_issue["sections"].values():
        stories.extend(section_stories)

    stories.extend(current_issue.get("flash", []))

    return [story for story in stories if story.get("id")]


def build_current_stories_payload(current_issue: dict | None) -> str:
    payload = [
        {
            "id": story["id"],
            "slot": story["slot"],
            "event": story["event"],
            "headline": story["headline"],
            "blurb": story["blurb"],
            "tickers": story["tickers"],
        }
        for story in current_issue_stories(current_issue)
    ]

    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2
    )


def build_current_lead_payload(current_issue: dict | None) -> str:
    if current_issue is None or current_issue["lead"] is None:
        return "null"

    lead = current_issue["lead"]

    return json.dumps(
        {
            "event": lead["event"],
            "headline": lead["headline"],
        },
        ensure_ascii=False,
        indent=2,
    )


def run_importance(
    developments: list[dict],
    models: list[str],
    as_of: str,
    previous_issue: dict | None = None,
    current_issue: dict | None = None,
    exchange: str = "IDX",
    effort: str = "medium",
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict | None:
    formated_developments = build_developments_payload(
        developments=developments
    )

    response = invoke_structured_llm(
        pydantic_output=AssignmentResult,
        system_prompt=get_assignment_system_prompt(exchange),
        user_prompt=ASSIGNMENT_USER_PROMPT,
        log_name="Importance",
        input_data={
            "developments": formated_developments,
            "previous_stories": build_issue_stories_payload(
                issue=previous_issue
            ),
            "previous_cutoff": build_previous_cutoff(
                issue=previous_issue,
                exchange=exchange,
            ),
            # An earlier run of this same issue, so the lead and layout change
            # between updates only when the news does
            "current_stories": build_current_stories_payload(
                current_issue=current_issue
            ),
            "current_lead": build_current_lead_payload(
                current_issue=current_issue
            ),
            "as_of": as_of,
        },  
        models=models,
        effort=effort,
        token_usage_logger=token_usage_logger,
    )

    if response is None:
        LOGGER.warning("Importance | no response")
        return None

    check = check_assignment_result(
        development_count=len(developments),
        result=response,
    )

    assignment_by_id = {
        assignment["development_id"]: assignment
        for assignment in response["assignments"]
    }

    current_ids = {story["id"] for story in current_issue_stories(current_issue)}
    scored_developments = []

    for position, development in enumerate(developments, start=1):
        development_id = f"dev_{position:03d}"
        assignment = assignment_by_id.get(development_id, {})

        # A match to an id the current version does not hold counts as none
        same_as_current_story = assignment.get("same_as_current_story")
        if same_as_current_story not in current_ids:
            same_as_current_story = None

        adds_new_fact = bool(assignment.get("adds_new_fact", True))
        covered_in_previous_issue = assignment.get("covered_in_previous_issue", False)

        # What readers have not seen yet: against the version they read earlier
        # today when there is one, else against yesterday's issue
        new_fact = (
            assignment.get("new_fact")
            if same_as_current_story is not None and adds_new_fact
            else None
        ) or (
            assignment.get("moved_on_fact")
            if covered_in_previous_issue
            else None
        )

        scored_developments.append({
            "development_id": development_id,
            **development,
            "covered_in_previous_issue": covered_in_previous_issue,
            "same_as_current_story": same_as_current_story,
            "adds_new_fact": adds_new_fact,
            "new_fact": new_fact,
            "section": assignment.get("section", "other"),
            "importance": assignment.get("importance", 1),
        })

        # Every score, so a lead or a missing story can be traced in the logs.
        # A story readers saw yesterday should only rank on what moved on
        LOGGER.info(
            "Importance | %s score %s (%s), %s%s | %s",
            development_id,
            assignment.get("importance", 1),
            assignment.get("importance_basis"),
            assignment.get("section", "other"),
            (
                f", covered yesterday, moved on: {assignment.get('moved_on_fact') or 'nothing'}"
                if covered_in_previous_issue
                else ""
            ),
            development["event"],
        )

    return {
        "lead_development_id": response["lead_development_id"],
        "assignments": scored_developments,
        "check": check,
    }
