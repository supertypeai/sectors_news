from preprocessing_articles.extract_summary_news import summarize_news


test_finansial = "https://finansial.bisnis.com/read/20250814/215/1902244/bpjs-ketenagakerjaan-gandeng-djp-lindungi-pekerja-tegakkan-aturan"
test_kontan = 'https://investasi.kontan.co.id/news/rupiah-menguat-ke-rp-16097-per-dolar-as-berikut-sentimen-penopangnya'

title, body = summarize_news(test_kontan)
print(title +'\n')
print(body)


