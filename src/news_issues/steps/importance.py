from collections import Counter

from llm.caller import invoke_structured_llm
from llm.client import TokenUsageLogger

from ..prompts.importance import get_assignment_system_prompt, ASSIGNMENT_USER_PROMPT, AssignmentResult

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


def build_previous_stories_payload(previous_issue: dict | None) -> str:
    if previous_issue is None:
        return "[]"

    stories = []
    
    if previous_issue["lead"] is not None:
        stories.append(previous_issue["lead"])
    
    for section_stories in previous_issue["sections"].values():
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


def run_importance(
    developments: list[dict],
    models: list[str],
    as_of: str,
    previous_issue: dict | None = None,
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
            "previous_stories": build_previous_stories_payload(
                previous_issue=previous_issue
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

    scored_developments = []

    for position, development in enumerate(developments, start=1):
        development_id = f"dev_{position:03d}"
        assignment = assignment_by_id.get(development_id, {})

        scored_developments.append({
            "development_id": development_id,
            **development,
            "covered_in_previous_issue": assignment.get("covered_in_previous_issue", False),
            "section": assignment.get("section", "other"),
            "importance": assignment.get("importance", 1),
        })

    return {
        "lead_development_id": response["lead_development_id"],
        "assignments": scored_developments,
        "check": check,
    }
