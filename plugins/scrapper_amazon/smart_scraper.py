import os
import json
import time
import random
import hashlib
import pandas as pd
from curl_cffi import requests
from parsel import Selector
import re

CSV_FILE = "monitor_list.csv"
OUTPUT_JSON = "amazon_classified.json"

def clean_price(price_str):
    if not price_str: return 0.0
    clean = re.sub(r'[^\d.,]', '', price_str)
    if not clean: return 0.0
    clean = clean.replace('.', '').replace(',', '.')
    try:
        return float(clean)
    except:
        return 0.0

def generate_hash(row):
    raw_str = f"{row['search_term']}_{row['category']}_{row['must_contain']}_{row['must_not_contain']}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

def validate_title(title, must_contain, must_not_contain):
    if not title: return False
    title_lower = title.lower()
    
    if pd.notna(must_contain) and str(must_contain).strip():
        reqs = [r.strip().lower() for r in str(must_contain).split(',')]
        if not all(r in title_lower for r in reqs):
            return False
            
    if pd.notna(must_not_contain) and str(must_not_contain).strip():
        bans = [b.strip().lower() for b in str(must_not_contain).split(',')]
        if any(b in title_lower for b in bans):
            return False
            
    return True

def run_scraper():
    if not os.path.exists(CSV_FILE):
        print(f"Erro: Arquivo {CSV_FILE} não encontrado.")
        return

    df = pd.read_csv(CSV_FILE)
    classified_data = {}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Referer': 'https://www.google.com/'
    }

    for index, row in df.iterrows():
        search_term = row['search_term']
        category = row['category']
        csv_hash = generate_hash(row)
        
        print(f"\nBuscando [{category}]: {search_term}")
        
        url = f"https://www.amazon.com.br/s?k={search_term.replace(' ', '+')}"
        try:
            time.sleep(random.uniform(2, 4))
            response = requests.get(url, headers=headers, impersonate="chrome")
            
            if response.status_code == 503:
                print(f"⚠️  Bloqueado pela Amazon (Erro 503 / CAPTCHA)")
                continue
                
            response.raise_for_status()
            selector = Selector(text=response.text)
            items = selector.css('[data-component-type="s-search-result"]')
            
            valid_items = []
            
            for item in items:
                title = item.css('[data-cy="title-recipe"] h2 span::text').get()
                if not title:
                    title = item.css('h2 span::text').get()
                    
                if not validate_title(title, row.get('must_contain'), row.get('must_not_contain')):
                    continue
                    
                price_str = item.css('[data-cy="price-recipe"] span.a-price span.a-offscreen::text').get()
                if not price_str:
                    price_str = item.css('span.a-price span.a-offscreen::text').get()
                    
                price_val = clean_price(price_str)
                if price_val == 0.0:
                    continue
                    
                link_href = item.css('[data-cy="title-recipe"] a::attr(href)').get()
                if not link_href:
                    link_href = item.css('h2 a::attr(href)').get()
                    
                link = f"https://www.amazon.com.br{link_href}" if link_href and not link_href.startswith('http') else link_href
                image = item.css('img.s-image::attr(src)').get()
                
                valid_items.append({
                    "title": title,
                    "url": link or "",
                    "price": price_str,
                    "price_val": price_val,
                    "image": image or "",
                    "csv_ref_hash": csv_hash,
                    "variant_name": search_term
                })

            if valid_items:
                valid_items.sort(key=lambda x: x["price_val"])
                cheapest = valid_items[0]
                del cheapest["price_val"]
                
                if category not in classified_data:
                    classified_data[category] = []
                    
                classified_data[category].append(cheapest)
                print(f"✅ Encontrado: {cheapest['title'][:50]}... por {cheapest['price']}")
            else:
                print("❌ Nenhum produto atendeu aos critérios exatos.")

        except Exception as e:
            print(f"Erro ao buscar {search_term}: {e}")

    # Sobrescreve o json classificado apenas com os itens do CSV!
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(classified_data, f, ensure_ascii=False, indent=4)
        
    print(f"\nFinalizado! Dados classificados salvos em '{OUTPUT_JSON}'.")

if __name__ == "__main__":
    run_scraper()
