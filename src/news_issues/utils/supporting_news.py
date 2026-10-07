import logging


LOGGER = logging.getLogger(__name__)


def build_supporting_news(
    news_ids: list[int],
    news_by_id: dict[int, dict],
) -> list[dict]:
    supporting_news = []

    for news_id in news_ids:
        news_record = news_by_id.get(news_id)

        if news_record is None:
            LOGGER.warning("Supporting news %s not found in news records", news_id)
            continue

        supporting_news.append({
            "id": news_record["id"],
            "title": news_record["title"],
            "sector": news_record["sector"],
            "sub_sector": news_record["sub_sector"],
            "source": news_record["source"],
            "thumbnail": news_record["thumbnail"]
        })

    return supporting_news


def with_supporting_news(
    story: dict,
    news_by_id: dict[int, dict],
) -> dict:
    # Swap supporting_news_ids for the article details shown with each story
    updated_story = {
        key: value
        for key, value in story.items()
        if key != "supporting_news_ids"
    }
    updated_story["supporting_news"] = build_supporting_news(
        news_ids=story["supporting_news_ids"],
        news_by_id=news_by_id,
    )
    return updated_story


def attach_supporting_news(
    display_result: dict,
    news_records: list[dict],
) -> dict:
    news_by_id = {
        news_record["id"]: news_record 
        for news_record in news_records
    }

    return {
        "lead": (
            with_supporting_news(display_result["lead"], news_by_id)
            if display_result["lead"] is not None
            else None
        ),
        "sections": {
            section: [with_supporting_news(story, news_by_id) for story in stories]
            for section, stories in display_result["sections"].items()
        },
        "flash": [
            with_supporting_news(story, news_by_id)
            for story in display_result["flash"]
        ],
    }


def attach_what_to_watch_supporting_news(
    what_to_watch_result: dict | None,
    news_records: list[dict],
) -> dict | None:
    if what_to_watch_result is None:
        return None

    news_by_id = {news_record["id"]: news_record for news_record in news_records}

    return {
        **what_to_watch_result,
        "items": [
            with_supporting_news(item, news_by_id)
            for item in what_to_watch_result["items"]
        ],
    }
