from dotenv import load_dotenv

import os
import requests

load_dotenv()

def test_brightdata_rest(target_url: str):
    response = requests.post(
        "https://api.brightdata.com/request",
        headers={
            "Authorization": f"Bearer {os.getenv("BRIGHTDATA_API_KEY")}",
            "Content-Type": "application/json",
        },
        json={
            "zone": os.getenv("BRIGHTDATA_ZONE"),
            "url": target_url,
            "format": "raw",
            "method": "GET",
        },
        timeout=60,
    )

    print("status:", response.status_code)
    print("body:", response.text[:1000])


test_brightdata_rest(
    "https://investor.id/stock/indeks/1"
)

test_brightdata_rest(
    "https://investasi.kontan.co.id/news/"
    "direksi-ketrosden-ketr-kompak-borong-saham-di-harga-rp-200"
)