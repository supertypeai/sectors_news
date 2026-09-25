from scraper_engine.llm.prompt_definitions.structure_summarization import (
    USER_PROMPT, 
    SYSTEM_PROMPT, 
    StructureNewsSummary
) 
from scraper_engine.llm.caller import invoke_structured_llm_async
from scraper_engine.llm.constant import MODEL_NAMES
from scraper_engine.llm.client import TokenUsageLogger


async def get_structure_summary(
    title: str, 
    article: str, 
    source: str, 
    timestamp: str, 
    models: list[str] = MODEL_NAMES,
    effort: str = "high",
    token_usage_logger: TokenUsageLogger | None = None,
):
    if not isinstance(timestamp, str): 
        timestamp = timestamp.strftime("%d %b %Y, %H:%M")

    input_data = {
        "title": title, 
        "article_content": article, 
        "source": source,
        "published_at": timestamp,
    }
    
    response = await invoke_structured_llm_async(
        pydantic_output=StructureNewsSummary,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=USER_PROMPT,
        log_name="Structure Summarization",
        input_data=input_data,
        models=models,
        temperature=0.5,
        effort=effort,
        token_usage_logger=token_usage_logger,
    )    

    return response 
