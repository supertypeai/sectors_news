from langchain.prompts              import ChatPromptTemplate
from langchain_core.output_parsers  import JsonOutputParser

from scraper_engine.llm.client  import get_llm
from scraper_engine.llm.prompts import EntityExtractionPrompts, CompanyNameExtraction
from scraper_engine.config.conf import MODEL_NAMES

import json
import logging 


LOGGER = logging.getLogger(__name__)


def load_sgx_company_data(): 
    with open("./data/sgx/sgx_companies.json", "r") as file:
            company = json.load(file)

    companies_name = []
    for _, value in company.items(): 
        company_name = value.get('name')
        companies_name.append(company_name)

    companies_name_str = ', '.join(companies_name)
    return companies_name_str


def extract_company_name(
    body: str, 
    source_scraper: str
) -> list[str]:
    prompts = EntityExtractionPrompts()

    if source_scraper == 'sgx': 
        user_prompt = prompts.user_prompt_sgx()
        system_prompt = prompts.system_prompt_sgx()
      
    else: 
        user_prompt = prompts.user_prompt_idx()
        system_prompt = prompts.system_prompt_idx()
        
    company_extraction_parser = JsonOutputParser(pydantic_object=CompanyNameExtraction)
    format_instructions = company_extraction_parser.get_format_instructions()

    # combined_text = f"{title} {body}"   
    company_names_desc = load_sgx_company_data()

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ('user', user_prompt )
    ])

    if source_scraper == 'sgx': 
        input_data = {
            'body': body,
            'company_names': company_names_desc,
            'format_instructions': format_instructions
        } 

    else: 
        input_data = {
            'body': body,
            'format_instructions': format_instructions
        }
    
    for model in MODEL_NAMES:
        LOGGER.info(f'LLM used: {model}')
        
        llm = get_llm(model, temperature=0.4)

        try:
            chain = prompt | llm | company_extraction_parser
            
            company_extracted = chain.invoke(input_data)
            
            if 'company' not in company_extracted or 'reason' not in company_extracted:
                LOGGER.warning("Output not complete, trying next LLM...")
                continue

            LOGGER.info(f"[SUCCES] Company extracted for url")
            
            LOGGER.info(f"reason company extraction: {company_extracted.get('reason')}")
            return company_extracted.get('company')
            
        except Exception as error:
            LOGGER.warning(f"LLM failed with error: {error}")
            continue 

    LOGGER.error("All LLMs failed to return a valid summary.")
    return None


if __name__ == "__main__":
    pass 