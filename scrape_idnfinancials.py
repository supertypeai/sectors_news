import requests
from bs4 import BeautifulSoup
import json
import csv
import argparse

# Fetching news data from idnfinancials using requests
def fetch_news(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    return soup

def extract_news(soup):
    articles = []
    for item in soup.find_all('article'):
        div = item.find('div', class_='col-8')
        if div:  
          title = div.find('h2', class_='title').find('a').text
          body = div.find('p', class_='summary').text
          source = div.find('h2', class_='title').find('a')['href']
          timestamp = div.find('p', class_='date-published')['data-date']
          articles.append({'title': title, 'body': body, 'source': source, 'timestamp': timestamp})
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

def main():
  url = 'https://www.idnfinancials.com/news'

  parser = argparse.ArgumentParser(description="Script for scraping data from idnfinancials")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="idnarticles")
  parser.add_argument("--csv", action='store_true', help="Flag to indicate write to csv file")

  args = parser.parse_args()

  num_page = args.page_number

  soup = fetch_news(url)
  articles = extract_news(soup)

  for i in range(1, num_page):
    soup = fetch_news(url + f"/page/{i}")
    articles.extend(extract_news(soup))   
    
  write_json(articles, args.filename)

  if args.csv:
     write_csv(args.filename)

if __name__ == "__main__":
    main()