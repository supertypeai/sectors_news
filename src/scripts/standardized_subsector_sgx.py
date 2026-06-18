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
        content = file.read()
        if not content.strip():
            return []
        return json.loads(content)


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
 

def get_db(table: str, columns: str = '*', query=None):
    db_query = (
        SUPABASE_CLIENT
        .table(table)
        .select(columns)
    )

    if query:
        db_query = query(db_query)

    response = db_query.execute()

    return response.data


def refresh_sgx_companies(output_path: str):
    data = get_db(
        'sgx_companies',
        query=lambda query_builder: (
            query_builder
            .eq('is_suspended', False)
            .eq('is_active', True)
        )
    )
    company = {}

    for row in data:
        company[row["symbol"]] = {
            "symbol": row["symbol"],
            "name": row["name"],
            "sector": convert_sub_sector_to_kebab(row['sector']),
            "sub_sector": convert_sub_sector_to_kebab(row["sub_sector"]),
        }

    write_json(company, output_path)
    

# def build_sgx_sector(path: str, output: str):
#     records = open_json(path)

#     lookup = {
#         value.get('sub_sector'): value.get('sector')
#         for value in records.values()
#     }   

#     write_json(lookup, output)


# def build_sgx_sub_sector(path: str, output: str):
#     records = open_json(path)

#     sub_sector_dicts = list({
#         record.get('sub_sector')
#         for record in records.values()
#     })
    
#     write_json(sub_sector_dicts, output)


# def standardize_data_db(output: str):
#     response = (
#         SUPABASE_CLIENT 
#         .table('sgx_news')
#         .select('id, sector, timestamp, source, sub_sector, tags, symbols')
#         .execute()
#     )

#     records = response.data 
#     write_json(records, 'sgx_news_db.json')
    
#     for record in records: 
#         sector = record.get('sector')
#         sub_sector = record.get('sub_sector')

#         clean_sector = convert_sub_sector_to_kebab(sector)
        
#         seen = set()
#         clean_subsector = []

#         for item in sub_sector: 
#             clean_item = convert_sub_sector_to_kebab(item)

#             if clean_item in seen:
#                 continue

#             seen.add(clean_item)
#             clean_subsector.append(clean_item)

#         record['sector'] = clean_sector 
#         record['sub_sector'] = clean_subsector 

#     write_json(records, output)


# def run_classifier(
#     body: str, 
#     title: str, 
#     source_scraper: str, 
#     valid_subsectors,
#     sectors_data
# ):
#     sub_sector_llm = CLASSIFIER._classify_data(
#         body=body,
#         category="subsectors",
#         source_scraper=source_scraper,
#         title=title,
#     )
#     print(sub_sector_llm)

#     sub_sector = [sub_sector_llm[0].lower()] if (
#         sub_sector_llm
#         and sub_sector_llm[0].lower() in valid_subsectors
#     ) else []

#     sector = ''
#     for sub in sub_sector:
#         if sub in sectors_data:
#             sector = sectors_data[sub]
#             break 
    
#     return sub_sector, sector


# def upsert_data(payload: list):
#     response = (
#         SUPABASE_CLIENT
#         .table("sgx_news")
#         .upsert(payload, on_conflict="id")
#         .execute()
#     )
#     return response


def get_current_news():
    records = get_db('sgx_news')

    record_with_symbol = [
        record 
        for record in records 
        if record.get('symbols')
    ]

    record_no_symbol = [
        record 
        for record in records 
        if record.get('symbols') == []
    ]

    print(f'length records with symbol: {len(record_with_symbol)} | with no symbol: {len(record_no_symbol)}')

    write_json(record_with_symbol, 'news_with_symbols.json')
    write_json(record_no_symbol, 'news_with_no_symbols.json')

    unique_sub_sector = {
        record.get('sub_sector')[0] 
        for record in record_no_symbol
    }   

    print(f'unique sub_sector in no symbols: {unique_sub_sector}')


def prepare_records_with_symbols(path_records: str): 
    companies = open_json('data/sgx/sgx_companies.json')
    sectors_data = open_json('data/sgx/sectors_data_sgx.json')
    records = open_json(path_records)

    for record in records: 
        symbols = record.get('symbols')
        id = record['id']

        final_sub_sector = {}

        for symbol in symbols: 
            if symbol not in companies:
                print(f'symbol skipped id: {id}')
                continue 

            sub_sector = companies[symbol]['sub_sector']

            final_sub_sector[sub_sector] = None  

        list_final_sub_sector = list(final_sub_sector)

        record['sub_sector'] = list_final_sub_sector

        sector = next((sectors_data[sub] for sub in list_final_sub_sector if sub in sectors_data), None)

        record['sector'] = sector
    
    write_json(records, 'updated_news_with_symbol.json')


