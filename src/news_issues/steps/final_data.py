def get_final_data_clean(
    display_result: dict,
    what_to_watch_result: dict | None,
) -> dict:
    display_records = {
        **display_result,
        "what_to_watch": (what_to_watch_result or {}).get("items", []),
    }

    final_clean = {}

    for key, value in display_records.items(): 
        if key == "lead":
            final_clean[key] = {} if value is None else {
                "headline": value["headline"],
                "blurb": value["blurb"],
                "tickers": value["tickers"],
                "supporting_news": value["supporting_news"],
            }

        elif key == "sections": 
            final_clean[key] = {}

            for section_key, section_items in value.items():
                final_clean[key][section_key] = [
                    {
                        "headline": item["headline"],
                        "blurb": item["blurb"],
                        "tickers": item["tickers"],
                        "supporting_news": item["supporting_news"],
                    }
                    for item in section_items
                ]
            
        elif key == "flash":
            final_clean[key] = [
                {
                    "headline": item["headline"],
                    "blurb": item["blurb"],
                    "tickers": item["tickers"],
                    "supporting_news": item["supporting_news"],
                }
                for item in value
            ]

        elif key == "what_to_watch":
            final_clean[key] = [
                {
                    "sort_date": item["sort_date"],
                    "timing_label": item["timing_label"],
                    "title": item["title"],
                    "tickers": item["tickers"],
                    "supporting_news": item["supporting_news"],
                }
                for item in value
            ]

    return final_clean
