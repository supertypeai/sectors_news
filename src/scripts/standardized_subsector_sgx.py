from pathlib import Path 

from scraper_engine.database.client import SUPABASE_CLIENT
from scraper_engine.preprocessing.classifier import CLASSIFIER, load_sub_sectors_data_sgx
from scraper_engine.database.metadata import (
    get_sectors_data_sgx, 
)

import json 
import re 


def open_json(path: str):
    path = Path(path) 

    with path.open('r') as file: 
        return json.load(file)


def write_json(records: list, path: str): 
    path = Path(path)

    with path.open('w') as file: 
        json.dump(records, file, indent=2)


def build_lookup_companies(path: str):
    records = open_json(path)

    lookup = {
        value.get('sub_sector'): value
        for key, value in records.items()
    }

    print(lookup)


def convert_sub_sector_to_kebab(sub_sector: str):
    result = (
        sub_sector
        .replace("&", "")
        .replace(",", "")
        .replace("  ", " ")
        .replace(" ", "-")
        .lower()
    )
    return re.sub(r'-+', '-', result)
 

def refresh_sgx_companies(output_path: str):
    response = (
        SUPABASE_CLIENT 
        .table('sgx_companies')
        .select('symbol, sector, name, sub_sector')
        .execute()
    ) 

    company = {}
    for row in response.data:
        company[row["symbol"]] = {
            "symbol": row["symbol"],
            "name": row["name"],
            "sector": convert_sub_sector_to_kebab(row['sector']),
            "sub_sector": convert_sub_sector_to_kebab(row["sub_sector"]),
        }

    write_json(company, output_path)
    

def build_sgx_sector(path: str, output: str):
    records = open_json(path)

    lookup = {
        value.get('sub_sector'): value.get('sector')
        for value in records.values()
    }   

    write_json(lookup, output)


def build_sgx_sub_sector(path: str, output: str):
    records = open_json(path)

    sub_sector_dicts = list({
        record.get('sub_sector')
        for record in records.values()
    })
    
    write_json(sub_sector_dicts, output)


def standardize_data_db(output: str):
    response = (
        SUPABASE_CLIENT 
        .table('sgx_news')
        .select('id, sector, timestamp, source, sub_sector, tags, symbols')
        .execute()
    )

    records = response.data 
    write_json(records, 'sgx_news_db.json')
    
    for record in records: 
        sector = record.get('sector')
        sub_sector = record.get('sub_sector')

        clean_sector = convert_sub_sector_to_kebab(sector)
        
        seen = set()
        clean_subsector = []

        for item in sub_sector: 
            clean_item = convert_sub_sector_to_kebab(item)

            if clean_item in seen:
                continue

            seen.add(clean_item)
            clean_subsector.append(clean_item)

        record['sector'] = clean_sector 
        record['sub_sector'] = clean_subsector 

    write_json(records, output)


def run_classifier(
    body: str, 
    title: str, 
    source_scraper: str, 
    valid_subsectors,
    sectors_data
):
    sub_sector_llm = CLASSIFIER._classify_data(
        body=body,
        category="subsectors",
        source_scraper=source_scraper,
        title=title,
    )
    print(sub_sector_llm)

    sub_sector = [sub_sector_llm[0].lower()] if (
        sub_sector_llm
        and sub_sector_llm[0].lower() in valid_subsectors
    ) else []

    sector = ''
    for sub in sub_sector:
        if sub in sectors_data:
            sector = sectors_data[sub]
            break 
    
    return sub_sector, sector


def upsert_data(payload: list):
    response = (
        SUPABASE_CLIENT
        .table("sgx_news")
        .upsert(payload, on_conflict="id")
        .execute()
    )
    return response


if __name__ == '__main__':
    sgx_path = 'data/sgx/sgx_companies.json'
    
    output_sgx_path = 'test_sgx_companies.json'
    output_sgx_sub_sector = 'test_subsectors_data_sgx.json'
    output_sgx_sector = 'test_sector_data_sgx.json'

    refresh_sgx_companies(output_sgx_path)

    build_sgx_sub_sector(output_sgx_path, output_sgx_sub_sector)
    build_sgx_sector(output_sgx_path, output_sgx_sector)

    # standardize_data_db('sgx_news_db_standardized.json')

#     body = """ 
# Former CEO and founder Pang Gek Teng was charged in Singapore State Courts with twelve offences, including nine counts of cheating, one count of forgery, one count of attempted cheating and one count of criminal breach of trust. The charges relate to the alleged misappropriation of S$242,738.11 from Surrey Hills Holdings between 3 April 2023 and 28 February 2024, as well as fraudulent schemes that duped victims of more than S$400,000 and involved a forged S$20,000 invoice from AC Global Consulting. Pang was dismissed from Surrey Hills Holdings on 26 March 2023 and faces up to 10 years’ jail for cheating or forgery and up to 20 years for criminal breach of trust, with the case adjourned to 10 July.
#     """
#     title = """ 
#     Surrey Hills Holdings former CEO Pang Gek Teng charged with embezzling S$242,738
# """
#     valid_subsectors = load_sub_sectors_data_sgx()
#     sectors_data = get_sectors_data_sgx()

#     sub_sector, sector = run_classifier(
#         body=body, 
#         title=title, 
#         source_scraper='sgx', 
#         valid_subsectors=valid_subsectors, 
#         sectors_data=sectors_data
#     )   

#     print(f'sub sector: {sub_sector} | sector: {sector}')

    # payload= open_json('sgx_news_db_standardized.json')
    # upsert_data(payload)

# uv run -m scripts.standardized_subsector_sgx