def prepare_records_with_no_symbols(path_records: str):
    mapping = {
        "capital-markets":                    ("financial-services",        "asset-management-investment"),
        "internet-retail":                    ("consumer-cyclical",         "retail"),
        "reit-industrial":                    ("reit",                      "reit-industrial"),
        "specialty-industrial-machinery":     ("industrials",               "industrial-machinery-parts"),
        "asset-management":                   ("financial-services",        "asset-management-investment"),
        "food-distribution":                  ("consumer-defensive",        "food-distribution"),
        "banks":                              ("financial-services",        "banks-credit-services"),
        "reit-healthcare-facilities":         ("reit",                      "reit-specialty-healthcare"),
        "gold":                               ("basic-materials",           "metals-mining"),
        "medical-care-facilities":            ("healthcare",                "healthcare-facilities-services"),
        "financial-data-stock-exchanges":     ("financial-services",        "financial-data-shell-companies"),
        "financial-data-and-stock-exchanges": ("financial-services",        "financial-data-shell-companies"),
        "packaging-and-containers":           ("consumer-cyclical",         "packaging-containers"),
        "utilities-regulated-water":          ("utilities",                 "utilites-regulated"),
        "reit-specialty":                     ("reit",                      "reit-specialty-healthcare"),
        "real-estate-services":               ("properties-real-estate",    "real-estate-services"),
        "investment-service":                 ("financial-services",        "asset-management-investment"),
        "entertainment":                      ("communication-services",    "media-entertainment"),
        "integrated-freight-logistics":       ("industrials",               "transportation-logistics"),
        "marine-shipping":                    ("industrials",               "transportation-logistics"),
        "transportation-infrastructure":      ("infrastructures",           "heavy-construction-transport-infrastructure"),
        "food-staples-retailing":             ("consumer-defensive",        "food-distribution"),
    }
    
    records = open_json(path_records)

    for record in records: 
        sub_sector = record['sub_sector'][0]

        new_sector, new_sub_sector = mapping[sub_sector]

        record['sub_sector'] = [new_sub_sector] 
        record['sector'] = new_sector 

    write_json(records, 'updated_news_with_no_symbol.json')


def upsert_payload(payload_path: str): 
    payload = open_json(payload_path)
   
    payload = [
        {
            'id': record['id'],
            'source': record['source'],
            'timestamp': record['timestamp'],
            'symbols': record['symbols'],
            'tags': record['tags'],
            'sector': record['sector'],
            'sub_sector': record['sub_sector'],
        }
        for record in payload
    ]

    # payload = payload[:3]

    # print(payload)

    response = (
        SUPABASE_CLIENT 
        .table('sgx_news')
        .upsert(payload)
        .execute()
    )

    print(len(response.data))


def generate_list_sub_sectors():
    companies = open_json('data/sgx/sgx_companies.json')
    
    sub_sector = {
        record.get('sub_sector')
        for record in companies.values()
    }

    write_json(list(sub_sector), 'data/sgx/subsectors_data_sgx.json')


def regenerate_sectors_data_sgx():
    companies_path = Path("data/sgx/sgx_companies.json")
    output_path = Path("data/sgx/sectors_data_sgx.json")

    with companies_path.open("r") as f:
        companies = json.load(f)

    sectors_data = {}

    for entry in companies.values():
        sub_sector = entry.get("sub_sector", "").strip()
        sector = entry.get("sector", "").strip()

        if sub_sector and sector:
            sectors_data[sub_sector] = sector  # already kebab-case in sgx_companies.json

    with output_path.open("w") as f:
        json.dump(sectors_data, f, indent=2)

    print(f"Written {len(sectors_data)} entries to {output_path}")


if __name__ == '__main__':
    sgx_path = 'data/sgx/sgx_companies.json'
    
    output_sgx_path = 'data/sgx/sgx_companies.json'
    output_sgx_sub_sector = 'test_subsectors_data_sgx.json'
    output_sgx_sector = 'test_sector_data_sgx.json'

    # refresh_sgx_companies(output_sgx_path)

    # get_current_news()
    # prepare_records_with_symbols('news_with_symbols.json')
    # prepare_records_with_no_symbols('news_with_no_symbols.json')

    # generate_list_sub_sectors()
    # regenerate_sectors_data_sgx()

    updated_path_symbols = 'updated_news_with_symbol.json'
    updated_path_no_symbol = 'updated_news_with_no_symbol.json' 

    upsert_payload(updated_path_symbols)

    # build_sgx_sub_sector(output_sgx_path, output_sgx_sub_sector)
    # build_sgx_sector(output_sgx_path, output_sgx_sector)

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

