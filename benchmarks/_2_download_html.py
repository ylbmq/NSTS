import json
import time
import random
import requests
from bs4 import BeautifulSoup
import os
import gc
from pathlib import Path
from tqdm import tqdm
from typing import Dict

# --- Selenium Imports ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

DYNAMIC_SITES = ["google"]

# --- Configuration ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ==========================================
# PHASE 1: STATIC PROCESSOR (Requests)
# ==========================================

class StaticProcessor:
    def __init__(self, config: Dict):
        self.name = config["name"]
        self.input_path = config["input"]
        self.output_path = config["output"]
        self.items = []
        self.processed_urls = set()
        self.file_handle = None
        self.pbar = None
        
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_processed()
        self._load_items()
        
        # Open file for appending
        self.file_handle = open(self.output_path, 'a', encoding='utf-8')

    def _load_processed(self):
        if self.output_path.exists():
            with open(self.output_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if "url" in data:
                            self.processed_urls.add(data["url"])
                    except json.JSONDecodeError:
                        continue

    def _load_items(self):
        if not self.input_path.exists():
            return
        
        with open(self.input_path, 'r', encoding='utf-8') as f:
            all_items = json.load(f)
            
        self.items = [item for item in all_items if item.get("url") not in self.processed_urls]
        del all_items # Free memory
        
        if len(self.items) > 0:
            self.pbar = tqdm(total=len(self.items), desc=f"{self.name}", unit="pg")

    def run(self):
        while self.items:
            item = self.items[0]
            url = item.get("url")
            
            try:
                response = requests.get(url, headers=HEADERS, timeout=15)
                
                # Rate Limiting
                if response.status_code in [403, 429]:
                    print(f"\n🛑 [{self.name}] Rate Limited. Waiting 60s...")
                    time.sleep(60)
                    continue

                # Error Handling
                if response.status_code != 200:
                    print(f"\n⚠️ [{self.name}] Failed {url} ({response.status_code}).")
                    self.items.pop(0)
                    self.pbar.update(1)
                    continue

                # Success
                self._save_record(url, response.text)
                time.sleep(random.uniform(1.0, 2.0))

            except Exception as e:
                print(f"\n❌ [{self.name}] Error: {e}")
                time.sleep(5)

    def _save_record(self, url, html):
        record = {"url": url, "html": html}
        self.file_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.file_handle.flush()
        self.items.pop(0)
        self.pbar.update(1)

    def close(self):
        if self.file_handle: self.file_handle.close()
        if self.pbar: self.pbar.close()

# ==========================================
# PHASE 2: DYNAMIC PROCESSOR (Selenium)
# ==========================================

def get_dynamic_page(driver, url):
    """
    Uses the existing driver instance to fetch a page.
    """
    try:
        # driver.get(url)
        # # Wait for JS execution
        # time.sleep(3) 
        # return driver.page_source
    
        driver.get(url)
        # Wait for JavaScript to render the content
        time.sleep(3) 
        
        # Get the full DOM
        full_html = driver.page_source
        
        # Remove all <script> and <style> tags
        soup = BeautifulSoup(full_html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        
        return str(soup)

    except Exception as e:
        print(f"Selenium Error on {url}: {e}")
        return None

def process_dynamic_page(input_file: Path, output_dir: Path):
    """
    Initializes Selenium once, processes items, then shuts down.
    """
    name = input_file.stem
    output_file = output_dir / f"{name}.jsonl"
    
    print(f"\n[Dynamic Phase] Starting {name}...")

    # 1. Load Data
    processed_urls = set()
    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    processed_urls.add(json.loads(line)["url"])
                except: continue

    with open(input_file, 'r', encoding='utf-8') as f:
        all_items = json.load(f)
    
    items_to_do = [x for x in all_items if x.get("url") not in processed_urls]
    del all_items # Clear RAM
    
    # 2. Selenium Logic (Only runs if we actually have items to scrape)
    if items_to_do:
        print(f"[{name}] Launching Chrome...")
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage") 
        options.add_argument("--disable-gpu")
        
        driver = webdriver.Chrome(options=options)
        
        # 3. Process Loop
        pbar = tqdm(total=len(items_to_do), desc=f"{name} (Selenium)", unit="pg")
        
        with open(output_file, 'a', encoding='utf-8') as f:
            for item in items_to_do:
                url = item.get("url")
                
                html = get_dynamic_page(driver, url)
                
                if html:
                    record = {"url": url, "html": html}
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    f.flush()
                
                pbar.update(1)
                time.sleep(random.uniform(2.0, 4.0))

        # 4. Cleanup
        driver.quit()
        pbar.close()
    
    else:
        print(f"[{name}] No new items to scrape.")

    # 5. Merge immediately (Runs regardless of whether we scraped or not)
    merge_and_cleanup_file(name, input_file, output_file)

def has_html_already(file_path: Path) -> bool:
    """
    Checks if 'html' key exists and has content WITHOUT loading the whole file.
    Reads only the first 10MB of the file to scan for the pattern.
    """
    try:
        # Read only the first 10MB (adjust size if needed, but 10MB is usually plenty to catch the first few items)
        with open(file_path, 'r', encoding='utf-8') as f:
            chunk = f.read(1024 * 1024 * 10) 
            
        # Quick heuristic check: does "html": " appear in the first chunk?
        # We look for "html": " followed by at least 20 chars of content
        if '"html": "' in chunk:
            # Check if it's not just an empty string ""
            # Find the index
            idx = chunk.find('"html": "')
            if idx != -1:
                # Look ahead a bit to see if it's not immediately closed
                # e.g. "html": "<html>...
                next_chars = chunk[idx+9 : idx+29]
                if len(next_chars) > 5 and '"' not in next_chars[:5]:
                    return True
    except Exception:
        return False
    return False

def merge_and_cleanup_file(name, input_path, output_path):
    print(f"[{name}] Merging data...")
    html_map = {}
    
    if output_path.exists():
        with open(output_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    d = json.loads(line)
                    html_map[d["url"]] = d["html"]
                except: continue

    with open(input_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    count = 0
    for item in raw_data:
        if item.get("url") in html_map:
            item["html"] = html_map[item["url"]]
            count += 1
            
    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(raw_data, f, indent=4, ensure_ascii=False)
        
    print(f"[{name}] Merged {count} items.")
    if output_path.exists():
        os.remove(output_path)

# ==========================================
# MAIN ORCHESTRATOR
# ==========================================

def download_html_content(input_dir: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    
    json_files = list(input_dir.glob("*.json"))
    
    # Separate files based on the global list
    dynamic_files = []
    static_files = []
    
    for f in json_files:
        if f.stem in DYNAMIC_SITES:  # <--- CHANGED: Checks against the global list
            dynamic_files.append(f)
        else:
            static_files.append(f)
            
    # --- STEP 1: Process Static Files ---
    print(f"=== PHASE 1: Static Files (Requests) - {len(static_files)} files ===")
    for json_file in static_files:
        if has_html_already(json_file):
            print(f"⏭️  Skipping {json_file.name}: Done.")
            continue

        processor = StaticProcessor({
            "name": json_file.stem,
            "input": json_file,
            "output": output_dir / f"{json_file.stem}.jsonl"
        })
        
        try:
            processor.run()
        except KeyboardInterrupt:
            print("Stopped.")
            return
        
        processor.close()
        merge_and_cleanup_file(processor.name, processor.input_path, processor.output_path)
        
        # Free memory
        del processor
        gc.collect()

    # --- STEP 2: Process Dynamic Files ---
    # FIXED: Iterate through dynamic_files list, not static_files
    if dynamic_files:
        print(f"\n=== PHASE 2: Dynamic Files (Selenium) - {len(dynamic_files)} files ===")
        
        for json_file in dynamic_files:
            if has_html_already(json_file):
                print(f"⏭️  Skipping {json_file.name}: Done.")
                continue

            # Explicitly collect garbage before starting Chrome
            gc.collect() 
            try:
                process_dynamic_page(json_file, output_dir)
            except KeyboardInterrupt:
                print("Stopped during Selenium phase.")
                return
            
    print("\n✅ All operations complete.")