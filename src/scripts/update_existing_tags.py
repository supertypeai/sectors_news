from langchain.prompts              import PromptTemplate
from langchain_core.output_parsers  import JsonOutputParser
from langchain_core.runnables       import RunnableParallel
from operator                       import itemgetter
from datetime                       import datetime, timedelta
from typing                         import List, Dict
from groq                           import RateLimitError

from scraper_engine.llm.client  import LLMCollection, invoke_llm
from scraper_engine.llm.prompts import (ClassifierPrompts, TagsClassification)

from scraper_engine.database.client  import SUPABASE_CLIENT

import json 
import os 
import traceback
import logging 


LOGGER = logging.getLogger(__name__)

LLMCOLLECTION = LLMCollection()
PROMPTS = ClassifierPrompts()


def get_unique_tags() -> list[str]:
    """
    Load unique tags from a JSON file.

    Returns:
        list: A list of unique tags loaded from "data/unique_tags.json".
    """
    with open("data/unique_tags.json", "r") as file:
        data_tags = json.load(file)
        data_tags = data_tags.get('tags')
    return data_tags


def get_existing_data(start_date: str) -> list[dict]:
    """
    Fetch existing data from the Supabase database based on a cutoff date.

    Args:
        start_date (str): The cutoff date in ISO format (YYYY-MM-DDTHH:MM:SS).

    Returns:
        list[dict]: A list of records containing "id", "tags", "body", and "timestamp".
    """
    try:
        response = (
            SUPABASE_CLIENT.table("idx_news")
            .select("id, tags, body, source, timestamp")
            .gte("timestamp", start_date)   
            .lt("timestamp", (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d"))     
            .not_.ilike("source", "%https://www.idx.co.id/StaticData%") 
            .order("timestamp", desc=True)  
            .execute()
        )
        return response.data

    except Exception as error:
        LOGGER.error(f"Error fetching data from Supabase: {error}")
        return []


def load_progress_data(filename: str = "data/data_to_update_tags.json") -> List[Dict]:
    """
    Load progress data from a JSON file.

    Args:
        filename (str): The path to the progress file. Defaults to "data/data_to_update_tags.json".

    Returns:
        list[dict]: A list of records loaded from the file, or an empty list if the file does not exist.
    """
    if not os.path.exists(filename):
        LOGGER.info(f"No data old tags file found at {filename}")
        return []
    
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
            LOGGER.info(f"Loaded {len(data)} records from {filename}")
            return data
        
    except (json.JSONDecodeError, KeyError) as error:
        LOGGER.error(f"Error loading progress file: {error}")
        return []


def save_progress_data(batch_data: list[dict]):
    """
    Save progress data to a JSON file.

    Args:
        batch_data (list[dict]): The batch data to save.
    """
    try:
        with open("data/data_to_update_tags.json", "w", encoding="utf-8") as file:
            json.dump(batch_data, file, ensure_ascii=False, indent=2)
    except Exception as file_err:
        LOGGER.error(f"Error saving data to file: {file_err}")


def create_sentiment_indexing(data_tags: list[dict]) -> dict[str]:
    """
    Create a sentiment index mapping article IDs to their sentiment tags.

    Args:
        data_tags (list[dict]): A list of records containing "id" and "tags".

    Returns:
        dict: A dictionary mapping article IDs to their sentiment tags.
    """
    index_sentiment = {}
    for data in data_tags:
        sentiment = data.get('tags')[-1]
        id = data.get('id')
        index_sentiment[id] = sentiment
    return index_sentiment


def get_tags_llm(tags: list[str], body: str) -> str:
    """
    Use an LLM to classify and extract tags for an article.

    Args:
        tags (list): The existing tags for the article.
        body (str): The body content of the article.

    Returns:
        str: The extracted tags as a string, or None if all LLMs fail.
    """
    # Get the prompt template for company extraction
    template = PROMPTS.get_tags_prompt()

    # Create a company extraction parser using the JsonOutputParser
    company_extraction_parser = JsonOutputParser(pydantic_object=TagsClassification)

    # Prepare the prompt with the template and format instructions
    company_prompt = PromptTemplate(
        template=template, 
        input_variables=["tags", "body"],
        partial_variables={
            "format_instructions": company_extraction_parser.get_format_instructions()
        }
    )

    # Create a runnable system that will handle the article input
    runnable_company_system = RunnableParallel(
            {   
                "tags": itemgetter("tags"),
                "body": itemgetter("body")
            }
        )

    # Prepare the input data for the LLM
    input_data = {"tags":tags, "body": body}
    
    for llm in LLMCOLLECTION.get_llms():
        try:
            # Create a summary chain that combines the system, prompt, and LLM
            summary_chain = (
                runnable_company_system
                | company_prompt
                | llm 
                | company_extraction_parser
            )
            
            tags = invoke_llm(summary_chain, input_data)

            if tags is None:
                LOGGER.warning("API call failed after all retries, trying next LLM...")
                continue

            LOGGER.info(f"[SUCCES] Tags extracted for url")
            return tags.get('tags')

        except RateLimitError as error:
            error_message = str(error).lower()
            if "tokens per day" in error_message or "tpd" in error_message:
                LOGGER.warning(f"LLM: {llm.model_name} hit its daily token limit. Moving to next LLM")
                continue 

        except json.JSONDecodeError as error:
            LOGGER.error(f"Failed to parse JSON response: {error}, trying next LLM...")
            continue
            
        except Exception as error:
            LOGGER.warning(f"LLM failed with error: {error}")
            continue 

    LOGGER.error("All LLMs failed to return a valid summary.")
    return None


def run_update_existing_tags(batch_data: list[dict[str]], unique_tags: list[str], 
                             sentiment_index: dict[str], batch_num: int):
    """
    Process and update tags for a batch of articles.

    Args:
        batch_data (list[dict]): The batch of articles to process.
        unique_tags (list[str]): A list of unique tags.
        sentiment_index (dict[str]): A dictionary mapping article IDs to sentiment tags.
        batch_num (int): The current batch number for logging.
    """
    for index, data in enumerate(batch_data):
        body = data.get('body')
        raw_id = data.get('id')

        try:
            new_tags = get_tags_llm(unique_tags, body)
            sentiment = sentiment_index.get(raw_id)
            if sentiment:
                new_tags.append(sentiment)

            new_tags = [str(tag) for tag in new_tags]
            LOGGER.info(f"Batch {batch_num}, Record {index+1}/{len(batch_data)} - ID {raw_id}: {new_tags}")

            # Update Supabase
            response = (
                SUPABASE_CLIENT.table("idx_news")
                .update({"tags": new_tags})
                .eq("id", int(raw_id))
                .execute()
            )

            LOGGER.info(f"Updated row {raw_id}: {response.data}")

        except Exception as error:
            LOGGER.error(f"Error processing ID {raw_id}: {error}")
            raise


def run_batch_update(unique_tags: list[str], sentiment_index: dict[str], batch_size: int = 50):
    """
    Run the batch update process for updating tags in the database.

    Args:
        unique_tags (list[str]): A list of unique tags.
        sentiment_index (dict[str]): A dictionary mapping article IDs to sentiment tags.
        batch_size (int): The number of records to process in each batch. Defaults to 50.
    """
    try:
        remaining_data = load_progress_data()

        if not remaining_data:
            LOGGER.info("No remaining data to process. Job complete!")
            # Clean up progress file when done
            if os.path.exists("data/data_to_update_tags.json"):
                os.remove("data/data_to_update_tags.json")
                LOGGER.info("Progress file removed - all processing complete!")
            return

        LOGGER.info(f"Found {len(remaining_data)} records remaining to process")

        # Get the batch to process
        current_batch = remaining_data[:batch_size]
        remaining_after_batch = remaining_data[batch_size:]

        # Calculate batch number for logging
        total_records = len(remaining_data)
        batch_num = ((1967 - total_records) // batch_size) + 1
        
        # Process the current batch
        run_update_existing_tags(current_batch, unique_tags, sentiment_index, batch_num)

        # Override remaining data to json
        save_progress_data(remaining_after_batch)

    except Exception as error:
        LOGGER.error(f"Error in batch update process: {error}")
        LOGGER.error(f"Traceback: {traceback.format_exc()}")
        raise error


if __name__ == "__main__":
    cutoff_date = "2025-06-01T23:59:59"
    data = get_existing_data(cutoff_date)
    unique_tags = get_unique_tags()
    sentiment_index = create_sentiment_indexing(data)
    run_batch_update(unique_tags, sentiment_index)
    

    
