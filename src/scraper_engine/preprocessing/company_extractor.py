from scraper_engine.llm.prompt_definitions.entity_extraction import (
    EntityExtractionPrompts,
    CompanyNameExtraction,
)
from scraper_engine.database.metadata import load_company_data_sgx
from scraper_engine.llm.caller import invoke_structured_llm_async
from scraper_engine.llm.client import TokenUsageLogger
from scraper_engine.llm.constant import MODEL_NAMES

import logging 


LOGGER = logging.getLogger(__name__)


def load_sgx_company_data(): 
    company = load_company_data_sgx()

    companies_name = []

    for _, value in company.items(): 
        company_name = value.get('name')
        companies_name.append(company_name)

    companies_name_str = ', '.join(companies_name)

    return companies_name_str


async def extract_company_name(
    title: str, 
    body: str, 
    source_scraper: str,
    effort: str = "low",
    models: list[str] =  MODEL_NAMES,
    token_usage_logger: TokenUsageLogger | None = None
) -> list[dict]:
    prompts = EntityExtractionPrompts()

    if source_scraper == "sgx": 
        user_prompt = prompts.user_prompt_sgx()
        system_prompt = prompts.system_prompt_sgx()
        company_names_desc = load_sgx_company_data()
        
        input_data = {
            "title": title, 
            "body": body,
            "company_names": company_names_desc
        } 

    elif source_scraper == "idx": 
        user_prompt = prompts.user_prompt_idx()
        system_prompt = prompts.system_prompt_idx()

        input_data = {
            "title": title,
            "body": body
        }

    result = await invoke_structured_llm_async(
        pydantic_output=CompanyNameExtraction,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        log_name="Company extraction",
        input_data=input_data,
        models=models,
        effort=effort,
        is_log_raw_response=True,
        token_usage_logger=token_usage_logger,
    )

    # LOGGER.info(
    #     "[Company Extraction] Reasoning: %s", 
    #     result.get("explanation")
    # )

    return result.get("companies")
