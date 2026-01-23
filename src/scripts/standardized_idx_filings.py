from datetime import datetime, timedelta, timezone

from scraper_engine.database.client import SUPABASE_CLIENT
from scraper_engine.preprocessing.extract_summary_news import normalize_dot_case

import pytz
import re 
import json 
import os 
import logging 

LOGGER = logging.getLogger(__name__)

def get_filings_data(
    base_dir: str,
    start_date: str | None = None, 
    end_date: str | None = None
) -> list[dict[str, any]]:
    try:
        tz_wib = pytz.timezone("Asia/Jakarta")
       
        if start_date and end_date:
            # Convert provided dates to WIB datetime range
            start_wib = tz_wib.localize(datetime.strptime(start_date, "%Y-%m-%d"))
            end_wib = tz_wib.localize(datetime.strptime(end_date, "%Y-%m-%d")) + timedelta(days=1)
        else:
            # Default today
            now_wib = datetime.now(tz_wib)
            start_wib = now_wib.replace(hour=0, minute=0, second=0, microsecond=0)
            end_wib = start_wib + timedelta(days=1)

        # Convert to UTC for Supabase query
        start_utc = start_wib.astimezone(timezone.utc).isoformat()
        end_utc = end_wib.astimezone(timezone.utc).isoformat()

        print(f"Fetching filings between {start_utc} and {end_utc}")

        response = (
            SUPABASE_CLIENT
            .table("idx_news")
            .select("*")
            .gte("created_at", start_utc)
            .lt("created_at", end_utc)
            .ilike("source", "%https://www.idx.co.id/%")
            .execute()
        )

        print(f'length data to process: {len(response.data)}')

        with open(f'{base_dir}/legacy_data_filings_to_update_{start_date}_{end_date}.json', 'w', encoding='utf-8') as file:
            json.dump(response.data, file, ensure_ascii=False, indent=4)

        return response.data or []

    except Exception as error:
        LOGGER.error(f"Error fetching filings data: {error}")
        return []


def upsert_to_db(payload: list[dict[str, any]]):
    try:
        response = (
             SUPABASE_CLIENT
            .table("idx_news")         
            .upsert(payload, on_conflict=['id'])             
            .execute()
        )

        if response.data:
            print(f"Upsert successful: {len(payload)} records")
        
    except Exception as error:
        LOGGER.error(f'Error upsert: {error}')


def replace_first_sentence(body: str) -> str:
    parts = body.split('.', 1)
    if len(parts) == 1:
        first_sentence = parts[0]
        rest = ""
    else:
        first_sentence, rest = parts[0], parts[1]

    # Replace only in the first sentence
    first_sentence = re.sub(r'\b[Ss]ell\b', 'sold', first_sentence)
    first_sentence = re.sub(r'\b[Bb]uy\b', 'bought', first_sentence)

    return f"{first_sentence.strip()}.{rest}" if rest else first_sentence.strip()


def standardized_body_and_title(payload_filings: list[dict[str, any]]) -> list[dict]:
    new_payload_filings = []
    
    for index, payload in enumerate(payload_filings):
        print(f'processing {index+1}')
        
        body = payload.get('body')
        title = payload.get('title')

        body = replace_first_sentence(body)
        body = re.sub(r' +', ' ', body).strip()
        payload['body'] = normalize_dot_case(body)

        new_title = re.sub(r'\b[Tt]ransaction of\b', 'Shares of', title)
        payload['title'] = new_title
        
        new_payload_filings.append(payload)

    return new_payload_filings


def run_standardization_numbers(
    start_date: str | None = None, 
    end_date: str | None = None,
    is_save: bool = True
):
    try:
        base_dir = 'new_filings_output'
        os.makedirs(base_dir, exist_ok=True)

        payload_filings = get_filings_data(base_dir, start_date, end_date)
        
        if not payload_filings:
            print('Data filings not found in db')
            return None 
        
        new_payload_filings = standardized_body_and_title(payload_filings)
        
        if is_save:
            with open(f'{base_dir}/new_filings_{start_date}_{end_date}.json', 'w', encoding='utf-8') as file:
                json.dump(new_payload_filings, file, ensure_ascii=False, indent=4)

        upsert_to_db(new_payload_filings)

    except Exception as error:
        LOGGER.error(f'Error standardization numbers: {error}', exc_info=True)
        return None 


if __name__ == '__main__':
    today = datetime.now().date()
    end_date = today
    start_date = today - timedelta(days=3)

    run_standardization_numbers(
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    )

    # run_standardization_numbers("2025-11-23", "2025-11-26")
    