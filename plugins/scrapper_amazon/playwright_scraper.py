import os
import json
import time
import random
import hashlib
import pandas as pd
from playwright.sync_api import sync_playwright
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
    title_lower = title.lower()
    
    if pd.notna(must_contain) and must_contain.strip():
        reqs = [r.strip().lower() for r in must_contain.split(',')]
        if not all(r in title_lower for r in reqs):
            return False
            
    if pd.notna(must_not_contain) and must_not_contain.strip():
        bans = [b.strip().lower() for b in must_not_contain.split(',')]
        if any(b in title_lower for b in bans):
            return False
            
    return True

def run_scraper():
    if not os.path.exists(CSV_FILE):
        print(f"Erro: Arquivo {CSV_FILE} não encontrado.")
        return

    df = pd.read_csv(CSV_FILE)
    classified_data = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Context with user agent to avoid basic blocks
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for index, row in df.iterrows():
            search_term = row['search_term']
            category = row['category']
            csv_hash = generate_hash(row)
            
            print(f"\nBuscando [{category}]: {search_term}")
            
            # Simple navigation
            url = f"https://www.amazon.com.br/s?k={search_term.replace(' ', '+')}"
            try:
                try:
                    page.goto(url, timeout=60000)
                    time.sleep(random.uniform(3, 6)) # Human delay
                except Exception as e:
                    print(f"Timeout ao carregar a página: {e}")
                    page.screenshot(path="error.png")
                    continue
                    
                # Check for captcha
                if "captcha" in page.title().lower() or page.locator("form[action='/errors/validateCaptcha']").count() > 0:
                    print("⚠️ CAPTCHA detectado! Verificando tela...")
                    page.screenshot(path="captcha.png")
                    continue
                    
                # Extract items
                items = page.locator('[data-component-type="s-search-result"]').all()
                valid_items = []
                
                for item in items:
                    try:
                        title = item.locator('[data-cy="title-recipe"] h2 span').inner_text()
                    except:
                        continue
                        
                    if not validate_title(title, row.get('must_contain'), row.get('must_not_contain')):
                        continue
                        
                    try:
                        price_str = item.locator('[data-cy="price-recipe"] span.a-price span.a-offscreen').first.inner_text()
                        price_val = clean_price(price_str)
                    except:
                        price_val = 0.0
                        price_str = "Sem preço"
                        
                    if price_val == 0.0:
                        continue # Ignore items without price
                        
                    try:
                        link_href = item.locator('[data-cy="title-recipe"] a').get_attribute('href')
                        link = f"https://www.amazon.com.br{link_href}" if link_href and not link_href.startswith('http') else link_href
                    except:
                        link = ""
                        
                    try:
                        image = item.locator('img.s-image').get_attribute('src')
                    except:
                        image = ""
                        
                    valid_items.append({
                        "title": title,
                        "url": link,
                        "price": price_str,
                        "price_val": price_val,
                        "image": image,
                        "csv_ref_hash": csv_hash,
                        "variant_name": search_term # Use search term as the strict variant name
                    })

                if valid_items:
                    # Sort by price and get the cheapest
                    valid_items.sort(key=lambda x: x["price_val"])
                    cheapest = valid_items[0]
                    
                    # Remove helper value
                    del cheapest["price_val"]
                    
                    if category not in classified_data:
                        classified_data[category] = []
                        
                    classified_data[category].append(cheapest)
                    print(f"✅ Encontrado: {cheapest['title'][:50]}... por {cheapest['price']}")
                else:
                    print("❌ Nenhum produto atendeu aos critérios exatos.")

            except Exception as e:
                print(f"Erro ao buscar {search_term}: {e}")

        browser.close()

    # Save output
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(classified_data, f, ensure_ascii=False, indent=4)
        
    print(f"\nFinalizado! Dados classificados salvos em '{OUTPUT_JSON}'.")

if __name__ == "__main__":
    run_scraper()
