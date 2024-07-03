import json
import csv
import argparse
import ssl
import urllib.request
import os

ssl._create_default_https_context = ssl._create_unverified_context

# Fetching news data from idnfinancials using requests
def fetch_news(url):
    proxy = os.environ.get("proxy")
    print("proxy", proxy)

    proxy_support = urllib.request.ProxyHandler({'http': proxy,'https': proxy})
    opener = urllib.request.build_opener(proxy_support)
    urllib.request.install_opener(opener)

    with urllib.request.urlopen(url) as response:
      data = response.read()
      data = json.loads(data)

    # write_json(data, "testidxsoup")

    # with open("./data/testidxsoup.json", "r") as f:
    #    data = json.loads(f.read())

    articles = []

    for item in data['Items']:
       title = item['Title']
       timestamp = item['PublishedDate']
       body = item['Summary']
       source = item['Links'][0]['Href']
       tags = item['Tags']
       articles.append({'title': title, 'body': body, 'source': source, 'timestamp': timestamp, 'tags': tags})
    return articles

def write_json(jsontext, filename):
  with open(f'./data/{filename}.json', 'w') as f:
    json.dump(jsontext, f, indent=4)

def write_file_soup(filetext, filename):
  with open(f'./data/{filename}.txt', 'w', encoding='utf-8') as f:
    f.write(filetext.prettify())

def write_csv(filename):
  with open(f'./data/{filename}.json', 'r', encoding='utf-8') as json_file:
    data = json.load(json_file)

  with open(f'./data/{filename}.csv', 'w', newline='', encoding='utf-8') as csv_file:
    
      # Create a CSV writer object
      csv_writer = csv.writer(csv_file)
        
      # Write the header
      header = data[0].keys()
      csv_writer.writerow(header)

      # Write the data rows
      for item in data:
        csv_writer.writerow(item.values())

def get_page(page_num, page_size):
   return f"https://www.idx.co.id/primary/NewsAnnouncement/GetNewsSearch?locale=id-id&pageNumber={page_num}&pageSize={page_size}"

def main():

  parser = argparse.ArgumentParser(description="Script for scraping data from idx")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("page_size", type=int, default=100, help="Page size max is 1000")
  parser.add_argument("filename", type=str, default="idxarticles")
  parser.add_argument("--csv", action='store_true', help="Flag to indicate write to csv file")

  args = parser.parse_args()

  num_page = args.page_number
  size_page = args.page_size
  
  articles = fetch_news(get_page(1, size_page))

  for i in range(1, num_page):
    articles.extend(fetch_news(get_page(i, size_page))) 
    
  write_json(articles, args.filename)

  if args.write_csv:
     write_csv(args.filename)

if __name__ == "__main__":
    main()