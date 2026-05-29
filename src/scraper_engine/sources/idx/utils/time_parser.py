from datetime import timedelta, datetime
from zoneinfo import ZoneInfo

import re 


WIB = ZoneInfo("Asia/Jakarta")


def parse_relative_time(raw: str) -> str | None:
    if not raw:
        return None

    now = datetime.now(WIB)

    if matched := re.search(r'(\d+)\s*menit', raw):
        return (now - timedelta(minutes=int(matched.group(1)))).strftime("%Y-%m-%d %H:%M:%S")
    
    if matched := re.search(r'(\d+)\s*jam', raw):
        return (now - timedelta(hours=int(matched.group(1)))).strftime("%Y-%m-%d %H:%M:%S")
    
    if matched := re.search(r'(\d+)\s*hari', raw):
        return (now - timedelta(days=int(matched.group(1)))).strftime("%Y-%m-%d %H:%M:%S")

    return None